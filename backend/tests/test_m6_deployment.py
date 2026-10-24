from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tests.test_api import context_payload, project_payload
from tests.test_m4_modeling import _create_m4_inputs, _m4_request
from tests.test_m2_ingestion import _contract_ref


def _schemas():
    root = Path(__file__).parents[2] / "contracts"
    if not root.is_dir():
        root = Path(__file__).parents[1] / "contracts"
    schemas = {}
    for path in root.rglob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        schemas[schema["$id"]] = schema
    registry = Registry().with_resources(
        (uri, Resource.from_contents(schema)) for uri, schema in schemas.items()
    )
    return schemas, registry


def _assert_m6_output_contract(result: dict) -> None:
    schemas, registry = _schemas()
    Draft202012Validator(
        schemas["https://analytixflow.local/contracts/m6/output.schema.json"],
        registry=registry,
    ).validate(result)


def _create_m4_model(client, project, context):
    gold, problem = _create_m4_inputs(client, project)
    response = client.post(
        f"/api/v1/projects/{project['id']}/executions/m4",
        json=_m4_request(
            project,
            context,
            gold,
            problem,
            execution_id="m4-for-m6",
            key="m4-for-m6-key",
        ),
    )
    assert response.status_code == 200
    result = response.json()
    return next(
        item["pipeline_artifact"]
        for item in result["module_output"]["candidates"]
        if item["technique"] == "logistic_regression"
    )


def _approved_model(client, project, model):
    response = client.post(
        f"/api/v1/projects/{project['id']}/approvals",
        json={
            "action": "accept_model",
            "scope_type": "artifact",
            "artifact_id": model["artifact_id"],
            "artifact_version": model["artifact_version"],
            "requested_by": "m6-reviewer",
        },
    )
    assert response.status_code == 201
    pending = response.json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/approvals/{pending['id']}/resolve",
        json={"status": "approved", "resolved_by": "m6-approver"},
    )
    assert response.status_code == 200
    resolved = response.json()
    return {
        "approval_id": resolved["id"],
        "action": resolved["action"],
        "scope_type": resolved["scope_type"],
        "status": resolved["status"],
        "scope_hash": resolved["scope_hash"],
        "artifact_id": resolved["artifact_id"],
        "artifact_version": resolved["artifact_version"],
        "approved_by": resolved["resolved_by"],
        "approved_at": resolved["resolved_at"],
    }


def _m6_request(project, context, model, approval, *, execution_id="m6-1", key="m6-key"):
    return {
        "project_id": project["id"],
        "execution_id": execution_id,
        "module_id": "m6",
        "contract_version": "v1.0",
        "context_snapshot_id": context["id"],
        "status": "requested",
        "correlation_id": f"corr-{execution_id}",
        "idempotency_key": key,
        "requested_by": "m6-requester",
        "module_input": {
            "selected_model": _contract_ref(model),
            "deployment_target": {
                "target_type": "docker_artifact",
                "cloud_execution_allowed": False,
                "configuration": {"port": 8000, "password": "must-not-persist"},
            },
            "api_contract": {
                "operation": "predict",
                "request_schema": {"type": "object", "properties": {"amount": {"type": "number"}}},
                "response_schema": {"type": "object"},
            },
            "runtime_policy": {"network_access": "denied", "secret_access": "none"},
        },
        "approval_refs": [approval],
    }


def test_m6_generates_human_gated_package_and_project_scoped_consumption(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m6")
    ).json()
    model = _create_m4_model(client, project, context)
    approval = _approved_model(client, project, model)

    response = client.post(
        f"/api/v1/projects/{project['id']}/executions/m6",
        json=_m6_request(project, context, model, approval),
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "awaiting_approval"
    _assert_m6_output_contract(result)
    assert result["module_output"]["deployment_plan"]["cloud_execution_allowed"] is False
    assert result["module_output"]["deployment_plan"]["approval_request"]["action"] == (
        "approve_deployment_action"
    )
    assert any(item["status"] == "pending" for item in result["approval_refs"])

    package = result["module_output"]["package_artifacts"][0]
    package_response = client.get(
        f"/api/v1/projects/{project['id']}/artifacts/"
        f"{package['artifact_id']}/{package['artifact_version']}/content"
    )
    assert package_response.status_code == 200
    assert package_response.headers["X-Artifact-Content-Hash"] == package["content_hash"]
    package_payload = package_response.json()
    assert package_payload["model_binary_deserialized"] is False
    assert package_payload["cloud_resources_created"] is False

    config = result["module_output"]["deployment_plan"]["configuration_artifact"]
    config_response = client.get(
        f"/api/v1/projects/{project['id']}/artifacts/"
        f"{config['artifact_id']}/{config['artifact_version']}/content"
    )
    assert config_response.status_code == 200
    assert config_response.json()["deployment_target"]["configuration"]["password"] == "[REDACTED]"

    replay = client.post(
        f"/api/v1/projects/{project['id']}/executions/m6",
        json=_m6_request(project, context, model, approval),
    )
    assert replay.status_code == 200
    assert replay.json() == result

    cloud_plan = _m6_request(
        project,
        context,
        model,
        approval,
        execution_id="m6-cloud-plan",
        key="m6-cloud-plan-key",
    )
    cloud_plan["module_input"]["deployment_target"]["target_type"] = "cloud_plan_only"
    cloud_response = client.post(
        f"/api/v1/projects/{project['id']}/executions/m6", json=cloud_plan
    )
    assert cloud_response.status_code == 200
    cloud_result = cloud_response.json()
    _assert_m6_output_contract(cloud_result)
    assert cloud_result["module_output"]["deployment_plan"]["cost_status"] == "not_available"
    assert cloud_result["module_output"]["validation_report"]["status"] == "passed_with_warnings"


def test_m6_rejects_cross_project_selected_model(client):
    project_a = client.post("/api/v1/projects", json=project_payload()).json()
    context_a = client.post(
        f"/api/v1/projects/{project_a['id']}/context", json=context_payload("m6-a")
    ).json()
    model = _create_m4_model(client, project_a, context_a)
    approval = _approved_model(client, project_a, model)

    project_b = client.post("/api/v1/projects", json=project_payload()).json()
    context_b = client.post(
        f"/api/v1/projects/{project_b['id']}/context", json=context_payload("m6-b")
    ).json()
    request = _m6_request(project_b, context_b, model, approval, execution_id="m6-cross", key="m6-cross")
    response = client.post(f"/api/v1/projects/{project_b['id']}/executions/m6", json=request)
    assert response.status_code == 404


def test_m6_requires_exact_model_approval(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m6-no-approval")
    ).json()
    model = _create_m4_model(client, project, context)
    request = _m6_request(project, context, model, {"approval_id": "missing"})
    request["approval_refs"] = []
    response = client.post(f"/api/v1/projects/{project['id']}/executions/m6", json=request)
    assert response.status_code == 422
