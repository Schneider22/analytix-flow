from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db.models import Artifact, Execution, ProjectContextSnapshot
from .domain.hashing import canonical_json, sha256_canonical
from .repositories import ExecutionRepository
from .schemas import ArtifactCreate, M2IngestionRequest
from .services import (
    ConflictError,
    NotFoundError,
    ValidationError,
    _verified_storage,
    artifacts,
    commit,
    create_artifact,
    record_audit,
    require_project,
)
from .storage import ArtifactStore, ArtifactStoreError


class M2IngestionModule:
    """Deterministic CSV/Excel profiling for the M2 contract.

    This module does not call another module, a model provider or the network.
    It receives already registered source artifacts and returns a versioned
    Bronze manifest plus a profile of the source bytes.
    """

    module_id = "m2"

    def __init__(self) -> None:
        self.executions = ExecutionRepository()

    def execute(
        self,
        db: Session,
        project_id: str,
        payload: M2IngestionRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict[str, Any]:
        if payload.project_id != project_id:
            raise ValidationError("project_id in the contract does not match the URL scope")
        if payload.module_id != self.module_id:
            raise ValidationError("M2 execution requires module_id='m2'")
        if payload.status not in {"requested", "ready"}:
            raise ValidationError("M2 executions must start in requested or ready status")

        project = require_project(db, project_id)
        context = db.get(ProjectContextSnapshot, payload.context_snapshot_id)
        if context is None or context.project_id != project.id:
            raise NotFoundError("Context snapshot not found for project")

        input_data = payload.model_dump(mode="json")
        input_hash = sha256_canonical(input_data)
        if payload.input_hash is not None and payload.input_hash != input_hash:
            raise ValidationError("input_hash does not match the canonical execution input")

        # The project row serializes M2 requests for one project and leaves the
        # unique constraint as the database-level guard for idempotency.
        locked_project = db.get(type(project), project_id, with_for_update=True)
        if locked_project is None:
            raise NotFoundError("Project not found")
        existing = self.executions.get_by_idempotency(
            db, project_id, self.module_id, payload.idempotency_key
        )
        if existing is not None:
            if existing.input_hash != input_hash or existing.id != payload.execution_id:
                raise ConflictError("The idempotency key is already bound to another execution")
            if existing.result_json is not None:
                return existing.result_json
            raise ConflictError("The idempotent execution is already running")

        existing_by_id = self.executions.get(db, payload.execution_id)
        if existing_by_id is not None:
            raise ConflictError("execution_id is already in use")

        now = datetime.now(timezone.utc)
        execution = Execution(
            id=payload.execution_id,
            project_id=project_id,
            module_id=self.module_id,
            contract_version=payload.contract_version,
            context_snapshot_id=context.id,
            status="running",
            idempotency_key=payload.idempotency_key,
            correlation_id=payload.correlation_id,
            input_hash=input_hash,
            requested_at=payload.requested_at or now,
            started_at=now,
        )
        self.executions.create(db, execution)
        record_audit(
            db,
            project_id=project_id,
            action="execution.started",
            entity_type="execution",
            entity_id=execution.id,
            module_id=self.module_id,
            correlation_id=payload.correlation_id,
            input_hash=input_hash,
            metadata={"contract_version": payload.contract_version},
        )
        commit(db)

        try:
            profile_result = self._profile_sources(
                db, project_id, payload, artifact_store
            )
            manifest = {
                "execution_id": execution.id,
                "project_id": project_id,
                "module_id": self.module_id,
                "contract_version": payload.contract_version,
                "selected_alternative_id": payload.module_input.selected_alternative_id,
                "source_manifest": profile_result["source_manifest"],
                "profile_report": profile_result["profile_report"],
                "issues": profile_result["issues"],
                "recovery_options": profile_result["recovery_options"],
            }
            manifest_bytes = canonical_json(manifest).encode("utf-8")
            stored = artifact_store.put(manifest_bytes)
            bronze_payload = ArtifactCreate(
                artifact_id=f"bronze-{execution.id}",
                artifact_type="dataset.bronze",
                artifact_version="v1",
                content_hash=stored.content_hash,
                storage_id=stored.storage_id,
                uri=stored.uri,
                media_type="application/json",
                layer="bronze",
                produced_by_module=self.module_id,
                source_execution_id=execution.id,
                metadata={
                    "source_count": len(profile_result["source_manifest"]),
                    "profile_status": "failed" if profile_result["errors"] else "complete",
                },
            )
            bronze = create_artifact(
                db,
                project_id,
                bronze_payload,
                artifact_store,
                max_metadata_bytes=max_metadata_bytes,
                correlation_id=payload.correlation_id,
            )
            bronze_ref = self._artifact_reference(bronze)
            requires_review = any(
                item["requires_human_decision"] for item in profile_result["issues"]
            )
            status = "failed_terminal" if profile_result["errors"] else "succeeded"
            output = self._result_envelope(
                payload,
                status=status,
                artifacts=[bronze_ref],
                warnings=payload.warnings + profile_result["warnings"],
                errors=profile_result["errors"],
                next_actions=[
                    {
                        "action": "review_ingestion_profile",
                        "requires_approval": requires_review,
                        "target_module": "m3",
                    }
                ],
                module_output={
                    "bronze_dataset": bronze_ref,
                    "source_manifest": profile_result["source_manifest"],
                    "profile_report": profile_result["profile_report"],
                    "issues": profile_result["issues"],
                    "recovery_options": profile_result["recovery_options"],
                },
            )
            if requires_review:
                output["status"] = "awaiting_approval"
                output["module_output"]["approval_request"] = {
                    "action": "approve_ingestion_interpretation",
                    "reason": "The ingestion profile contains an interpretation or quality issue requiring review.",
                }
            self._finish_execution(
                db,
                execution.id,
                output,
                input_hash=input_hash,
                correlation_id=payload.correlation_id,
            )
            return output
        except (ValidationError, NotFoundError, ConflictError):
            raise
        except ArtifactStoreError as exc:
            db.rollback()
            self._fail_execution(
                db,
                execution.id,
                payload,
                input_hash,
                "Artifact storage failed during M2 ingestion",
            )
            raise ValidationError("Artifact storage failed during ingestion") from exc
        except Exception as exc:
            db.rollback()
            self._fail_execution(
                db,
                execution.id,
                payload,
                input_hash,
                "Unexpected M2 ingestion failure",
            )
            raise RuntimeError("M2 ingestion failed") from exc

    def _profile_sources(
        self,
        db: Session,
        project_id: str,
        payload: M2IngestionRequest,
        artifact_store: ArtifactStore,
    ) -> dict[str, Any]:
        sources = payload.module_input.source_artifacts
        options = {item.artifact_id: item for item in payload.module_input.ingestion_options}
        if len(options) != len(payload.module_input.ingestion_options):
            raise ValidationError("Each ingestion option must identify a unique source artifact")
        if set(options) != {item.artifact_id for item in sources}:
            raise ValidationError("Ingestion options must match the source artifact set exactly")

        source_manifest: list[dict[str, Any]] = []
        structures: list[str] = []
        column_reports: list[dict[str, Any]] = []
        temporal_coverage: dict[str, Any] = {}
        identifiers: list[str] = []
        issues: list[dict[str, Any]] = []
        warnings: list[str] = []
        errors: list[dict[str, Any]] = []
        total_rows = 0
        total_columns = 0

        for source_ref in sources:
            artifact = artifacts.get_by_logical_version(
                db, project_id, source_ref.artifact_id, source_ref.artifact_version
            )
            if artifact is None:
                raise NotFoundError("Source artifact not found for project")
            if source_ref.content_hash != artifact.content_hash:
                raise ValidationError("Source artifact content_hash does not match the server record")
            if source_ref.version_number != artifact.version_number:
                raise ValidationError("Source artifact version_number does not match the server record")

            stored = _verified_storage(artifact_store, artifact.storage_id, artifact.content_hash)
            source_bytes = artifact_store.read(artifact.storage_id, expected_hash=artifact.content_hash)
            option = options[artifact.logical_id]
            manifest_item = {
                "source_artifact": self._artifact_reference(artifact),
                "preserved": True,
                "content_hash": stored.content_hash,
                "metadata": {
                    "size_bytes": stored.size_bytes,
                    "format": option.format,
                    "sheet_name": option.sheet_name,
                },
            }
            source_manifest.append(manifest_item)
            try:
                tables = self._read_tables(source_bytes, option)
                for structure_name, frame in tables:
                    profile = self._profile_table(structure_name, frame)
                    structures.append(structure_name)
                    column_reports.extend(profile["columns"])
                    temporal_coverage.update(profile["temporal_coverage"])
                    identifiers.extend(profile["potential_identifiers"])
                    total_rows += profile["row_count"]
                    total_columns += profile["column_count"]
                    issues.extend(profile["issues"])
            except Exception:
                description = "The source could not be parsed with the declared format or options."
                issue = {
                    "issue_id": f"parse-{artifact.logical_id}",
                    "severity": "blocking",
                    "description": description,
                    "requires_human_decision": True,
                }
                issues.append(issue)
                errors.append(
                    {
                        "code": "VALIDATION_ERROR",
                        "message": description,
                        "retryable": False,
                        "recovery_action": "review_ingestion_options_and_retry",
                    }
                )

        profile_report = {
            "structures": structures,
            "row_count": total_rows,
            "column_count": total_columns,
            "columns": column_reports,
            "temporal_coverage": temporal_coverage,
            "potential_identifiers": sorted(set(identifiers)),
        }
        recovery_options = [
            {
                "option_id": "review-ingestion-options",
                "description": "Review encoding, delimiter, header row or Excel sheet selection and retry.",
                "requires_approval": True,
            }
        ] if errors else []
        if any(item["severity"] == "warning" for item in issues):
            warnings.append("The profile contains quality warnings that should be reviewed before M3.")
        return {
            "source_manifest": source_manifest,
            "profile_report": profile_report,
            "issues": issues,
            "recovery_options": recovery_options,
            "warnings": warnings,
            "errors": errors,
        }

    @staticmethod
    def _read_tables(stored, option):
        try:
            import pandas as pd
        except ModuleNotFoundError as exc:
            raise ValidationError("pandas is required for M2 ingestion") from exc

        data = stored
        if option.format == "csv":
            return [("table", pd.read_csv(BytesIO(data), encoding=option.encoding or "utf-8", sep=option.delimiter or ",", header=option.header_row if option.header_row is not None else 0))]

        engine = "openpyxl" if option.format == "xlsx" else "xlrd"
        workbook = pd.ExcelFile(BytesIO(data), engine=engine)
        sheets = [option.sheet_name] if option.sheet_name else workbook.sheet_names
        missing = [sheet for sheet in sheets if sheet not in workbook.sheet_names]
        if missing:
            raise ValueError("Requested Excel sheet does not exist")
        return [
            (f"sheet:{sheet}", workbook.parse(sheet_name=sheet, header=option.header_row if option.header_row is not None else 0))
            for sheet in sheets
        ]

    @staticmethod
    def _profile_table(structure_name: str, frame) -> dict[str, Any]:
        import pandas as pd

        columns: list[dict[str, Any]] = []
        temporal: dict[str, Any] = {}
        potential_identifiers: list[str] = []
        row_count = int(len(frame.index))
        for column in frame.columns:
            name = str(column)
            series = frame[column]
            missing_count = int(series.isna().sum())
            non_null = int(series.notna().sum())
            unique_count = int(series.nunique(dropna=True))
            columns.append(
                {
                    "name": name,
                    "dtype": str(series.dtype),
                    "missing_count": missing_count,
                    "unique_count": unique_count,
                    "null_ratio": (missing_count / row_count) if row_count else 0,
                }
            )
            normalized_name = name.strip().lower()
            if non_null and unique_count == non_null and (
                normalized_name == "id" or normalized_name.endswith("_id") or unique_count == row_count
            ):
                potential_identifiers.append(name)
            temporal_candidate = pd.api.types.is_datetime64_any_dtype(series) or any(
                token in normalized_name
                for token in ("date", "time", "fecha", "hora", "timestamp")
            )
            if temporal_candidate:
                parsed = (
                    series
                    if pd.api.types.is_datetime64_any_dtype(series)
                    else pd.to_datetime(series, errors="coerce", format="mixed")
                )
                if int(parsed.notna().sum()) >= 2 and int(parsed.notna().sum()) >= max(2, int(non_null * 0.8)):
                    temporal[name] = {
                        "min": parsed.min().isoformat(),
                        "max": parsed.max().isoformat(),
                    }

        duplicate_count = int(frame.duplicated().sum())
        issues: list[dict[str, Any]] = []
        if duplicate_count:
            issues.append(
                {
                    "issue_id": f"duplicates-{structure_name}",
                    "severity": "warning",
                    "description": f"{duplicate_count} duplicate rows were detected; no rows were removed.",
                    "requires_human_decision": False,
                }
            )
        return {
            "row_count": row_count,
            "column_count": int(len(frame.columns)),
            "columns": columns,
            "temporal_coverage": {structure_name: temporal},
            "potential_identifiers": [f"{structure_name}.{item}" for item in potential_identifiers],
            "issues": issues,
        }

    @staticmethod
    def _artifact_reference(artifact: Artifact) -> dict[str, Any]:
        reference = {
            "artifact_id": artifact.logical_id,
            "artifact_type": artifact.artifact_type,
            "artifact_version": artifact.artifact_version,
            "version_number": artifact.version_number,
            "version_id": artifact.id,
            "content_hash": artifact.content_hash,
        }
        optional = {
            "predecessor_version_id": artifact.predecessor_artifact_id,
            "uri": artifact.uri,
            "media_type": artifact.media_type,
            "layer": artifact.layer,
            "produced_by_module": artifact.produced_by_module,
            "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
        }
        reference.update({key: value for key, value in optional.items() if value is not None})
        return reference

    @staticmethod
    def _result_envelope(
        payload: M2IngestionRequest,
        *,
        status: str,
        artifacts: list[dict[str, Any]],
        warnings: list[str],
        errors: list[dict[str, Any]],
        next_actions: list[dict[str, Any]],
        module_output: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "project_id": payload.project_id,
            "execution_id": payload.execution_id,
            "module_id": "m2",
            "contract_version": payload.contract_version,
            "context_snapshot_id": payload.context_snapshot_id,
            "correlation_id": payload.correlation_id,
            "status": status,
            "artifacts": artifacts,
            "approval_refs": payload.approval_refs,
            "warnings": warnings,
            "errors": errors,
            "next_actions": next_actions,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "module_output": module_output,
        }

    def _finish_execution(
        self, db: Session, execution_id: str, output: dict[str, Any], *, input_hash: str, correlation_id: str
    ) -> None:
        execution = self.executions.get(db, execution_id)
        if execution is None:
            raise RuntimeError("Execution disappeared while completing M2")
        output_hash = sha256_canonical(output)
        execution.status = output["status"]
        execution.output_hash = output_hash
        execution.result_json = output
        execution.completed_at = datetime.now(timezone.utc)
        record_audit(
            db,
            project_id=execution.project_id,
            action="execution.completed",
            entity_type="execution",
            entity_id=execution.id,
            module_id="m2",
            correlation_id=correlation_id,
            input_hash=input_hash,
            output_hash=output_hash,
            metadata={"status": output["status"]},
        )
        commit(db)

    def _fail_execution(
        self,
        db: Session,
        execution_id: str,
        payload: M2IngestionRequest,
        input_hash: str,
        message: str,
    ) -> None:
        execution = self.executions.get(db, execution_id)
        if execution is None:
            return
        execution.status = "failed_terminal"
        execution.error_summary = message
        execution.completed_at = datetime.now(timezone.utc)
        record_audit(
            db,
            project_id=execution.project_id,
            action="execution.failed",
            entity_type="execution",
            entity_id=execution.id,
            module_id="m2",
            correlation_id=payload.correlation_id,
            input_hash=input_hash,
            metadata={"status": "failed_terminal", "error": message},
        )
        commit(db)
