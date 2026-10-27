from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db.models import Approval, Artifact, ArtifactLineage, Execution, Project, ProjectContextSnapshot
from .domain.hashing import canonical_json, sha256_canonical
from .repositories import ExecutionRepository
from .schemas import ArtifactReferenceInput, M5EvaluationRequest
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


class M5EvaluationModule:
    """Review M4 evidence without retraining or selecting a model.

    M4 currently stores measured preliminary metrics and the configuration used
    to produce them, but not the exact row indices or fold assignments. M5
    therefore evaluates the persisted evidence, makes that limitation
    explicit, and always leaves the decision behind human approval.
    """

    module_id = "m5"
    contract_version = "v1.0"

    def __init__(self) -> None:
        self.executions = ExecutionRepository()

    def execute(
        self,
        db: Session,
        project_id: str,
        payload: M5EvaluationRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict[str, Any]:
        self._validate_request(project_id, payload)
        project = require_editable_project(db, project_id)
        context = db.get(ProjectContextSnapshot, payload.context_snapshot_id)
        if context is None or context.project_id != project_id:
            raise NotFoundError("Context snapshot not found for project")

        input_hash = sha256_canonical(payload.model_dump(mode="json"))
        locked_project = db.get(Project, project_id, with_for_update=True)
        if locked_project is None:
            raise NotFoundError("Project not found")

        existing = self.executions.get_by_idempotency(
            db, project_id, self.module_id, payload.idempotency_key
        )
        if existing is not None:
            if existing.input_hash != input_hash or existing.id != payload.execution_id:
                raise ConflictError("The idempotency key is already bound to another M5 execution")
            if existing.result_json is not None:
                return existing.result_json
            raise ConflictError("The idempotent M5 execution is already running")

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

        staged_storage_ids: list[str] = []
        try:
            evidence = self._load_evidence(
                db, project_id, payload, artifact_store
            )
            output = self._persist_report(
                db,
                project_id,
                execution,
                payload,
                evidence,
                artifact_store,
                max_metadata_bytes=max_metadata_bytes,
                staged_storage_ids=staged_storage_ids,
            )
            return self._persist_output(
                db,
                execution,
                output,
                input_hash=input_hash,
                correlation_id=payload.correlation_id,
            )
        except (ValidationError, NotFoundError, ConflictError) as exc:
            self._cleanup_staged_artifacts(artifact_store, staged_storage_ids)
            self._fail_execution(db, execution.id, payload, input_hash, str(exc))
            raise
        except ArtifactStoreError as exc:
            self._cleanup_staged_artifacts(artifact_store, staged_storage_ids)
            self._fail_execution(
                db,
                execution.id,
                payload,
                input_hash,
                "Artifact storage failed during M5 evaluation",
            )
            raise ValidationError("Artifact storage failed during evaluation") from exc
        except Exception as exc:
            self._cleanup_staged_artifacts(artifact_store, staged_storage_ids)
            self._fail_execution(
                db,
                execution.id,
                payload,
                input_hash,
                "Unexpected M5 evaluation failure",
            )
            raise RuntimeError("M5 evaluation failed") from exc

    def _validate_request(self, project_id: str, payload: M5EvaluationRequest) -> None:
        if payload.project_id != project_id:
            raise ValidationError("project_id in the contract does not match the URL scope")
        if payload.module_id != self.module_id:
            raise ValidationError("M5 execution requires module_id='m5'")
        if payload.contract_version != self.contract_version:
            raise ValidationError("M5 requires contract_version='v1.0'")
        if payload.status not in {"requested", "ready"}:
            raise ValidationError("M5 executions must start in requested or ready status")

        policy = payload.module_input.evaluation_policy
        primary = [item.strip() for item in policy.primary_metrics]
        secondary = [item.strip() for item in policy.secondary_metrics]
        if any(not item for item in primary + secondary):
            raise ValidationError("Evaluation metric names must be non-empty")
        if len(set(primary + secondary)) != len(primary + secondary):
            raise ValidationError("Evaluation metric names must be unique")

        references = payload.module_input.candidate_models
        identity = [
            (item.artifact_id, item.artifact_version, item.version_id)
            for item in references
        ]
        if len(set(identity)) != len(identity):
            raise ValidationError("candidate_models must contain unique artifact versions")

    def _load_evidence(
        self,
        db: Session,
        project_id: str,
        payload: M5EvaluationRequest,
        artifact_store: ArtifactStore,
    ) -> dict[str, Any]:
        gold = artifacts.get_by_logical_version(
            db,
            project_id,
            payload.module_input.gold_dataset.artifact_id,
            payload.module_input.gold_dataset.artifact_version,
        )
        if gold is None:
            raise NotFoundError("Gold dataset artifact not found for project")
        self._validate_artifact_reference(
            gold, payload.module_input.gold_dataset, expected_layer="gold"
        )
        _verified_storage(artifact_store, gold.storage_id, gold.content_hash)

        candidate_artifacts: list[Artifact] = []
        source_execution: Execution | None = None
        source_output: dict[str, Any] | None = None
        candidate_entries: list[dict[str, Any]] = []
        experiment_artifact: Artifact | None = None
        experiment_payload: dict[str, Any] | None = None

        for reference in payload.module_input.candidate_models:
            candidate = artifacts.get_by_logical_version(
                db, project_id, reference.artifact_id, reference.artifact_version
            )
            if candidate is None:
                raise NotFoundError("Candidate model artifact not found for project")
            self._validate_artifact_reference(candidate, reference, expected_type="model.pipeline")
            _verified_storage(artifact_store, candidate.storage_id, candidate.content_hash)
            if not candidate.source_execution_id:
                raise ValidationError("Candidate model is missing its source M4 execution")

            candidate_source = db.get(Execution, candidate.source_execution_id)
            if (
                candidate_source is None
                or candidate_source.project_id != project_id
                or candidate_source.module_id != "m4"
                or candidate_source.status != "succeeded"
                or not isinstance(candidate_source.result_json, dict)
            ):
                raise ValidationError("Candidate model does not reference a successful M4 execution")
            if source_execution is None:
                source_execution = candidate_source
                source_output = candidate_source.result_json
            elif source_execution.id != candidate_source.id:
                raise ValidationError(
                    "All M5 candidate models must come from the same M4 execution"
                )

            assert source_output is not None
            module_output = source_output.get("module_output")
            if not isinstance(module_output, dict):
                raise ValidationError("M4 execution output does not contain module_output")
            entries = module_output.get("candidates")
            if not isinstance(entries, list):
                raise ValidationError("M4 execution output does not contain candidate evidence")
            matching = [
                item
                for item in entries
                if isinstance(item, dict)
                and self._reference_matches(item.get("pipeline_artifact"), candidate)
            ]
            if len(matching) != 1:
                raise ValidationError(
                    "Candidate model artifact is not represented exactly once in the M4 result"
                )
            candidate_entry = matching[0]
            if candidate.metadata_json.get("candidate_id") != candidate_entry.get("candidate_id"):
                raise ValidationError("Candidate model metadata does not match the M4 result")
            if candidate_entry not in candidate_entries:
                candidate_entries.append(candidate_entry)
            candidate_artifacts.append(candidate)

        approval_refs = self._validate_candidate_approvals(
            db, project_id, payload, candidate_artifacts
        )

        assert source_execution is not None
        assert source_output is not None
        module_output = source_output.get("module_output")
        experiment_refs = module_output.get("experiment_artifacts") if isinstance(module_output, dict) else None
        if not isinstance(experiment_refs, list) or len(experiment_refs) != 1:
            raise ValidationError("M4 execution must expose exactly one experiment artifact")
        experiment_ref = experiment_refs[0]
        if not isinstance(experiment_ref, dict):
            raise ValidationError("M4 experiment reference is invalid")
        experiment_artifact = artifacts.get_by_logical_version(
            db,
            project_id,
            experiment_ref.get("artifact_id"),
            experiment_ref.get("artifact_version"),
        )
        if experiment_artifact is None:
            raise NotFoundError("M4 experiment artifact not found for project")
        self._validate_artifact_reference(
            experiment_artifact, experiment_ref, expected_type="experiment.m4"
        )
        experiment_bytes = artifact_store.read(
            experiment_artifact.storage_id,
            expected_hash=experiment_artifact.content_hash,
        )
        try:
            parsed_experiment = json.loads(experiment_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("M4 experiment artifact is not valid JSON") from exc
        if not isinstance(parsed_experiment, dict):
            raise ValidationError("M4 experiment artifact must contain a JSON object")
        experiment_payload = parsed_experiment

        expected_gold = experiment_payload.get("gold_dataset")
        if not self._same_reference(expected_gold, gold):
            raise ValidationError(
                "M5 gold_dataset must match the Gold artifact evaluated by M4"
            )
        problem_ref = experiment_payload.get("problem_definition")
        if not isinstance(problem_ref, dict):
            raise ValidationError("M4 experiment does not contain a problem-definition reference")
        problem_artifact = artifacts.get_by_logical_version(
            db,
            project_id,
            problem_ref.get("artifact_id"),
            problem_ref.get("artifact_version"),
        )
        if problem_artifact is None:
            raise NotFoundError("M4 problem-definition artifact not found for project")
        self._validate_artifact_reference(problem_artifact, problem_ref)
        if problem_artifact.id == gold.id:
            raise ValidationError("M4 problem-definition and Gold artifacts must be different")
        problem_bytes = artifact_store.read(
            problem_artifact.storage_id,
            expected_hash=problem_artifact.content_hash,
        )
        self._validate_problem_definition(problem_bytes, experiment_payload)

        experiment_parent_ids = set(
            db.scalars(
                select(ArtifactLineage.parent_artifact_id).where(
                    ArtifactLineage.project_id == project_id,
                    ArtifactLineage.child_artifact_id == experiment_artifact.id,
                )
            )
        )
        if not {gold.id, problem_artifact.id}.issubset(experiment_parent_ids):
            raise ValidationError("M4 experiment lineage does not contain Gold and problem-definition inputs")
        for candidate in candidate_artifacts:
            candidate_parent_ids = set(
                db.scalars(
                    select(ArtifactLineage.parent_artifact_id).where(
                        ArtifactLineage.project_id == project_id,
                        ArtifactLineage.child_artifact_id == candidate.id,
                    )
                )
            )
            if experiment_artifact.id not in candidate_parent_ids:
                raise ValidationError("M4 candidate lineage does not point to its experiment")

        self._validate_experiment_configuration(experiment_payload, module_output)
        if source_execution.output_hash != sha256_canonical(source_output):
            raise ValidationError("M4 execution result hash does not match persisted evidence")
        if experiment_payload.get("candidate_ids") != [
            item.get("candidate_id") for item in module_output.get("candidates", [])
        ]:
            raise ValidationError("M4 experiment candidate identifiers are inconsistent")
        expected_strategy = payload.module_input.evaluation_policy.validation_strategy
        if experiment_payload.get("split_policy", {}).get("strategy") != expected_strategy:
            raise ValidationError(
                "M5 validation_strategy does not match the M4 split policy"
            )

        all_entries = module_output.get("candidates")
        if not isinstance(all_entries, list):
            raise ValidationError("M4 candidate evidence is invalid")
        baseline_selector = payload.module_input.baseline.artifact_or_method
        baseline_entry = next(
            (
                item
                for item in all_entries
                if isinstance(item, dict)
                and (
                    item.get("candidate_id") == baseline_selector
                    or item.get("technique") == baseline_selector
                )
            ),
            None,
        )
        if baseline_entry is None:
            raise ValidationError(
                "The declared baseline is not present in the M4 execution evidence"
            )

        return {
            "gold": gold,
            "candidate_artifacts": candidate_artifacts,
            "source_execution": source_execution,
            "source_output": source_output,
            "experiment_artifact": experiment_artifact,
            "problem_artifact": problem_artifact,
            "experiment_payload": experiment_payload,
            "approval_refs": approval_refs,
            "candidate_entries": candidate_entries,
            "all_entries": all_entries,
            "baseline_entry": baseline_entry,
        }

    @staticmethod
    def _validate_candidate_approvals(
        db: Session,
        project_id: str,
        payload: M5EvaluationRequest,
        candidates: list[Artifact],
    ) -> list[dict[str, Any]]:
        used_approval_ids: set[str] = set()
        canonical_refs: list[dict[str, Any]] = []
        for candidate in candidates:
            matches = [
                reference
                for reference in payload.approval_refs
                if reference.action == "select_model_candidate"
                and reference.scope_type == "artifact"
                and reference.status == "approved"
                and reference.artifact_id == candidate.logical_id
                and reference.artifact_version == candidate.artifact_version
            ]
            if len(matches) != 1:
                raise ValidationError(
                    "M5 requires one approved select_model_candidate approval per evaluated artifact"
                )
            reference = matches[0]
            if reference.approval_id in used_approval_ids:
                raise ValidationError("An approval cannot be reused for multiple M5 candidates")
            used_approval_ids.add(reference.approval_id)
            approval = db.get(Approval, reference.approval_id)
            if (
                approval is None
                or approval.project_id != project_id
                or approval.action != "select_model_candidate"
                or approval.scope_type != "artifact"
                or approval.status != "approved"
                or approval.artifact_id != candidate.id
                or approval.artifact_version != candidate.artifact_version
                or approval.scope_hash != reference.scope_hash
            ):
                raise ValidationError(
                    "Candidate approval does not match the exact project-scoped artifact version"
                )
            canonical_refs.append(
                {
                    "approval_id": approval.id,
                    "action": approval.action,
                    "scope_type": approval.scope_type,
                    "status": approval.status,
                    "scope_hash": approval.scope_hash,
                    "artifact_id": candidate.logical_id,
                    "artifact_version": candidate.artifact_version,
                    "approved_by": approval.resolved_by,
                    "approved_at": (
                        approval.resolved_at.isoformat()
                        if approval.resolved_at is not None
                        else None
                    ),
                }
            )
        return canonical_refs

    def _persist_report(
        self,
        db: Session,
        project_id: str,
        execution: Execution,
        payload: M5EvaluationRequest,
        evidence: dict[str, Any],
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
        staged_storage_ids: list[str],
    ) -> dict[str, Any]:
        experiment_payload = evidence["experiment_payload"]
        problem_type = experiment_payload.get("problem_type")
        baseline_entry = evidence["baseline_entry"]
        baseline_results = baseline_entry.get("preliminary_results")
        if not isinstance(baseline_results, dict):
            raise ValidationError("M4 baseline evidence is incomplete")
        self._validate_measured_results(baseline_results, problem_type, "baseline")

        comparisons: list[dict[str, Any]] = []
        all_metrics: set[str] = set()
        policy = payload.module_input.evaluation_policy
        requested_metrics = policy.primary_metrics + policy.secondary_metrics
        for entry in evidence["candidate_entries"]:
            preliminary = entry.get("preliminary_results")
            if not isinstance(preliminary, dict):
                raise ValidationError(
                    "M5 requires measured preliminary results from M4"
                )
            self._validate_measured_results(
                preliminary, problem_type, f"candidate {entry.get('candidate_id')}"
            )
            metrics = preliminary.get("metrics")
            missing_for_candidate = sorted(set(requested_metrics) - set(metrics))
            if missing_for_candidate:
                raise ValidationError(
                    f"Requested metrics are missing from candidate {entry.get('candidate_id')}: "
                    + ", ".join(missing_for_candidate)
                )
            all_metrics.update(metrics)

            expected_comparison = self._baseline_comparison(
                preliminary,
                baseline_results,
                problem_type,
                baseline_entry.get("candidate_id"),
            )
            existing_comparison = preliminary.get("baseline_comparison")
            if existing_comparison is not None and existing_comparison != expected_comparison:
                raise ValidationError(
                    f"Baseline comparison is inconsistent for candidate {entry.get('candidate_id')}"
                )
            baseline_comparison = expected_comparison
            comparison = {
                "candidate_id": entry.get("candidate_id"),
                "metrics": {
                    "result_classification": "measured",
                    "values": metrics,
                    "metric_std": preliminary.get("metric_std", {}),
                    "primary_metric": preliminary.get("primary_metric"),
                },
                "baseline_comparison": baseline_comparison,
                "limitations": self._limitations(entry, preliminary),
            }
            comparisons.append(comparison)

        baseline_candidate_id = baseline_entry.get("candidate_id")
        all_candidate_ids = {item.get("candidate_id") for item in evidence["all_entries"]}
        if baseline_candidate_id not in all_candidate_ids:
            raise ValidationError("M4 baseline evidence is inconsistent")
        missing_baseline_metrics = sorted(set(requested_metrics) - set(baseline_results["metrics"]))
        if missing_baseline_metrics:
            raise ValidationError(
                "Requested metrics are missing from the declared baseline: "
                + ", ".join(missing_baseline_metrics)
            )

        limitation = (
            "M4 did not persist exact row indices or fold assignments; this report "
            "reviews measured preliminary evidence and does not claim an independent re-evaluation."
        )
        report = {
            "report_version": "v1.0",
            "evaluation_type": "evidence_review",
            "evidence_classification": "measured_preliminary",
            "evidence_level": "low",
            "project_id": project_id,
            "m5_execution_id": execution.id,
            "m4_execution_id": evidence["source_execution"].id,
            "gold_dataset": self._artifact_reference(evidence["gold"]),
            "experiment_artifact": self._artifact_reference(evidence["experiment_artifact"]),
            "problem_definition": self._artifact_reference(evidence["problem_artifact"]),
            "baseline": {
                "description": payload.module_input.baseline.description,
                "artifact_or_method": payload.module_input.baseline.artifact_or_method,
                "candidate_id": baseline_candidate_id,
            },
            "evaluation_policy": policy.model_dump(mode="json"),
            "approval_refs": evidence["approval_refs"],
            "success_criteria": payload.module_input.success_criteria,
            "criteria_assessment": {
                "status": "not_machine_evaluable",
                "reason": "Success criteria are narrative and no thresholds were supplied.",
            },
            "model_comparisons": comparisons,
            "reproducibility_review": {
                "status": "configuration_verified",
                "source": self._artifact_reference(evidence["experiment_artifact"]),
                "random_seed": experiment_payload.get("reproducibility", {}).get("random_seed"),
                "split_policy": experiment_payload.get("split_policy"),
                "independent_reexecution": False,
            },
            "leakage_review": {
                "status": "inherited_from_m4_documentation",
                "statement": "M4 records preprocessing inside training partitions; exact partition assignments are not persisted for independent replay.",
            },
            "bias_checks": {
                "requested": policy.bias_checks,
                "status": "not_available",
                "reason": "M4 did not persist subgroup definitions or predictions required for these checks.",
            },
            "limitations": [
                limitation,
                "No business impact, effectiveness probability or deployment readiness is inferred.",
                "Formal acceptance remains subject to human review of the declared criteria.",
            ],
        }
        stored = artifact_store.put(canonical_json(report).encode("utf-8"))
        staged_storage_ids.append(stored.storage_id)
        parent_refs = [
            ArtifactReferenceInput(
                artifact_id=evidence["gold"].logical_id,
                artifact_version=evidence["gold"].artifact_version,
            ),
            ArtifactReferenceInput(
                artifact_id=evidence["experiment_artifact"].logical_id,
                artifact_version=evidence["experiment_artifact"].artifact_version,
            ),
        ]
        parent_ids = {(item.artifact_id, item.artifact_version) for item in parent_refs}
        for candidate in evidence["candidate_artifacts"]:
            key = (candidate.logical_id, candidate.artifact_version)
            if key not in parent_ids:
                parent_refs.append(
                    ArtifactReferenceInput(
                        artifact_id=candidate.logical_id,
                        artifact_version=candidate.artifact_version,
                    )
                )
                parent_ids.add(key)

        report_artifact = create_artifact(
            db,
            project_id,
            _artifact_create_payload(
                execution.id,
                stored,
                parent_refs,
                len(comparisons),
            ),
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
            correlation_id=payload.correlation_id,
            commit_transaction=False,
        )
        report_ref = self._artifact_reference(report_artifact)
        module_output = {
            "evaluation_report": report_ref,
            "model_comparisons": comparisons,
            "recommendation": {
                "status": "insufficient_evidence",
                "rationale": limitation,
                "evidence_level": "low",
            },
            "iteration_decision": {
                "required": True,
                "target_module": "m4",
                "hypothesis": "Persisting exact partition assignments will make independent M5 evaluation reproducible.",
                "objective": "Produce evaluation-ready M4 evidence without changing the declared model policy.",
                "success_signal": "A subsequent M5 run can independently replay the declared holdout, cross-validation or temporal partition.",
            },
            "decision_request": {
                "action": "record_insufficient_evidence",
                "requires_approval": True,
            },
        }
        return {
            "project_id": payload.project_id,
            "execution_id": payload.execution_id,
            "module_id": self.module_id,
            "contract_version": payload.contract_version,
            "context_snapshot_id": payload.context_snapshot_id,
            "correlation_id": payload.correlation_id,
            "status": "awaiting_approval",
            "artifacts": [report_ref],
            "approval_refs": evidence["approval_refs"],
            "warnings": payload.warnings,
            "errors": [],
            "next_actions": [
                {
                    "action": "record_insufficient_evidence",
                    "requires_approval": True,
                    "target_module": "m5",
                    "hypothesis": "M5 needs exact M4 partition evidence for independent evaluation.",
                }
            ],
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "module_output": module_output,
        }

    @staticmethod
    def _cleanup_staged_artifacts(
        artifact_store: ArtifactStore, storage_ids: list[str]
    ) -> None:
        for storage_id in storage_ids:
            try:
                artifact_store.delete(storage_id)
            except (ArtifactStoreError, OSError):
                # The failed execution remains auditable; an external store can
                # reconcile cleanup failures independently.
                pass
        storage_ids.clear()

    @staticmethod
    def _baseline_comparison(
        preliminary: dict[str, Any],
        baseline: dict[str, Any],
        problem_type: str | None,
        baseline_candidate_id: str | None,
    ) -> dict[str, Any]:
        if problem_type == "descriptive":
            return {
                "status": "not_applicable",
                "reason": "Descriptive profiles do not have a predictive baseline comparison.",
            }
        metric = preliminary.get("primary_metric")
        values = preliminary.get("metrics", {})
        baseline_values = baseline.get("metrics", {})
        if not isinstance(metric, str) or metric not in values or metric not in baseline_values:
            return {"status": "not_available", "reason": "A common primary metric was not recorded."}
        candidate_value = float(values[metric])
        baseline_value = float(baseline_values[metric])
        higher_is_better = problem_type == "classification"
        delta = candidate_value - baseline_value if higher_is_better else baseline_value - candidate_value
        return {
            "baseline_candidate_id": baseline_candidate_id,
            "metric": metric,
            "baseline_value": baseline_value,
            "candidate_value": candidate_value,
            "improvement_over_baseline": delta,
            "direction": "higher_is_better" if higher_is_better else "lower_is_better",
        }

    @staticmethod
    def _validate_measured_results(
        preliminary: dict[str, Any], problem_type: str | None, subject: str
    ) -> None:
        if preliminary.get("result_classification") != "measured":
            raise ValidationError(f"M5 requires measured preliminary results for {subject}")
        metric_rules: dict[str, tuple[str, Any]]
        if problem_type == "classification":
            metric_rules = {
                "accuracy": ("unit_interval", None),
                "f1_macro": ("unit_interval", None),
            }
            expected_primary = "f1_macro"
        elif problem_type == "regression":
            metric_rules = {
                "mae": ("non_negative", None),
                "rmse": ("non_negative", None),
                "r2": ("finite", None),
            }
            expected_primary = "rmse"
        elif problem_type == "descriptive":
            metric_rules = {
                "row_count": ("non_negative_integer", None),
                "column_count": ("non_negative_integer", None),
            }
            expected_primary = "row_count"
        else:
            raise ValidationError(f"Unsupported M4 problem type for {subject}")

        metrics = preliminary.get("metrics")
        if not isinstance(metrics, dict) or not metrics:
            raise ValidationError(f"M4 {subject} evidence has no measured metrics")
        unknown = sorted(set(metrics) - set(metric_rules))
        if unknown:
            raise ValidationError(
                f"M4 {subject} evidence contains undefined metrics: {', '.join(unknown)}"
            )
        for name, value in metrics.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValidationError(f"M4 metric {name} for {subject} is not numeric")
            if not math.isfinite(float(value)):
                raise ValidationError(f"M4 metric {name} for {subject} is not finite")
            rule = metric_rules[name][0]
            if rule == "unit_interval" and not 0 <= float(value) <= 1:
                raise ValidationError(f"M4 metric {name} for {subject} is outside [0, 1]")
            if rule == "non_negative" and float(value) < 0:
                raise ValidationError(f"M4 metric {name} for {subject} is negative")
            if rule == "non_negative_integer" and (
                float(value) < 0 or not float(value).is_integer()
            ):
                raise ValidationError(f"M4 metric {name} for {subject} is not a non-negative integer")

        if preliminary.get("primary_metric") != expected_primary:
            raise ValidationError(
                f"M4 primary metric for {subject} must be {expected_primary!r}"
            )
        metric_std = preliminary.get("metric_std", {})
        if not isinstance(metric_std, dict):
            raise ValidationError(f"M4 metric_std for {subject} is invalid")
        if set(metric_std) - set(metrics):
            raise ValidationError(f"M4 metric_std for {subject} contains unknown metrics")
        for name, value in metric_std.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValidationError(f"M4 metric_std {name} for {subject} is not numeric")
            if not math.isfinite(float(value)) or float(value) < 0:
                raise ValidationError(f"M4 metric_std {name} for {subject} is invalid")

    @staticmethod
    def _validate_problem_definition(problem_bytes: bytes, experiment: dict[str, Any]) -> None:
        try:
            document = json.loads(problem_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("M4 problem-definition artifact is not valid JSON") from exc
        if not isinstance(document, dict):
            raise ValidationError("M4 problem-definition artifact must contain a JSON object")
        definition = document.get("problem_definition", document)
        if not isinstance(definition, dict):
            raise ValidationError("M4 problem-definition payload is not an object")
        if definition.get("problem_type") != experiment.get("problem_type"):
            raise ValidationError("M4 problem definition and experiment problem types differ")
        declared_target = definition.get("target", definition.get("target_column"))
        if declared_target != experiment.get("target_column"):
            raise ValidationError("M4 problem definition and experiment targets differ")

    @staticmethod
    def _validate_experiment_configuration(
        experiment: dict[str, Any], module_output: dict[str, Any]
    ) -> None:
        problem_type = experiment.get("problem_type")
        policy = experiment.get("model_policy")
        if problem_type not in {"classification", "regression", "descriptive"}:
            raise ValidationError("M4 experiment has an unsupported problem type")
        if not isinstance(policy, dict) or not isinstance(policy.get("allowed_techniques"), list):
            raise ValidationError("M4 experiment model policy is incomplete")
        baseline = {
            "classification": "majority_class_baseline",
            "regression": "mean_baseline",
            "descriptive": "descriptive_statistics",
        }[problem_type]
        allowed = set(policy["allowed_techniques"]) | {baseline}
        candidates = module_output.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ValidationError("M4 experiment has no candidate evidence")
        for candidate in candidates:
            if not isinstance(candidate, dict) or candidate.get("technique") not in allowed:
                raise ValidationError("M4 candidate technique is inconsistent with its policy")

    @staticmethod
    def _limitations(entry: dict[str, Any], preliminary: dict[str, Any]) -> list[str]:
        values = list(entry.get("limitations", [])) + list(preliminary.get("limitations", []))
        values.append("M5 reused measured M4 evidence and did not retrain the candidate.")
        return list(dict.fromkeys(value for value in values if isinstance(value, str) and value))

    @staticmethod
    def _validate_artifact_reference(
        artifact: Artifact,
        reference: Any,
        *,
        expected_layer: str | None = None,
        expected_type: str | None = None,
    ) -> None:
        def value(name: str):
            return reference.get(name) if isinstance(reference, dict) else getattr(reference, name)

        if expected_type is not None and artifact.artifact_type != expected_type:
            raise ValidationError(f"M5 requires an artifact of type {expected_type}")
        if artifact.artifact_type != value("artifact_type"):
            raise ValidationError("Artifact reference type does not match the server record")
        if artifact.artifact_version != value("artifact_version"):
            raise ValidationError("Artifact reference version does not match the server record")
        if artifact.content_hash != value("content_hash"):
            raise ValidationError("Artifact reference content_hash does not match the server record")
        if artifact.version_number != value("version_number"):
            raise ValidationError("Artifact reference version_number does not match the server record")
        if value("version_id") is not None and artifact.id != value("version_id"):
            raise ValidationError("Artifact reference version_id does not match the server record")
        if expected_layer is not None and artifact.layer != expected_layer:
            raise ValidationError(f"M5 requires a {expected_layer} artifact")

    @staticmethod
    def _reference_matches(reference: Any, artifact: Artifact) -> bool:
        return (
            isinstance(reference, dict)
            and reference.get("artifact_id") == artifact.logical_id
            and reference.get("artifact_version") == artifact.artifact_version
            and reference.get("version_id") == artifact.id
            and reference.get("content_hash") == artifact.content_hash
        )

    @staticmethod
    def _same_reference(reference: Any, artifact: Artifact) -> bool:
        return (
            isinstance(reference, dict)
            and reference.get("artifact_id") == artifact.logical_id
            and reference.get("artifact_type") == artifact.artifact_type
            and reference.get("artifact_version") == artifact.artifact_version
            and reference.get("version_number") == artifact.version_number
            and reference.get("content_hash") == artifact.content_hash
            and (
                reference.get("version_id") is None
                or reference.get("version_id") == artifact.id
            )
        )

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
            action="execution.completed",
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
        payload: M5EvaluationRequest,
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
            metadata={"error": message[:1000]},
        )
        commit(db)


def _artifact_create_payload(
    execution_id: str,
    stored: Any,
    parent_refs: list[ArtifactReferenceInput],
    candidate_count: int,
):
    from .schemas import ArtifactCreate

    return ArtifactCreate(
        artifact_id=f"m5-evaluation-{sha256_canonical(execution_id)[7:23]}",
        artifact_type="evaluation.m5",
        artifact_version="v1",
        content_hash=stored.content_hash,
        storage_id=stored.storage_id,
        uri=stored.uri,
        media_type="application/json",
        layer="report",
        produced_by_module="m5",
        source_execution_id=execution_id,
        parent_artifact_refs=parent_refs,
        metadata={"candidate_count": candidate_count, "evidence_classification": "measured_preliminary"},
    )
