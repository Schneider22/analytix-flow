from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    Approval,
    Artifact,
    ArtifactLineage,
    AuditEvent,
    Decision,
    Execution,
    Project,
    ProjectContextSnapshot,
)
from app.db.session import build_engine
from app.m7_governance import M7GovernanceModule
from app.schemas import (
    ApprovalCreate,
    ArtifactCreate,
    ContextCreate,
    ContractArtifactReference,
    M7GovernanceRequest,
    M7ModuleInput,
    M7OperationalPolicy,
)
from app.services import (
    ConflictError,
    NotFoundError,
    ValidationError,
    create_approval,
    create_artifact,
    create_context_snapshot,
    create_project,
    record_audit,
)
from app.storage import LocalArtifactStore


def _schemas():
    contract_root = Path(__file__).parents[2] / "contracts"
    if not contract_root.is_dir():
        contract_root = Path(__file__).parents[1] / "contracts"
    schemas = {}
    for path in contract_root.rglob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        schemas[schema["$id"]] = schema
    registry = Registry().with_resources(
        (uri, Resource.from_contents(schema)) for uri, schema in schemas.items()
    )
    return schemas, registry


def _assert_m7_output_contract(result: dict) -> None:
    schemas, registry = _schemas()
    Draft202012Validator(
        schemas["https://analytixflow.local/contracts/m7/output.schema.json"],
        registry=registry,
    ).validate(result)


def _setup_session():
    engine = build_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine, Session(engine)


def _contract_ref(artifact: Artifact) -> ContractArtifactReference:
    return ContractArtifactReference(
        artifact_id=artifact.logical_id,
        artifact_type=artifact.artifact_type,
        artifact_version=artifact.artifact_version,
        version_number=artifact.version_number or 1,
        version_id=artifact.id,
        content_hash=artifact.content_hash,
        layer=artifact.layer,
        produced_by_module=artifact.produced_by_module,
    )


def _create_test_project_and_context(db: Session):
    project = Project(
        id=str(uuid4()),
        company_name="Acme Corp",
        company_description="Domain testing for M7",
        business_need="Governance and audit assurance",
        expected_objective="Audit trail and operational controls",
        business_rules=[],
        constraints=[],
        success_criteria=["Complete auditability"],
        status="active",
        current_phase="deployment",
    )
    db.add(project)
    db.commit()

    context = create_context_snapshot(
        db,
        project.id,
        ContextCreate(
            context={
                "company_name": "Acme Corp",
                "company_description": "Domain testing for M7",
                "business_need": "Governance and audit assurance",
                "expected_objective": "Audit trail and operational controls",
                "business_rules": [],
                "constraints": [],
                "assumptions": [],
                "success_criteria": ["Complete auditability"],
            },
            created_by="tester",
        ),
    )
    return project, context


def test_m7_executes_successfully_and_generates_verifiable_audit_artifact():
    engine, db = _setup_session()
    with TemporaryDirectory(prefix="test-m7-store-") as temp_dir:
        store = LocalArtifactStore(Path(temp_dir), max_bytes=1024 * 1024)
        try:
            project, context = _create_test_project_and_context(db)

            # Store a Bronze dataset artifact
            stored_bronze = store.put(b"col1,col2\n1,2\n3,4\n")
            bronze = create_artifact(
                db,
                project.id,
                ArtifactCreate(
                    artifact_id="dataset-bronze-01",
                    artifact_type="dataset.bronze",
                    artifact_version="v1",
                    content_hash=stored_bronze.content_hash,
                    storage_id=stored_bronze.storage_id,
                    media_type="text/csv",
                    layer="bronze",
                    produced_by_module="m2",
                ),
                store,
                max_metadata_bytes=262144,
            )

            # Add an execution for M2 with duration
            t0 = datetime(2026, 10, 24, 10, 0, 0, tzinfo=timezone.utc)
            t1 = datetime(2026, 10, 24, 10, 0, 15, tzinfo=timezone.utc)
            exec_m2 = Execution(
                id="exec-m2-test-01",
                project_id=project.id,
                module_id="m2",
                contract_version="v1.0",
                context_snapshot_id=context.id,
                status="succeeded",
                idempotency_key="key-m2-01",
                correlation_id="corr-m2-01",
                input_hash="sha256:" + "0" * 64,
                output_hash="sha256:" + "1" * 64,
                requested_at=t0,
                started_at=t0,
                completed_at=t1,
            )
            db.add(exec_m2)
            db.commit()

            # Record an audit event
            record_audit(
                db,
                project_id=project.id,
                action="dataset.ingested",
                entity_type="artifact",
                entity_id=bronze.id,
                module_id="m2",
            )
            db.commit()

            # Build M7 request
            req_payload = M7GovernanceRequest(
                project_id=project.id,
                execution_id="exec-m7-001",
                module_id="m7",
                contract_version="v1.0",
                context_snapshot_id=context.id,
                status="requested",
                correlation_id="corr-m7-001",
                idempotency_key="key-m7-001",
                requested_by="auditor-1",
                module_input=M7ModuleInput(
                    project_artifacts=[_contract_ref(bronze)],
                    execution_ids=[exec_m2.id],
                    operational_policy=M7OperationalPolicy(
                        audit_retention_required=True,
                        quality_checks=["schema_integrity"],
                        freshness_checks=["age_within_30d"],
                    ),
                ),
            )

            module = M7GovernanceModule()
            result = module.execute(db, project.id, req_payload, store, max_metadata_bytes=262144)

            assert result["status"] == "succeeded"
            _assert_m7_output_contract(result)

            # Check audit artifact
            audit_ref = result["module_output"]["audit_artifact"]
            assert audit_ref["artifact_type"] == "governance.audit"
            assert audit_ref["layer"] == "audit"
            assert audit_ref["produced_by_module"] == "m7"

            # Verify bytes in store
            audit_artifact_record = db.get(Artifact, audit_ref["version_id"])
            assert audit_artifact_record is not None
            stored_bytes = store.read(audit_artifact_record.storage_id, expected_hash=audit_ref["content_hash"])
            audit_data = json.loads(stored_bytes.decode("utf-8"))
            assert audit_data["format"] == "analytixflow.m7.governance-audit.v1"
            assert audit_data["project_id"] == project.id
            assert audit_data["summary"]["executions_count"] >= 2  # exec-m2 and exec-m7
            assert len(audit_data["audit_events"]) >= 1

            # Check lineage
            lineage = list(
                db.scalars(
                    select(ArtifactLineage).where(
                        ArtifactLineage.project_id == project.id,
                        ArtifactLineage.child_artifact_id == audit_ref["version_id"],
                    )
                )
            )
            assert any(l.parent_artifact_id == bronze.id for l in lineage)

        finally:
            db.close()
            engine.dispose()


def test_m7_evaluates_project_state_and_blocked_reasons():
    engine, db = _setup_session()
    with TemporaryDirectory(prefix="test-m7-store-") as temp_dir:
        store = LocalArtifactStore(Path(temp_dir), max_bytes=1024 * 1024)
        try:
            project, context = _create_test_project_and_context(db)

            # Create a pending approval
            approval = create_approval(
                db,
                project.id,
                ApprovalCreate(
                    action="select_alternative",
                    scope_type="project",
                    requested_by="reviewer-1",
                    reason="Model candidate evaluation review required",
                ),
            )

            # Create a failed execution for M4
            exec_m4 = Execution(
                id="exec-m4-fail-01",
                project_id=project.id,
                module_id="m4",
                contract_version="v1.0",
                context_snapshot_id=context.id,
                status="failed_terminal",
                error_summary="Hyperparameter search convergence failure",
                idempotency_key="key-m4-fail",
                correlation_id="corr-m4-fail",
                input_hash="sha256:" + "0" * 64,
                requested_at=datetime.now(timezone.utc),
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db.add(exec_m4)

            # Create an execution awaiting approval for M6
            exec_m6 = Execution(
                id="exec-m6-await-01",
                project_id=project.id,
                module_id="m6",
                contract_version="v1.0",
                context_snapshot_id=context.id,
                status="awaiting_approval",
                idempotency_key="key-m6-await",
                correlation_id="corr-m6-await",
                input_hash="sha256:" + "1" * 64,
                requested_at=datetime.now(timezone.utc),
                started_at=datetime.now(timezone.utc),
            )
            db.add(exec_m6)
            db.commit()

            req_payload = M7GovernanceRequest(
                project_id=project.id,
                execution_id="exec-m7-eval-01",
                module_id="m7",
                contract_version="v1.0",
                context_snapshot_id=context.id,
                status="requested",
                correlation_id="corr-m7-eval",
                idempotency_key="key-m7-eval",
                module_input=M7ModuleInput(
                    project_artifacts=[],
                    execution_ids=[],
                    operational_policy=M7OperationalPolicy(
                        audit_retention_required=True,
                        quality_checks=[],
                        freshness_checks=[],
                    ),
                ),
            )

            module = M7GovernanceModule()
            result = module.execute(db, project.id, req_payload, store, max_metadata_bytes=262144)
            _assert_m7_output_contract(result)

            state = result["module_output"]["project_state"]
            assert state["module_statuses"]["m4"] == "failed_terminal"
            assert state["module_statuses"]["m6"] == "awaiting_approval"
            assert state["module_statuses"]["m7"] == "succeeded"

            blocked = state["blocked_reasons"]
            assert any("Pending approval required" in b for b in blocked)
            assert any("Terminal failure in module 'm4'" in b for b in blocked)
            assert any("Module 'm6' execution 'exec-m6-await-01' is awaiting approval" in b for b in blocked)

        finally:
            db.close()
            engine.dispose()


def test_m7_operational_indicators_and_unmeasured_cost():
    engine, db = _setup_session()
    with TemporaryDirectory(prefix="test-m7-store-") as temp_dir:
        store = LocalArtifactStore(Path(temp_dir), max_bytes=1024 * 1024)
        try:
            project, context = _create_test_project_and_context(db)

            # Store a Bronze dataset
            stored = store.put(b"test data")
            bronze = create_artifact(
                db,
                project.id,
                ArtifactCreate(
                    artifact_id="bronze-data-test",
                    artifact_type="dataset.bronze",
                    artifact_version="v1",
                    content_hash=stored.content_hash,
                    storage_id=stored.storage_id,
                    layer="bronze",
                    produced_by_module="m2",
                ),
                store,
                max_metadata_bytes=262144,
            )

            # Succeeded execution with latency
            t0 = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
            t1 = datetime(2026, 10, 24, 12, 0, 5, tzinfo=timezone.utc)
            e1 = Execution(
                id="exec-e1",
                project_id=project.id,
                module_id="m2",
                contract_version="v1.0",
                context_snapshot_id=context.id,
                status="succeeded",
                idempotency_key="key-e1",
                correlation_id="corr-e1",
                input_hash="sha256:" + "0" * 64,
                requested_at=t0,
                started_at=t0,
                completed_at=t1,
            )
            db.add(e1)
            db.commit()

            req_payload = M7GovernanceRequest(
                project_id=project.id,
                execution_id="exec-m7-indicators",
                module_id="m7",
                contract_version="v1.0",
                context_snapshot_id=context.id,
                status="requested",
                correlation_id="corr-m7-ind",
                idempotency_key="key-m7-ind",
                module_input=M7ModuleInput(
                    project_artifacts=[],
                    execution_ids=[],
                    operational_policy=M7OperationalPolicy(
                        audit_retention_required=True,
                        quality_checks=[],
                        freshness_checks=[],
                    ),
                ),
            )

            module = M7GovernanceModule()
            result = module.execute(db, project.id, req_payload, store, max_metadata_bytes=262144)
            _assert_m7_output_contract(result)

            indicators = {ind["name"]: ind for ind in result["module_output"]["operational_indicators"]}

            # 1. Cost must NOT be labeled as measured $0.00
            cost_ind = indicators["operational_cloud_cost"]
            assert cost_ind["classification"] == "documentary_evidence"
            assert cost_ind["value_status"] == "not_applicable"
            assert "$0.00" not in cost_ind["value_status"]

            # 2. Latency is measured
            latency_ind = indicators["mean_module_latency_seconds"]
            assert latency_ind["classification"] == "measured"
            assert latency_ind["value_status"] == "5.00s"

            # 3. Success rate is measured
            rate_ind = indicators["execution_success_rate"]
            assert rate_ind["classification"] == "measured"
            assert rate_ind["value_status"] == "100.0%"

            # 4. Data freshness references Bronze
            freshness_ind = indicators["data_freshness_status"]
            assert freshness_ind["classification"] == "measured"
            assert "source_artifact" in freshness_ind
            assert freshness_ind["source_artifact"]["artifact_id"] == "bronze-data-test"

            # 5. Drift is documentary evidence
            drift_ind = indicators["model_drift_monitoring"]
            assert drift_ind["classification"] == "documentary_evidence"
            assert drift_ind["value_status"] == "deferred_to_production"

        finally:
            db.close()
            engine.dispose()


def test_m7_maintenance_plan_distinguishes_mvp_procedures_from_future_controls():
    engine, db = _setup_session()
    with TemporaryDirectory(prefix="test-m7-store-") as temp_dir:
        store = LocalArtifactStore(Path(temp_dir), max_bytes=1024 * 1024)
        try:
            project, context = _create_test_project_and_context(db)

            req_payload = M7GovernanceRequest(
                project_id=project.id,
                execution_id="exec-m7-mplan",
                module_id="m7",
                contract_version="v1.0",
                context_snapshot_id=context.id,
                status="requested",
                correlation_id="corr-m7-mplan",
                idempotency_key="key-m7-mplan",
                module_input=M7ModuleInput(
                    project_artifacts=[],
                    execution_ids=[],
                    operational_policy=M7OperationalPolicy(
                        audit_retention_required=True,
                        quality_checks=[],
                        freshness_checks=[],
                    ),
                ),
            )

            module = M7GovernanceModule()
            result = module.execute(db, project.id, req_payload, store, max_metadata_bytes=262144)
            _assert_m7_output_contract(result)

            plan = result["module_output"]["maintenance_plan"]
            assert len(plan["procedures"]) >= 2
            assert len(plan["future_controls"]) >= 2

            # Confirm rollback procedure is documented
            assert any("Rollback procedure" in p for p in plan["procedures"])
            # Confirm drift detection is listed under future controls
            assert any("concept drift and data drift" in fc for fc in plan["future_controls"])

        finally:
            db.close()
            engine.dispose()


def test_m7_idempotency_replay_and_conflict_handling():
    engine, db = _setup_session()
    with TemporaryDirectory(prefix="test-m7-store-") as temp_dir:
        store = LocalArtifactStore(Path(temp_dir), max_bytes=1024 * 1024)
        try:
            project, context = _create_test_project_and_context(db)

            req_payload = M7GovernanceRequest(
                project_id=project.id,
                execution_id="exec-m7-idem",
                module_id="m7",
                contract_version="v1.0",
                context_snapshot_id=context.id,
                status="requested",
                correlation_id="corr-m7-idem",
                idempotency_key="key-m7-idem",
                module_input=M7ModuleInput(
                    project_artifacts=[],
                    execution_ids=[],
                    operational_policy=M7OperationalPolicy(
                        audit_retention_required=True,
                        quality_checks=[],
                        freshness_checks=[],
                    ),
                ),
            )

            module = M7GovernanceModule()
            first_result = module.execute(db, project.id, req_payload, store, max_metadata_bytes=262144)
            assert first_result["status"] == "succeeded"

            # 1. Exact replay returns stored result
            second_result = module.execute(db, project.id, req_payload, store, max_metadata_bytes=262144)
            assert second_result == first_result

            # 2. Same key but changed input raises ConflictError
            altered_payload = req_payload.model_copy(deep=True)
            altered_payload.correlation_id = "corr-altered"
            with pytest.raises(ConflictError, match="idempotency key is already bound"):
                module.execute(db, project.id, altered_payload, store, max_metadata_bytes=262144)

            # 3. Same execution_id with different key raises ConflictError
            conflict_exec_id = req_payload.model_copy(deep=True)
            conflict_exec_id.idempotency_key = "different-key"
            with pytest.raises(ConflictError, match="execution_id is already in use"):
                module.execute(db, project.id, conflict_exec_id, store, max_metadata_bytes=262144)

        finally:
            db.close()
            engine.dispose()


def test_m7_rejects_cross_project_referenced_artifact():
    engine, db = _setup_session()
    with TemporaryDirectory(prefix="test-m7-store-") as temp_dir:
        store = LocalArtifactStore(Path(temp_dir), max_bytes=1024 * 1024)
        try:
            project_a, context_a = _create_test_project_and_context(db)
            project_b, context_b = _create_test_project_and_context(db)

            # Create artifact in project B
            stored = store.put(b"project B data")
            artifact_b = create_artifact(
                db,
                project_b.id,
                ArtifactCreate(
                    artifact_id="art-b",
                    artifact_type="dataset.bronze",
                    artifact_version="v1",
                    content_hash=stored.content_hash,
                    storage_id=stored.storage_id,
                    layer="bronze",
                    produced_by_module="m2",
                ),
                store,
                max_metadata_bytes=262144,
            )

            # Project A tries to reference Project B's artifact
            req_payload = M7GovernanceRequest(
                project_id=project_a.id,
                execution_id="exec-m7-cross-art",
                module_id="m7",
                contract_version="v1.0",
                context_snapshot_id=context_a.id,
                status="requested",
                correlation_id="corr-cross",
                idempotency_key="key-cross",
                module_input=M7ModuleInput(
                    project_artifacts=[_contract_ref(artifact_b)],
                    execution_ids=[],
                    operational_policy=M7OperationalPolicy(
                        audit_retention_required=True,
                        quality_checks=[],
                        freshness_checks=[],
                    ),
                ),
            )

            module = M7GovernanceModule()
            with pytest.raises(NotFoundError, match="not found for project"):
                module.execute(db, project_a.id, req_payload, store, max_metadata_bytes=262144)

            # Verify execution was recorded as failed_terminal
            failed_exec = db.get(Execution, "exec-m7-cross-art")
            assert failed_exec is not None
            assert failed_exec.status == "failed_terminal"

        finally:
            db.close()
            engine.dispose()


def test_m7_rejects_cross_project_referenced_execution():
    engine, db = _setup_session()
    with TemporaryDirectory(prefix="test-m7-store-") as temp_dir:
        store = LocalArtifactStore(Path(temp_dir), max_bytes=1024 * 1024)
        try:
            project_a, context_a = _create_test_project_and_context(db)
            project_b, context_b = _create_test_project_and_context(db)

            # Create execution in project B
            exec_b = Execution(
                id="exec-in-b",
                project_id=project_b.id,
                module_id="m2",
                contract_version="v1.0",
                context_snapshot_id=context_b.id,
                status="succeeded",
                idempotency_key="key-b",
                correlation_id="corr-b",
                input_hash="sha256:" + "0" * 64,
                requested_at=datetime.now(timezone.utc),
            )
            db.add(exec_b)
            db.commit()

            # Project A tries to reference Project B's execution
            req_payload = M7GovernanceRequest(
                project_id=project_a.id,
                execution_id="exec-m7-cross-exec",
                module_id="m7",
                contract_version="v1.0",
                context_snapshot_id=context_a.id,
                status="requested",
                correlation_id="corr-cross-exec",
                idempotency_key="key-cross-exec",
                module_input=M7ModuleInput(
                    project_artifacts=[],
                    execution_ids=[exec_b.id],
                    operational_policy=M7OperationalPolicy(
                        audit_retention_required=True,
                        quality_checks=[],
                        freshness_checks=[],
                    ),
                ),
            )

            module = M7GovernanceModule()
            with pytest.raises(NotFoundError, match="not found for project"):
                module.execute(db, project_a.id, req_payload, store, max_metadata_bytes=262144)

            failed_exec = db.get(Execution, "exec-m7-cross-exec")
            assert failed_exec is not None
            assert failed_exec.status == "failed_terminal"

        finally:
            db.close()
            engine.dispose()


def test_m7_handles_persistence_or_storage_failure():
    engine, db = _setup_session()
    with TemporaryDirectory(prefix="test-m7-store-") as temp_dir:
        # Create store with a tiny byte limit to induce ArtifactStoreError during audit persistence
        store = LocalArtifactStore(Path(temp_dir), max_bytes=10)
        try:
            project, context = _create_test_project_and_context(db)

            req_payload = M7GovernanceRequest(
                project_id=project.id,
                execution_id="exec-m7-store-fail",
                module_id="m7",
                contract_version="v1.0",
                context_snapshot_id=context.id,
                status="requested",
                correlation_id="corr-store-fail",
                idempotency_key="key-store-fail",
                module_input=M7ModuleInput(
                    project_artifacts=[],
                    execution_ids=[],
                    operational_policy=M7OperationalPolicy(
                        audit_retention_required=True,
                        quality_checks=[],
                        freshness_checks=[],
                    ),
                ),
            )

            module = M7GovernanceModule()
            with pytest.raises(ValidationError, match="Artifact storage failed"):
                module.execute(db, project.id, req_payload, store, max_metadata_bytes=262144)

            # Check that execution is marked failed_terminal and audit event is recorded
            exec_record = db.get(Execution, "exec-m7-store-fail")
            assert exec_record is not None
            assert exec_record.status == "failed_terminal"
            assert "Artifact storage failed" in (exec_record.error_summary or "")

        finally:
            db.close()
            engine.dispose()

