from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from sqlalchemy.orm import Session

from .db.models import Approval, Artifact, Execution, Project, ProjectContextSnapshot
from .domain.hashing import canonical_json, sha256_canonical
from .repositories import ExecutionRepository
from .schemas import (
    ArtifactCreate,
    ArtifactReferenceInput,
    M3PreparationRequest,
    M3TransformationRule,
)
from .services import (
    ConflictError,
    NotFoundError,
    ValidationError,
    _verified_storage,
    artifacts,
    commit,
    create_artifact,
    record_audit,
    require_editable_project,
)
from .storage import ArtifactStore, ArtifactStoreError


class M3PreparationModule:
    """Deterministic, local preparation from M2 Bronze artifacts.

    M3 deliberately supports a small, explicit transformation vocabulary. A
    free-form action is not executable safely, so unsupported semantics are
    rejected instead of being guessed or silently ignored.
    """

    module_id = "m3"
    contract_version = "v1.1"
    supported_actions = frozenset(
        {
            "normalize_column_names",
            "drop_duplicate_rows",
            "fill_missing_values",
            "parse_date_columns",
            "drop_empty_rows",
        }
    )

    def __init__(self) -> None:
        self.executions = ExecutionRepository()

    def execute(
        self,
        db: Session,
        project_id: str,
        payload: M3PreparationRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict[str, Any]:
        self._validate_request(project_id, payload)
        self._validate_rules(payload.module_input.transformation_plan.rules)
        project = require_editable_project(db, project_id)
        context = db.get(ProjectContextSnapshot, payload.context_snapshot_id)
        if context is None or context.project_id != project_id:
            raise NotFoundError("Context snapshot not found for project")

        input_hash = self._input_hash(payload)
        locked_project = db.get(Project, project_id, with_for_update=True)
        if locked_project is None:
            raise NotFoundError("Project not found")

        existing = self.executions.get_by_idempotency(
            db, project_id, self.module_id, payload.idempotency_key
        )
        execution: Execution | None = None
        if existing is not None:
            if existing.input_hash != input_hash or existing.id != payload.execution_id:
                raise ConflictError("The idempotency key is already bound to another M3 execution")
            execution = existing
            if existing.status != "awaiting_approval" and existing.result_json is not None:
                return existing.result_json
        else:
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
            bronze_artifacts, source_manifest, frame = self._load_bronze_inputs(
                db, project_id, payload, artifact_store
            )
            preview, preview_summary, preview_rule_ids, preview_limitations = self._apply_rules(
                frame.copy(), payload.module_input.transformation_plan.rules
            )
            preview_quality = self._quality_report(
                preview,
                payload.module_input.quality_policy.required_checks,
                payload.module_input.quality_policy.blocking_conditions,
                preview_limitations,
            )

            requires_approval = any(
                rule.approval_required
                for rule in payload.module_input.transformation_plan.rules
            )
            approvals_satisfied = self._has_required_approvals(
                db, project_id, bronze_artifacts, payload
            )
            if requires_approval and not approvals_satisfied:
                if execution.result_json is not None and execution.status == "awaiting_approval":
                    return execution.result_json
                pending = self._result_envelope(
                    payload,
                    status="awaiting_approval",
                    artifacts=[],
                    warnings=payload.warnings,
                    errors=[],
                    next_actions=[
                        {
                            "action": "approve_transformations",
                            "requires_approval": True,
                            "target_module": "m3",
                        }
                    ],
                    module_output={
                        "transformation_summary": preview_summary,
                        "quality_report": preview_quality,
                        "lineage": [],
                        "approval_request": {
                            "action": "approve_transformations",
                            "reason": (
                                "Material M3 transformations require approval for each "
                                "input Bronze artifact before Silver and Gold are persisted."
                            ),
                        },
                    },
                )
                return self._persist_output(
                    db,
                    execution,
                    pending,
                    input_hash=input_hash,
                    correlation_id=payload.correlation_id,
                )

            prepared, summary, applied_rule_ids, limitations = self._apply_rules(
                frame, payload.module_input.transformation_plan.rules
            )
            quality = self._quality_report(
                prepared,
                payload.module_input.quality_policy.required_checks,
                payload.module_input.quality_policy.blocking_conditions,
                limitations,
            )
            if quality["status"] == "blocked":
                blocked = self._result_envelope(
                    payload,
                    status="failed_terminal",
                    artifacts=[],
                    warnings=payload.warnings,
                    errors=[
                        {
                            "code": "DATA_QUALITY_BLOCKED",
                            "message": "The M3 quality policy blocked the prepared dataset.",
                            "retryable": False,
                            "recovery_action": "review_quality_policy_and_transformation_plan",
                        }
                    ],
                    next_actions=[
                        {
                            "action": "review_quality_report",
                            "requires_approval": True,
                            "target_module": "m3",
                        }
                    ],
                    module_output={
                        "transformation_summary": summary,
                        "quality_report": quality,
                        "lineage": [],
                    },
                )
                return self._persist_output(
                    db,
                    execution,
                    blocked,
                    input_hash=input_hash,
                    correlation_id=payload.correlation_id,
                )

            silver_ref, gold_ref = self._persist_dataset_artifacts(
                db,
                project_id,
                execution,
                prepared,
                bronze_artifacts,
                applied_rule_ids,
                quality["status"],
                artifact_store,
                max_metadata_bytes=max_metadata_bytes,
                correlation_id=payload.correlation_id,
                business_rule_count=len(payload.module_input.business_rules),
            )
            lineage = [
                {
                    "input_artifact": self._artifact_reference(bronze),
                    "output_artifact": silver_ref,
                    "rule_ids": applied_rule_ids,
                }
                for bronze in bronze_artifacts
            ]
            lineage.append(
                {
                    "input_artifact": silver_ref,
                    "output_artifact": gold_ref,
                    "rule_ids": [],
                }
            )
            output = self._result_envelope(
                payload,
                status="succeeded",
                artifacts=[silver_ref, gold_ref],
                warnings=payload.warnings + self._quality_warnings(quality),
                errors=[],
                next_actions=[
                    {
                        "action": "review_prepared_datasets",
                        "requires_approval": False,
                        "target_module": "m4",
                    }
                ],
                module_output={
                    "silver_dataset": silver_ref,
                    "gold_dataset": gold_ref,
                    "transformation_summary": summary,
                    "quality_report": quality,
                    "lineage": lineage,
                },
            )
            return self._persist_output(
                db,
                execution,
                output,
                input_hash=input_hash,
                correlation_id=payload.correlation_id,
            )
        except (ValidationError, NotFoundError, ConflictError) as exc:
            self._fail_execution(db, execution.id, payload, input_hash, str(exc))
            raise
        except ArtifactStoreError as exc:
            self._fail_execution(
                db,
                execution.id,
                payload,
                input_hash,
                "Artifact storage failed during M3 preparation",
            )
            raise ValidationError("Artifact storage failed during preparation") from exc
        except Exception as exc:
            self._fail_execution(
                db,
                execution.id,
                payload,
                input_hash,
                "Unexpected M3 preparation failure",
            )
            raise RuntimeError("M3 preparation failed") from exc

    def _validate_request(self, project_id: str, payload: M3PreparationRequest) -> None:
        if payload.project_id != project_id:
            raise ValidationError("project_id in the contract does not match the URL scope")
        if payload.module_id != self.module_id:
            raise ValidationError("M3 execution requires module_id='m3'")
        if payload.contract_version != self.contract_version:
            raise ValidationError("M3 requires contract_version='v1.1'")
        if payload.status not in {"requested", "ready"}:
            raise ValidationError("M3 executions must start in requested or ready status")

    def _validate_rules(self, rules: list[M3TransformationRule]) -> None:
        seen: set[str] = set()
        for rule in rules:
            if rule.rule_id in seen:
                raise ValidationError("Transformation rule_id values must be unique")
            seen.add(rule.rule_id)
            if rule.action not in self.supported_actions:
                raise ValidationError(f"Unsupported M3 transformation action: {rule.action}")
            parameters = rule.parameters
            if rule.action == "fill_missing_values":
                strategy = parameters.get("strategy")
                if strategy not in {"zero", "mean", "median", "mode", "constant"}:
                    raise ValidationError(
                        "fill_missing_values requires strategy zero, mean, median, mode or constant"
                    )
                if strategy == "constant" and "value" not in parameters:
                    raise ValidationError("constant missing-value filling requires parameters.value")
            if rule.action == "drop_duplicate_rows":
                if parameters.get("keep", "first") not in {"first", "last", False}:
                    raise ValidationError("drop_duplicate_rows.keep must be first, last or false")
            if rule.action in {"fill_missing_values", "parse_date_columns"}:
                columns = parameters.get("columns")
                if columns is not None and (
                    not isinstance(columns, list)
                    or not all(isinstance(item, str) and item for item in columns)
                ):
                    raise ValidationError(f"{rule.action}.columns must be a list of names")

    @staticmethod
    def _input_hash(payload: M3PreparationRequest) -> str:
        data = payload.model_dump(mode="json", exclude={"approval_refs"})
        return sha256_canonical(data)

    def _load_bronze_inputs(
        self,
        db: Session,
        project_id: str,
        payload: M3PreparationRequest,
        artifact_store: ArtifactStore,
    ) -> tuple[list[Artifact], list[dict[str, Any]], Any]:
        import pandas as pd

        bronze_artifacts: list[Artifact] = []
        source_manifest: list[dict[str, Any]] = []
        source_keys: set[tuple[str, str]] = set()
        frames: list[Any] = []
        for source_ref in payload.module_input.bronze_artifacts:
            bronze = artifacts.get_by_logical_version(
                db, project_id, source_ref.artifact_id, source_ref.artifact_version
            )
            if bronze is None:
                raise NotFoundError("Bronze artifact not found for project")
            if bronze.content_hash != source_ref.content_hash:
                raise ValidationError("Bronze content_hash does not match the server record")
            if bronze.version_number != source_ref.version_number:
                raise ValidationError("Bronze version_number does not match the server record")
            if bronze.layer != "bronze":
                raise ValidationError("M3 inputs must reference Bronze artifacts")
            _verified_storage(artifact_store, bronze.storage_id, bronze.content_hash)
            try:
                manifest = json.loads(
                    artifact_store.read(bronze.storage_id, expected_hash=bronze.content_hash)
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValidationError("Bronze artifact is not a valid M2 manifest") from exc
            if manifest.get("project_id") != project_id or manifest.get("module_id") != "m2":
                raise ValidationError("Bronze manifest is outside the requested project or module")
            entries = manifest.get("source_manifest")
            if not isinstance(entries, list) or not entries:
                raise ValidationError("Bronze manifest has no preserved source artifacts")
            bronze_artifacts.append(bronze)
            for entry in entries:
                source_ref_data = entry.get("source_artifact") if isinstance(entry, dict) else None
                if not isinstance(source_ref_data, dict):
                    raise ValidationError("Bronze source manifest contains an invalid artifact reference")
                source_id = source_ref_data.get("artifact_id")
                source_version = source_ref_data.get("artifact_version")
                if not isinstance(source_id, str) or not isinstance(source_version, str):
                    raise ValidationError("Bronze source manifest lacks a logical artifact version")
                key = (source_id, source_version)
                if key in source_keys:
                    continue
                source = artifacts.get_by_logical_version(
                    db, project_id, source_id, source_version
                )
                if source is None:
                    raise NotFoundError("Bronze source artifact not found for project")
                if source.content_hash != source_ref_data.get("content_hash"):
                    raise ValidationError("Bronze source content_hash does not match the server record")
                if source.version_number != source_ref_data.get("version_number"):
                    raise ValidationError("Bronze source version_number does not match the server record")
                source_keys.add(key)
                metadata = entry.get("metadata") or {}
                _verified_storage(artifact_store, source.storage_id, source.content_hash)
                raw = artifact_store.read(source.storage_id, expected_hash=source.content_hash)
                frames.extend(self._read_source_tables(raw, metadata, source.media_type))
                source_manifest.append(entry)

        if not frames:
            raise ValidationError("M3 found no tabular source data in the Bronze artifacts")
        combined = pd.concat(frames, ignore_index=True, sort=False)
        if "_af_row_id" in combined.columns:
            raise ValidationError("The reserved _af_row_id column cannot be used as source data")
        combined.insert(0, "_af_row_id", range(len(combined.index)))
        return bronze_artifacts, source_manifest, combined

    @staticmethod
    def _read_source_tables(data: bytes, metadata: dict[str, Any], media_type: str | None) -> list[Any]:
        import pandas as pd

        format_name = metadata.get("format")
        if format_name not in {"csv", "xlsx", "xls"}:
            if media_type == "text/csv":
                format_name = "csv"
            elif "spreadsheetml" in (media_type or ""):
                format_name = "xlsx"
            elif "ms-excel" in (media_type or ""):
                format_name = "xls"
            else:
                raise ValidationError("Bronze source metadata does not declare a supported format")
        header = metadata.get("header_row")
        header = header if isinstance(header, int) else 0
        if format_name == "csv":
            return [
                pd.read_csv(
                    BytesIO(data),
                    encoding=metadata.get("encoding") or "utf-8",
                    sep=metadata.get("delimiter") or ",",
                    header=header,
                )
            ]
        engine = "openpyxl" if format_name == "xlsx" else "xlrd"
        workbook = pd.ExcelFile(BytesIO(data), engine=engine)
        sheet_name = metadata.get("sheet_name")
        sheets = [sheet_name] if sheet_name else workbook.sheet_names
        if any(sheet not in workbook.sheet_names for sheet in sheets):
            raise ValidationError("Bronze source metadata identifies a missing Excel sheet")
        return [workbook.parse(sheet_name=sheet, header=header) for sheet in sheets]

    def _apply_rules(
        self, frame: Any, rules: list[M3TransformationRule]
    ) -> tuple[Any, dict[str, Any], list[str], list[str]]:
        import pandas as pd

        df = frame.copy()
        input_rows = len(df.index)
        excluded_ids: set[int] = set()
        touched_ids: set[int] = set()
        exclusion_reasons: list[str] = []
        limitations: list[str] = []
        applied_rule_ids: list[str] = []
        for rule in rules:
            params = rule.parameters
            applied_rule_ids.append(rule.rule_id)
            if rule.action == "normalize_column_names":
                normalized: list[str] = []
                seen: dict[str, int] = {}
                for column in df.columns:
                    if column == "_af_row_id":
                        normalized.append(column)
                        continue
                    base = re.sub(r"[^a-zA-Z0-9]+", "_", str(column).strip().lower()).strip("_") or "column"
                    seen[base] = seen.get(base, 0) + 1
                    normalized.append(base if seen[base] == 1 else f"{base}_{seen[base]}")
                df.columns = normalized
            elif rule.action == "drop_duplicate_rows":
                keep = params.get("keep", "first")
                duplicate_mask = df.drop(columns=["_af_row_id"]).duplicated(keep=keep)
                excluded_ids.update(int(value) for value in df.loc[duplicate_mask, "_af_row_id"])
                if duplicate_mask.any():
                    exclusion_reasons.append("drop_duplicate_rows")
                    df = df.loc[~duplicate_mask].reset_index(drop=True)
            elif rule.action == "drop_empty_rows":
                empty_mask = df.drop(columns=["_af_row_id"]).isna().all(axis=1)
                excluded_ids.update(int(value) for value in df.loc[empty_mask, "_af_row_id"])
                if empty_mask.any():
                    exclusion_reasons.append("drop_empty_rows")
                    df = df.loc[~empty_mask].reset_index(drop=True)
            elif rule.action == "fill_missing_values":
                strategy = params["strategy"]
                columns = params.get("columns") or [
                    column for column in df.columns if column != "_af_row_id"
                ]
                self._require_columns(df, columns)
                for column in columns:
                    missing_mask = df[column].isna()
                    touched_ids.update(int(value) for value in df.loc[missing_mask, "_af_row_id"])
                    if not missing_mask.any():
                        continue
                    if strategy == "zero":
                        value = 0
                    elif strategy == "constant":
                        value = params["value"]
                    elif strategy == "mode":
                        modes = df[column].dropna().mode()
                        if modes.empty:
                            limitations.append(f"No mode was available for column {column}")
                            continue
                        value = modes.iloc[0]
                    elif strategy in {"mean", "median"}:
                        if not pd.api.types.is_numeric_dtype(df[column]):
                            raise ValidationError(
                                f"{strategy} missing-value filling requires numeric column {column}"
                            )
                        value = getattr(df[column].dropna(), strategy)()
                    else:
                        raise ValidationError(f"Unsupported missing-value strategy: {strategy}")
                    df[column] = df[column].fillna(value)
            elif rule.action == "parse_date_columns":
                columns = params.get("columns") or [
                    column
                    for column in df.columns
                    if column != "_af_row_id"
                    and any(token in str(column).lower() for token in ("date", "time", "fecha", "hora"))
                ]
                if not columns:
                    raise ValidationError("parse_date_columns could not identify any date columns")
                self._require_columns(df, columns)
                for column in columns:
                    non_null = df[column].notna()
                    parsed = pd.to_datetime(df[column], errors="coerce", format="mixed")
                    invalid = non_null & parsed.isna()
                    if invalid.any():
                        raise ValidationError(f"Could not parse date values in column {column}")
                    touched_ids.update(int(value) for value in df.loc[non_null, "_af_row_id"])
                    df[column] = parsed

        retained_rows = len(df.index)
        summary = {
            "input_rows": input_rows,
            "retained_rows": retained_rows,
            "transformed_rows": min(retained_rows, len(touched_ids - excluded_ids)),
            "excluded_rows": input_rows - retained_rows,
            "exclusion_reasons": sorted(set(exclusion_reasons)),
        }
        return df, summary, applied_rule_ids, limitations

    @staticmethod
    def _require_columns(frame: Any, columns: list[str]) -> None:
        missing = sorted(set(columns) - set(frame.columns))
        if missing:
            raise ValidationError("Transformation references missing columns: " + ", ".join(missing))

    @staticmethod
    def _quality_report(
        frame: Any,
        required_checks: list[str],
        blocking_conditions: list[str],
        limitations: list[str],
    ) -> dict[str, Any]:
        data = frame.drop(columns=["_af_row_id"], errors="ignore")
        duplicate_count = int(data.duplicated().sum())
        missing_count = int(data.isna().sum().sum())
        checks_by_id = {
            "non_empty_dataset": (len(data.index) > 0, len(data.index)),
            "columns_present": (len(data.columns) > 0, len(data.columns)),
            "no_duplicate_rows": (duplicate_count == 0, duplicate_count),
            "no_missing_values": (missing_count == 0, missing_count),
        }
        check_ids = required_checks or ["non_empty_dataset", "columns_present"]
        checks: list[dict[str, Any]] = []
        failed_blocking = False
        for check_id in check_ids:
            if check_id not in checks_by_id:
                check = {
                    "check_id": check_id,
                    "status": "not_implemented",
                    "observed": None,
                    "blocking": check_id in blocking_conditions,
                }
                limitations.append(f"Quality check {check_id} is not implemented in M3")
                if check_id in blocking_conditions:
                    failed_blocking = True
            else:
                passed, observed = checks_by_id[check_id]
                check = {
                    "check_id": check_id,
                    "status": "passed" if passed else "failed",
                    "observed": observed,
                    "blocking": check_id in blocking_conditions,
                }
                if not passed and check_id in blocking_conditions:
                    failed_blocking = True
            checks.append(check)
        return {
            "status": "blocked" if failed_blocking else ("passed_with_warnings" if any(
                check["status"] != "passed" for check in checks
            ) or limitations else "passed"),
            "checks": checks,
            "limitations": sorted(set(limitations)),
        }

    @staticmethod
    def _quality_warnings(quality: dict[str, Any]) -> list[str]:
        return [
            f"Quality check {check['check_id']} did not pass"
            for check in quality["checks"]
            if check["status"] != "passed"
        ] + [f"Quality limitation: {item}" for item in quality["limitations"]]

    @staticmethod
    def _has_required_approvals(
        db: Session,
        project_id: str,
        bronze_artifacts: list[Artifact],
        payload: M3PreparationRequest,
    ) -> bool:
        required = {(item.logical_id, item.artifact_version) for item in bronze_artifacts}
        approved: set[tuple[str, str]] = set()
        for reference in payload.approval_refs:
            if reference.action != "approve_transformations" or reference.status != "approved":
                continue
            if reference.scope_type != "artifact" or not reference.artifact_id or not reference.artifact_version:
                continue
            approval = db.get(Approval, reference.approval_id)
            if approval is None or approval.project_id != project_id:
                continue
            if approval.status != "approved" or approval.action != "approve_transformations":
                continue
            if approval.scope_type != "artifact" or approval.scope_hash != reference.scope_hash:
                continue
            target = db.get(Artifact, approval.artifact_id) if approval.artifact_id else None
            if target is None or target.project_id != project_id:
                continue
            target_key = (target.logical_id, target.artifact_version)
            if target_key not in required or reference.artifact_version != target.artifact_version:
                continue
            if reference.artifact_id not in {target.id, target.logical_id}:
                continue
            approved.add(target_key)
        return required <= approved

    def _persist_dataset_artifacts(
        self,
        db: Session,
        project_id: str,
        execution: Execution,
        prepared: Any,
        bronze_artifacts: list[Artifact],
        applied_rule_ids: list[str],
        quality_status: str,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
        correlation_id: str,
        business_rule_count: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        csv_bytes = prepared.drop(columns=["_af_row_id"], errors="ignore").to_csv(index=False).encode("utf-8")
        silver_stored = artifact_store.put(csv_bytes)
        bronze_parents = [
            ArtifactReferenceInput(
                artifact_id=bronze.logical_id,
                artifact_version=bronze.artifact_version,
            )
            for bronze in bronze_artifacts
        ]
        silver = create_artifact(
            db,
            project_id,
            ArtifactCreate(
                artifact_id=f"silver-{execution.id}",
                artifact_type="dataset.silver",
                artifact_version="v1",
                content_hash=silver_stored.content_hash,
                storage_id=silver_stored.storage_id,
                uri=silver_stored.uri,
                media_type="text/csv",
                layer="silver",
                produced_by_module=self.module_id,
                source_execution_id=execution.id,
                parent_artifact_refs=bronze_parents,
                metadata={
                    "transformation_rule_ids": applied_rule_ids,
                    "quality_status": quality_status,
                    "business_rule_count": business_rule_count,
                },
            ),
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
            correlation_id=correlation_id,
            commit_transaction=False,
        )
        gold_stored = artifact_store.put(csv_bytes)
        gold = create_artifact(
            db,
            project_id,
            ArtifactCreate(
                artifact_id=f"gold-{execution.id}",
                artifact_type="dataset.gold",
                artifact_version="v1",
                content_hash=gold_stored.content_hash,
                storage_id=gold_stored.storage_id,
                uri=gold_stored.uri,
                media_type="text/csv",
                layer="gold",
                produced_by_module=self.module_id,
                source_execution_id=execution.id,
                parent_artifact_refs=[
                    ArtifactReferenceInput(
                        artifact_id=silver.logical_id,
                        artifact_version=silver.artifact_version,
                    )
                ],
                metadata={
                    "prepared_from": silver.logical_id,
                    "quality_status": quality_status,
                    "business_rule_count": business_rule_count,
                },
            ),
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
            correlation_id=correlation_id,
            commit_transaction=False,
        )
        return self._artifact_reference(silver), self._artifact_reference(gold)

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
        payload: M3PreparationRequest,
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
            "module_id": "m3",
            "contract_version": payload.contract_version,
            "context_snapshot_id": payload.context_snapshot_id,
            "correlation_id": payload.correlation_id,
            "status": status,
            "artifacts": artifacts,
            "approval_refs": [
                reference.model_dump(mode="json", exclude_none=True)
                for reference in payload.approval_refs
            ],
            "warnings": warnings,
            "errors": errors,
            "next_actions": next_actions,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "module_output": module_output,
        }

    def _persist_output(
        self,
        db: Session,
        execution: Execution,
        output: dict[str, Any],
        *,
        input_hash: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        execution.status = output["status"]
        execution.output_hash = sha256_canonical(output)
        execution.result_json = output
        execution.completed_at = datetime.now(timezone.utc)
        record_audit(
            db,
            project_id=execution.project_id,
            action=(
                "execution.awaiting_approval"
                if output["status"] == "awaiting_approval"
                else "execution.completed"
            ),
            entity_type="execution",
            entity_id=execution.id,
            module_id=self.module_id,
            correlation_id=correlation_id,
            input_hash=input_hash,
            output_hash=execution.output_hash,
            metadata={"status": output["status"]},
        )
        commit(db)
        return output

    def _fail_execution(
        self,
        db: Session,
        execution_id: str,
        payload: M3PreparationRequest,
        input_hash: str,
        message: str,
    ) -> None:
        db.rollback()
        execution = self.executions.get(db, execution_id)
        if execution is None:
            return
        execution.status = "failed_terminal"
        execution.error_summary = message[:1000]
        execution.completed_at = datetime.now(timezone.utc)
        record_audit(
            db,
            project_id=execution.project_id,
            action="execution.failed",
            entity_type="execution",
            entity_id=execution.id,
            module_id=self.module_id,
            correlation_id=payload.correlation_id,
            input_hash=input_hash,
            metadata={"status": "failed_terminal", "error": "M3 preparation failed"},
        )
        commit(db)
