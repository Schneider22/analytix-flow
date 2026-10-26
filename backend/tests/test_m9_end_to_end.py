from __future__ import annotations

import json
from io import BytesIO
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select

from app.api import get_db
from app.db.models import Approval, Artifact, ArtifactLineage, AuditEvent, Decision, Execution, Project, ProjectContextSnapshot
from tests.test_api import context_payload, project_payload


def _contract_ref(artifact: dict) -> dict:
    """Format an API artifact payload into a valid ContractArtifactReference dictionary."""
    keys = (
        "artifact_id",
        "artifact_type",
        "artifact_version",
        "version_number",
        "version_id",
        "predecessor_version_id",
        "content_hash",
        "uri",
        "media_type",
        "layer",
        "produced_by_module",
        "created_at",
    )
    return {k: artifact[k] for k in keys if artifact.get(k) is not None}


def generate_synthetic_churn_csv(num_rows: int = 100, seed: int = 42) -> bytes:
    """Generate a deterministic synthetic customer churn dataset as specified in ADR-0012.

    Explicitly identified as synthetic test data; never portrayed as real commercial evidence.
    """
    rng = np.random.default_rng(seed)
    customer_ids = [f"CUST-{i:04d}" for i in range(1, num_rows + 1)]
    tenures = rng.integers(1, 73, size=num_rows)
    monthly = np.round(rng.uniform(18.50, 118.75, size=num_rows), 2)
    # Total charges roughly tenure * monthly with controlled variation
    total = np.round(tenures * monthly + rng.uniform(-5.0, 5.0, size=num_rows), 2)
    # Controlled missing values so M3's material transformation rule has real work to do
    total[5] = np.nan
    total[25] = np.nan

    contract_choices = ["month-to-month", "one-year", "two-year"]
    contracts = rng.choice(contract_choices, size=num_rows, p=[0.55, 0.25, 0.20])

    # Probability of churn conditioned on monthly charges and tenure
    logits = (monthly - 60.0) / 25.0 - (tenures - 30.0) / 15.0
    probs = 1.0 / (1.0 + np.exp(-logits))
    churn = (rng.uniform(0.0, 1.0, size=num_rows) < probs).astype(int)

    df = pd.DataFrame(
        {
            "customer_id": customer_ids,
            "tenure_months": tenures,
            "monthly_charges": monthly,
            "total_charges": total,
            "contract_type": contracts,
            "churn_label": churn,
        }
    )
    return df.to_csv(index=False).encode("utf-8")


def test_m9_full_analytical_lifecycle_end_to_end(client):
    """Execute the complete CRISP-DM analytical lifecycle through real M1–M8 endpoints.

    Verifies prerequisite gating, human approval resolution, immutable artifact persistence,
    multi-hop lineage, absence of fabricated metrics, and executive dashboard synthesis.
    """
    correlation_id = f"corr-m9-{uuid4().hex[:8]}"
    headers = {"X-Correlation-ID": correlation_id}

    # =========================================================================
    # Step 1: M1 — Project Initialization, Business Context, and Decision
    # =========================================================================
    project_resp = client.post(
        "/api/v1/projects",
        json={
            "company_name": "TelcoGlobal Synthetic Services",
            "company_description": "Synthetic enterprise provider for end-to-end integration validation.",
            "business_need": "Identify telecom subscribers at risk of churn to prioritize retention efforts.",
            "expected_objective": "Build a reproducible supervised classification pipeline with verified evidence.",
            "business_rules": [
                "Strictly isolate subscriber records within the project boundary.",
                "Enforce human approval before applying material transformations and deploying models.",
            ],
            "constraints": ["Local execution only; zero unapproved external network transmission."],
            "success_criteria": [
                "Achieve holdout F1-score >= 0.60 on synthetic validation partition.",
                "Ensure unbroken cryptographic lineage from source CSV to executive dashboard.",
            ],
            "owner_id": "test-architect",
        },
        headers=headers,
    )
    assert project_resp.status_code == 201
    project = project_resp.json()
    project_id = project["id"]
    assert project["company_name"] == "TelcoGlobal Synthetic Services"

    # Context Snapshot (v1)
    context_resp = client.post(
        f"/api/v1/projects/{project_id}/context",
        json=context_payload("m9-e2e-initial"),
        headers=headers,
    )
    assert context_resp.status_code == 201
    context = context_resp.json()
    context_snapshot_id = context["id"]
    assert context["version"] == 1

    # Foundational Decision (M1 Alternative Selection)
    decision_resp = client.post(
        f"/api/v1/projects/{project_id}/decisions",
        json={
            "decision_type": "select_alternative",
            "question": "Which analytical modeling strategy should be deployed for subscriber churn?",
            "options": [
                "supervised_tabular_classification",
                "heuristic_business_rule_engine",
                "unsupervised_anomaly_clustering",
            ],
            "selected_option": "supervised_tabular_classification",
            "rationale": "Supervised tabular classification produces measurable, optimizable metrics backed by ground truth.",
            "evidence_artifact_refs": [],
            "status": "decided",
            "decided_by": "lead_data_scientist",
        },
        headers=headers,
    )
    assert decision_resp.status_code == 201
    decision = decision_resp.json()
    assert decision["selected_option"] == "supervised_tabular_classification"

    # Human Approval for M1 Alternative
    approval_m1_resp = client.post(
        f"/api/v1/projects/{project_id}/approvals",
        json={
            "action": "select_alternative",
            "scope_type": "project",
            "requested_by": "lead_data_scientist",
        },
        headers=headers,
    )
    assert approval_m1_resp.status_code == 201
    app_m1 = approval_m1_resp.json()
    resolve_m1 = client.post(
        f"/api/v1/projects/{project_id}/approvals/{app_m1['id']}/resolve",
        json={"status": "approved", "resolved_by": "executive_sponsor"},
        headers=headers,
    )
    assert resolve_m1.status_code == 200
    assert resolve_m1.json()["status"] == "approved"

    # =========================================================================
    # Step 2: M2 — Data Registration and Bronze Ingestion
    # =========================================================================
    synthetic_csv = generate_synthetic_churn_csv(num_rows=100, seed=42)

    upload_resp = client.post(
        f"/api/v1/projects/{project_id}/artifacts/content",
        params={
            "artifact_type": "source",
            "artifact_version": "v1",
            "artifact_id": "synthetic-telco-churn-source",
            "media_type": "text/csv",
            "layer": "source",
            "produced_by_module": "m1",
        },
        content=synthetic_csv,
        headers=headers,
    )
    assert upload_resp.status_code == 201
    source_artifact = upload_resp.json()
    assert source_artifact["artifact_type"] == "source"
    assert source_artifact["content_hash"].startswith("sha256:")

    m2_execution_id = f"exec-m2-{uuid4().hex[:8]}"
    m2_req = {
        "project_id": project_id,
        "execution_id": m2_execution_id,
        "module_id": "m2",
        "contract_version": "v1.0",
        "context_snapshot_id": context_snapshot_id,
        "status": "requested",
        "correlation_id": correlation_id,
        "idempotency_key": f"key-{m2_execution_id}",
        "module_input": {
            "selected_alternative_id": "supervised_tabular_classification",
            "source_artifacts": [_contract_ref(source_artifact)],
            "ingestion_options": [{"artifact_id": source_artifact["artifact_id"], "format": "csv"}],
        },
    }
    m2_resp = client.post(f"/api/v1/projects/{project_id}/executions/m2", json=m2_req, headers=headers)
    assert m2_resp.status_code == 200
    m2_result = m2_resp.json()
    assert m2_result["status"] == "succeeded"
    bronze_dataset = m2_result["module_output"]["bronze_dataset"]
    profile_report = m2_result["module_output"]["profile_report"]
    assert bronze_dataset["layer"] == "bronze"
    assert profile_report["row_count"] == 100

    # =========================================================================
    # Step 3: M3 — Preparation, Quality Gate, and Silver/Gold Datasets
    # =========================================================================
    m3_execution_id = f"exec-m3-{uuid4().hex[:8]}"
    m3_req = {
        "project_id": project_id,
        "execution_id": m3_execution_id,
        "module_id": "m3",
        "contract_version": "v1.1",
        "context_snapshot_id": context_snapshot_id,
        "status": "requested",
        "correlation_id": correlation_id,
        "idempotency_key": f"key-{m3_execution_id}",
        "module_input": {
            "bronze_artifacts": [_contract_ref(bronze_dataset)],
            "transformation_plan": {
                "rules": [
                    {
                        "rule_id": "norm-cols",
                        "action": "normalize_column_names",
                        "reason": "Standardize column identifiers to snake_case.",
                        "approval_required": False,
                        "parameters": {},
                    },
                    {
                        "rule_id": "fill-charges",
                        "action": "fill_missing_values",
                        "reason": "Impute missing total_charges with constant 0 to preserve record count.",
                        "approval_required": True,
                        "parameters": {"strategy": "zero", "columns": ["total_charges"]},
                    },
                    {
                        "rule_id": "drop-dupes",
                        "action": "drop_duplicate_rows",
                        "reason": "Prevent repeated subscriber records from skewing training.",
                        "approval_required": False,
                        "parameters": {},
                    },
                ]
            },
            "business_rules": ["Zero data loss on active subscribers."],
            "quality_policy": {
                "required_checks": ["non_empty_dataset", "columns_present", "no_missing_values"],
                "blocking_conditions": ["non_empty_dataset", "columns_present"],
            },
        },
        "approval_refs": [],
    }

    # First attempt: material transformations require human approval
    m3_pending = client.post(f"/api/v1/projects/{project_id}/executions/m3", json=m3_req, headers=headers)
    assert m3_pending.status_code == 200
    m3_pending_res = m3_pending.json()
    assert m3_pending_res["status"] == "awaiting_approval"
    assert m3_pending_res["module_output"]["approval_request"]["action"] == "approve_transformations"

    # Human Gate 1: Approve M3 Material Transformations
    app_m3_resp = client.post(
        f"/api/v1/projects/{project_id}/approvals",
        json={
            "action": "approve_transformations",
            "scope_type": "artifact",
            "artifact_id": bronze_dataset["artifact_id"],
            "artifact_version": bronze_dataset["artifact_version"],
            "requested_by": "m3-data-engineer",
        },
        headers=headers,
    )
    assert app_m3_resp.status_code == 201
    app_m3 = app_m3_resp.json()
    res_m3 = client.post(
        f"/api/v1/projects/{project_id}/approvals/{app_m3['id']}/resolve",
        json={"status": "approved", "resolved_by": "qa-lead"},
        headers=headers,
    )
    assert res_m3.status_code == 200
    resolved_m3_app = res_m3.json()

    # Re-run M3 with resolved approval attached
    m3_req["approval_refs"] = [
        {
            "approval_id": resolved_m3_app["id"],
            "action": resolved_m3_app["action"],
            "scope_type": resolved_m3_app["scope_type"],
            "status": resolved_m3_app["status"],
            "scope_hash": resolved_m3_app["scope_hash"],
            "artifact_id": bronze_dataset["artifact_id"],
            "artifact_version": bronze_dataset["artifact_version"],
            "approved_by": resolved_m3_app["resolved_by"],
            "approved_at": resolved_m3_app["resolved_at"],
        }
    ]
    m3_resp = client.post(f"/api/v1/projects/{project_id}/executions/m3", json=m3_req, headers=headers)
    assert m3_resp.status_code == 200
    m3_result = m3_resp.json()
    assert m3_result["status"] == "succeeded"
    silver_dataset = m3_result["module_output"]["silver_dataset"]
    gold_dataset = m3_result["module_output"]["gold_dataset"]
    quality_report = m3_result["module_output"]["quality_report"]
    assert silver_dataset["layer"] == "silver"
    assert gold_dataset["layer"] == "gold"
    assert quality_report["status"] in ["passed", "passed_with_warnings"]

    # =========================================================================
    # Step 4: M4 — Modeling Experiments and Candidate Generation
    # =========================================================================
    problem_def_resp = client.post(
        f"/api/v1/projects/{project_id}/artifacts/content",
        params={
            "artifact_type": "problem.definition",
            "artifact_version": "v1",
            "artifact_id": "churn-problem-def",
            "media_type": "application/json",
            "layer": "other",
            "produced_by_module": "m1",
        },
        content=json.dumps({"problem_type": "classification", "target": "churn_label"}).encode("utf-8"),
        headers=headers,
    )
    assert problem_def_resp.status_code == 201
    problem_def_artifact = problem_def_resp.json()

    m4_execution_id = f"exec-m4-{uuid4().hex[:8]}"
    m4_req = {
        "project_id": project_id,
        "execution_id": m4_execution_id,
        "module_id": "m4",
        "contract_version": "v1.0",
        "context_snapshot_id": context_snapshot_id,
        "status": "requested",
        "correlation_id": correlation_id,
        "idempotency_key": f"key-{m4_execution_id}",
        "module_input": {
            "gold_dataset": _contract_ref(gold_dataset),
            "problem_definition": _contract_ref(problem_def_artifact),
            "target_column": "churn_label",
            "model_policy": {
                "problem_type": "classification",
                "allowed_techniques": ["logistic_regression", "decision_tree_classifier"],
                "interpretability_constraints": ["prefer_interpretable_models"],
            },
            "split_policy": {
                "strategy": "holdout",
                "test_fraction": 0.25,
            },
            "reproducibility": {"random_seed": 42, "record_environment": True},
        },
    }
    m4_resp = client.post(f"/api/v1/projects/{project_id}/executions/m4", json=m4_req, headers=headers)
    assert m4_resp.status_code == 200
    m4_result = m4_resp.json()
    assert m4_result["status"] == "succeeded"

    candidates = m4_result["module_output"]["candidates"]
    assert len(candidates) == 3  # majority_class_baseline, logistic_regression, decision_tree_classifier
    assert m4_result["next_actions"] == [
        {
            "action": "select_model_candidate",
            "requires_approval": True,
            "target_module": "m5",
        }
    ]

    # Select Logistic Regression as the candidate to advance
    lr_candidate = next(item for item in candidates if item["technique"] == "logistic_regression")
    pipeline_artifact = lr_candidate["pipeline_artifact"]
    assert pipeline_artifact["layer"] == "model"
    assert lr_candidate["preliminary_results"]["result_classification"] == "measured"

    # =========================================================================
    # Step 5: Human Gate 2 (Candidate Selection for M5)
    # =========================================================================
    app_m4_resp = client.post(
        f"/api/v1/projects/{project_id}/approvals",
        json={
            "action": "select_model_candidate",
            "scope_type": "artifact",
            "artifact_id": pipeline_artifact["artifact_id"],
            "artifact_version": pipeline_artifact["artifact_version"],
            "requested_by": "lead_ml_engineer",
        },
        headers=headers,
    )
    assert app_m4_resp.status_code == 201
    app_m4 = app_m4_resp.json()
    res_m4 = client.post(
        f"/api/v1/projects/{project_id}/approvals/{app_m4['id']}/resolve",
        json={"status": "approved", "resolved_by": "head_of_analytics"},
        headers=headers,
    )
    assert res_m4.status_code == 200
    resolved_m4_app = res_m4.json()

    # =========================================================================
    # Step 6: M5 — Empirical Evaluation and Validation Gating
    # =========================================================================
    m5_execution_id = f"exec-m5-{uuid4().hex[:8]}"
    m5_req = {
        "project_id": project_id,
        "execution_id": m5_execution_id,
        "module_id": "m5",
        "contract_version": "v1.0",
        "context_snapshot_id": context_snapshot_id,
        "status": "requested",
        "correlation_id": correlation_id,
        "idempotency_key": f"key-{m5_execution_id}",
        "module_input": {
            "candidate_models": [_contract_ref(pipeline_artifact)],
            "gold_dataset": _contract_ref(gold_dataset),
            "baseline": {
                "description": "Baseline majority-class classifier from M4.",
                "artifact_or_method": "majority_class_baseline",
            },
            "evaluation_policy": {
                "primary_metrics": ["f1_macro"],
                "secondary_metrics": ["accuracy"],
                "validation_strategy": "holdout",
                "bias_checks": ["review_contract_type_subgroups"],
            },
            "success_criteria": ["Holdout macro F1 must be measured and reviewed by governance."],
        },
        "approval_refs": [
            {
                "approval_id": resolved_m4_app["id"],
                "action": resolved_m4_app["action"],
                "scope_type": resolved_m4_app["scope_type"],
                "status": resolved_m4_app["status"],
                "scope_hash": resolved_m4_app["scope_hash"],
                "artifact_id": pipeline_artifact["artifact_id"],
                "artifact_version": pipeline_artifact["artifact_version"],
                "approved_by": resolved_m4_app["resolved_by"],
                "approved_at": resolved_m4_app["resolved_at"],
            }
        ],
    }
    m5_resp = client.post(f"/api/v1/projects/{project_id}/executions/m5", json=m5_req, headers=headers)
    assert m5_resp.status_code == 200
    m5_result = m5_resp.json()
    assert m5_result["status"] == "awaiting_approval"
    evaluation_report = m5_result["module_output"]["evaluation_report"]
    assert evaluation_report["layer"] == "report"
    assert m5_result["module_output"]["model_comparisons"][0]["metrics"]["result_classification"] == "measured"

    # =========================================================================
    # Step 7: Human Gate 3 (Model Approval for Deployment)
    # =========================================================================
    app_m5_resp = client.post(
        f"/api/v1/projects/{project_id}/approvals",
        json={
            "action": "accept_model",
            "scope_type": "artifact",
            "artifact_id": pipeline_artifact["artifact_id"],
            "artifact_version": pipeline_artifact["artifact_version"],
            "requested_by": "qa_evaluator",
        },
        headers=headers,
    )
    assert app_m5_resp.status_code == 201
    app_m5 = app_m5_resp.json()
    res_m5 = client.post(
        f"/api/v1/projects/{project_id}/approvals/{app_m5['id']}/resolve",
        json={"status": "approved", "resolved_by": "business_operations_manager"},
        headers=headers,
    )
    assert res_m5.status_code == 200
    resolved_m5_app = res_m5.json()

    # =========================================================================
    # Step 8: M6 — Local Deployment Packaging and Plan
    # =========================================================================
    m6_execution_id = f"exec-m6-{uuid4().hex[:8]}"
    m6_req = {
        "project_id": project_id,
        "execution_id": m6_execution_id,
        "module_id": "m6",
        "contract_version": "v1.0",
        "context_snapshot_id": context_snapshot_id,
        "status": "requested",
        "correlation_id": correlation_id,
        "idempotency_key": f"key-{m6_execution_id}",
        "requested_by": "deployment_engineer",
        "module_input": {
            "selected_model": _contract_ref(pipeline_artifact),
            "deployment_target": {
                "target_type": "docker_artifact",
                "cloud_execution_allowed": False,
                "configuration": {"port": 8080, "workers": 2},
            },
            "api_contract": {
                "operation": "predict_churn",
                "request_schema": {
                    "type": "object",
                    "properties": {
                        "tenure_months": {"type": "integer"},
                        "monthly_charges": {"type": "number"},
                        "total_charges": {"type": "number"},
                        "contract_type": {"type": "string"},
                    },
                    "required": ["tenure_months", "monthly_charges", "total_charges", "contract_type"],
                },
                "response_schema": {
                    "type": "object",
                    "properties": {"churn_prediction": {"type": "integer"}, "risk_score": {"type": "number"}},
                },
            },
            "runtime_policy": {"network_access": "denied", "secret_access": "none"},
        },
        "approval_refs": [
            {
                "approval_id": resolved_m5_app["id"],
                "action": resolved_m5_app["action"],
                "scope_type": resolved_m5_app["scope_type"],
                "status": resolved_m5_app["status"],
                "scope_hash": resolved_m5_app["scope_hash"],
                "artifact_id": resolved_m5_app["artifact_id"],
                "artifact_version": resolved_m5_app["artifact_version"],
                "approved_by": resolved_m5_app["resolved_by"],
                "approved_at": resolved_m5_app["resolved_at"],
            }
        ],
    }
    m6_resp = client.post(f"/api/v1/projects/{project_id}/executions/m6", json=m6_req, headers=headers)
    assert m6_resp.status_code == 200
    m6_result = m6_resp.json()
    assert m6_result["status"] == "awaiting_approval"
    deployment_package = m6_result["module_output"]["package_artifacts"][0]
    deployment_plan_config = m6_result["module_output"]["deployment_plan"]["configuration_artifact"]
    assert deployment_package["layer"] == "deployment"
    assert deployment_plan_config["layer"] == "deployment"

    # =========================================================================
    # Step 9: M7 — Continuous Governance, Audit, and Operational State
    # =========================================================================
    m7_execution_id = f"exec-m7-{uuid4().hex[:8]}"
    project_artifacts_for_m7 = [
        source_artifact,
        bronze_dataset,
        silver_dataset,
        gold_dataset,
        pipeline_artifact,
        evaluation_report,
        deployment_package,
    ]
    execution_ids_for_m7 = [
        m2_execution_id,
        m3_execution_id,
        m4_execution_id,
        m5_execution_id,
        m6_execution_id,
    ]
    m7_req = {
        "project_id": project_id,
        "execution_id": m7_execution_id,
        "module_id": "m7",
        "contract_version": "v1.0",
        "context_snapshot_id": context_snapshot_id,
        "status": "requested",
        "correlation_id": correlation_id,
        "idempotency_key": f"key-{m7_execution_id}",
        "requested_by": "chief_compliance_officer",
        "module_input": {
            "project_artifacts": [_contract_ref(a) for a in project_artifacts_for_m7],
            "execution_ids": execution_ids_for_m7,
            "operational_policy": {
                "audit_retention_required": True,
                "quality_checks": ["schema_validation", "null_check", "hash_verification"],
                "freshness_checks": ["max_age_30d"],
            },
        },
    }
    m7_resp = client.post(f"/api/v1/projects/{project_id}/executions/m7", json=m7_req, headers=headers)
    assert m7_resp.status_code == 200
    m7_result = m7_resp.json()
    assert m7_result["status"] == "succeeded"
    governance_audit = m7_result["module_output"]["audit_artifact"]
    assert governance_audit["layer"] == "audit"
    assert m7_result["module_output"]["project_state"]["module_statuses"]["m1"] in ["ready", "succeeded"]
    assert m7_result["module_output"]["project_state"]["module_statuses"]["m2"] == "succeeded"
    assert m7_result["module_output"]["project_state"]["module_statuses"]["m3"] == "succeeded"
    assert m7_result["module_output"]["project_state"]["module_statuses"]["m4"] == "succeeded"

    # =========================================================================
    # Step 10: M8 — Executive Dashboard and Evidence Consolidation
    # =========================================================================
    m8_execution_id = f"exec-m8-{uuid4().hex[:8]}"
    m8_req = {
        "project_id": project_id,
        "execution_id": m8_execution_id,
        "module_id": "m8",
        "contract_version": "v1.0",
        "context_snapshot_id": context_snapshot_id,
        "correlation_id": correlation_id,
        "idempotency_key": f"key-{m8_execution_id}",
        "status": "requested",
        "requested_by": "chief_analytics_officer",
        "module_input": {
            "context_artifacts": [
                _contract_ref(source_artifact),
                _contract_ref(problem_def_artifact),
            ],
            "result_artifacts": [
                _contract_ref(bronze_dataset),
                _contract_ref(silver_dataset),
                _contract_ref(gold_dataset),
                _contract_ref(pipeline_artifact),
                _contract_ref(evaluation_report),
                _contract_ref(deployment_package),
                _contract_ref(governance_audit),
            ],
            "claim_policy": {
                "required_classification": True,
                "require_source_reference": True,
                "allow_hypotheses": False,
            },
        },
    }

    # POST to generate dashboard
    m8_resp = client.post(f"/api/v1/projects/{project_id}/dashboard", json=m8_req, headers=headers)
    assert m8_resp.status_code == 200
    m8_result = m8_resp.json()
    assert m8_result["status"] == "succeeded"

    dashboard_artifact = m8_result["module_output"]["dashboard_artifact"]
    assert dashboard_artifact["artifact_type"] == "dashboard.report"
    assert dashboard_artifact["layer"] == "report"

    # GET to retrieve latest dashboard
    get_dash_resp = client.get(f"/api/v1/projects/{project_id}/dashboard", headers=headers)
    assert get_dash_resp.status_code == 200
    retrieved_dash = get_dash_resp.json()
    assert retrieved_dash["execution_id"] == m8_execution_id
    assert retrieved_dash["output_hash"] == m8_result["output_hash"]

    # =========================================================================
    # Step 11: Comprehensive Transversal Validations
    # =========================================================================
    # 1. Six executive sections strictly enforced
    sections = m8_result["module_output"]["sections"]
    section_ids = [s["section_id"] for s in sections]
    assert section_ids == [
        "business_diagnosis",
        "data_quality",
        "analytical_strategy",
        "evaluation_results",
        "impact_and_costs",
        "roadmap",
    ]

    # 2. Epistemic claim classification (Golden Rule of Evidence)
    valid_classifications = {"measured", "estimated", "hypothesis", "documentary_evidence"}
    for section in sections:
        assert len(section["claims"]) >= 1
        for cl in section["claims"]:
            assert cl["classification"] in valid_classifications
            # Since allow_hypotheses is False, no claims should be classified as hypothesis
            assert cl["classification"] != "hypothesis"
            assert len(cl["source_artifacts"]) >= 1

    # 3. Machine-actionable roadmap
    roadmap = m8_result["module_output"]["roadmap"]
    assert len(roadmap) >= 1
    assert all("item" in r and "dependencies" in r and "success_signal" in r for r in roadmap)

    # 4. Multi-hop Relational Lineage Verification in Database
    app = client.app
    with app.state.session_factory() as session:
        # Check that dashboard.report has recorded parents in artifact_lineage
        dashboard_db = session.scalars(
            select(Artifact).where(
                Artifact.project_id == project_id,
                Artifact.artifact_type == "dashboard.report",
            )
        ).first()
        assert dashboard_db is not None
        assert dashboard_db.produced_by_module == "m8"

        lineage_parents = session.scalars(
            select(ArtifactLineage).where(ArtifactLineage.child_artifact_id == dashboard_db.id)
        ).all()
        # M8 synthesized from 9 artifacts (2 context + 7 result)
        assert len(lineage_parents) == 9

        # Verify Gold descends from Silver, Silver descends from Bronze, Bronze descends from Source
        gold_db = session.scalars(
            select(Artifact).where(Artifact.id == gold_dataset["version_id"])
        ).one()
        assert silver_dataset["artifact_id"] in gold_db.parent_artifact_ids

        silver_db = session.scalars(
            select(Artifact).where(Artifact.id == silver_dataset["version_id"])
        ).one()
        assert bronze_dataset["artifact_id"] in silver_db.parent_artifact_ids

        bronze_db = session.scalars(
            select(Artifact).where(Artifact.id == bronze_dataset["version_id"])
        ).one()
        assert source_artifact["artifact_id"] in bronze_db.parent_artifact_ids

        # 5. Audit Log Trail Verification
        audit_records = session.scalars(
            select(AuditEvent).where(AuditEvent.project_id == project_id)
        ).all()
        actions = {event.action for event in audit_records}
        assert "execution.started" in actions
        assert "execution.succeeded" in actions
        assert "artifact.created" in actions


def test_m9_multiproject_isolation_and_security(client):
    """Verify that project isolation strictly prevents cross-project artifact leakage."""
    # Project 1: Primary
    proj1 = client.post("/api/v1/projects", json=project_payload()).json()
    ctx1 = client.post(f"/api/v1/projects/{proj1['id']}/context", json=context_payload("p1")).json()

    # Upload source in Project 1
    source1 = client.post(
        f"/api/v1/projects/{proj1['id']}/artifacts/content",
        params={
            "artifact_type": "source",
            "artifact_version": "v1",
            "artifact_id": "proj1-source",
            "media_type": "text/csv",
            "layer": "source",
        },
        content=b"col_a,col_b\n1,2\n3,4\n",
    ).json()

    # Project 2: Alien
    proj2 = client.post(
        "/api/v1/projects",
        json={**project_payload(), "company_name": "Alien Intruder Corp"},
    ).json()
    ctx2 = client.post(f"/api/v1/projects/{proj2['id']}/context", json=context_payload("p2")).json()

    # Project 2 tries to run M2 referencing Project 1's source artifact
    alien_m2 = client.post(
        f"/api/v1/projects/{proj2['id']}/executions/m2",
        json={
            "project_id": proj2["id"],
            "execution_id": "exec-alien-m2",
            "module_id": "m2",
            "contract_version": "v1.0",
            "context_snapshot_id": ctx2["id"],
            "status": "requested",
            "correlation_id": "corr-alien-1",
            "idempotency_key": "key-alien-1",
            "module_input": {
                "selected_alternative_id": "alt-a",
                "source_artifacts": [_contract_ref(source1)],  # Cross-project reference!
                "ingestion_options": [{"artifact_id": source1["artifact_id"], "format": "csv"}],
            },
        },
    )
    # Must be rejected because source1 does not belong to proj2
    assert alien_m2.status_code in {400, 404, 422}

    # Project 2 tries to query dashboard of Project 1
    alien_dash = client.get(f"/api/v1/projects/{proj2['id']}/dashboard")
    assert alien_dash.status_code == 404
