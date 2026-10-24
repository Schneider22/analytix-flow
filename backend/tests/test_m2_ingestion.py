from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pandas as pd
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tests.test_api import context_payload, project_payload


def _contract_ref(source: dict) -> dict:
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
    return {key: source[key] for key in keys if source.get(key) is not None}


def _m2_request(project, context, source, *, execution_id: str, key: str, fmt: str):
    return {
        "project_id": project["id"],
        "execution_id": execution_id,
        "module_id": "m2",
        "contract_version": "v1.0",
        "context_snapshot_id": context["id"],
        "status": "requested",
        "correlation_id": f"corr-{execution_id}",
        "idempotency_key": key,
        "module_input": {
            "selected_alternative_id": "alternative-a",
            "source_artifacts": [_contract_ref(source)],
            "ingestion_options": [{"artifact_id": source["artifact_id"], "format": fmt}],
        },
    }


def _assert_m2_output_contract(result: dict) -> None:
    contract_root = Path(__file__).parents[2] / "contracts"
    schemas = {}
    for path in contract_root.rglob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        schemas[schema["$id"]] = schema
    registry = Registry().with_resources(
        (uri, Resource.from_contents(schema)) for uri, schema in schemas.items()
    )
    output_schema = schemas["https://analytixflow.local/contracts/m2/output.schema.json"]
    Draft202012Validator(output_schema, registry=registry).validate(result)


def test_m2_profiles_csv_preserves_source_and_is_idempotent(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m2")
    ).json()
    source_content = b"id,amount,created_at\n1,10,2026-01-01\n2,20,2026-01-02\n2,20,2026-01-02\n"
    uploaded = client.post(
        f"/api/v1/projects/{project['id']}/artifacts/content",
        params={
            "artifact_type": "source",
            "artifact_version": "v1",
            "artifact_id": "orders-source",
            "media_type": "text/csv",
            "layer": "source",
        },
        content=source_content,
    ).json()

    request = _m2_request(
        project,
        context,
        uploaded,
        execution_id="m2-execution-1",
        key="m2-key-1",
        fmt="csv",
    )
    first = client.post(f"/api/v1/projects/{project['id']}/executions/m2", json=request)
    assert first.status_code == 200
    result = first.json()
    _assert_m2_output_contract(result)
    assert result["status"] == "succeeded"
    assert result["module_output"]["profile_report"]["row_count"] == 3
    assert result["module_output"]["profile_report"]["column_count"] == 3
    assert result["module_output"]["source_manifest"][0]["preserved"] is True
    assert any(issue["severity"] == "warning" for issue in result["module_output"]["issues"])
    bronze = result["module_output"]["bronze_dataset"]
    assert bronze["layer"] == "bronze"

    replay = client.post(f"/api/v1/projects/{project['id']}/executions/m2", json=request)
    assert replay.status_code == 200
    assert replay.json() == result
    assert len(client.get(f"/api/v1/projects/{project['id']}/artifacts").json()) == 2


def test_m2_profiles_excel_sheet(client):
    project = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{project['id']}/context", json=context_payload("m2-excel")
    ).json()
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame({"customer_id": ["a", "b"], "value": [1, 2]}).to_excel(
            writer, sheet_name="Data", index=False
        )
    response = client.post(
        f"/api/v1/projects/{project['id']}/artifacts/content",
        params={
            "artifact_type": "source",
            "artifact_version": "v1",
            "artifact_id": "excel-source",
            "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "layer": "source",
        },
        content=buffer.getvalue(),
    )
    assert response.status_code == 201
    source = response.json()
    request = _m2_request(
        project,
        context,
        source,
        execution_id="m2-excel-execution",
        key="m2-excel-key",
        fmt="xlsx",
    )
    result = client.post(f"/api/v1/projects/{project['id']}/executions/m2", json=request)
    assert result.status_code == 200
    assert result.json()["module_output"]["profile_report"]["structures"] == ["sheet:Data"]
    assert "sheet:Data.customer_id" in result.json()["module_output"]["profile_report"]["potential_identifiers"]


def test_m2_rejects_wrong_context_project_scope(client):
    first = client.post("/api/v1/projects", json=project_payload()).json()
    second = client.post("/api/v1/projects", json=project_payload()).json()
    context = client.post(
        f"/api/v1/projects/{first['id']}/context", json=context_payload("wrong-scope")
    ).json()
    response = client.post(
        f"/api/v1/projects/{second['id']}/executions/m2",
        json={
            "project_id": second["id"],
            "execution_id": "m2-wrong-scope",
            "module_id": "m2",
            "contract_version": "v1.0",
            "context_snapshot_id": context["id"],
            "status": "requested",
            "correlation_id": "corr-wrong-scope",
            "idempotency_key": "key-wrong-scope",
            "module_input": {
                "selected_alternative_id": "alternative-a",
                "source_artifacts": [
                    {
                        "artifact_id": "missing-source",
                        "artifact_type": "source",
                        "artifact_version": "v1",
                        "version_number": 1,
                        "content_hash": "sha256:" + "0" * 64,
                    }
                ],
                "ingestion_options": [{"artifact_id": "missing-source", "format": "csv"}],
            },
        },
    )
    # A cross-project context is deliberately reported as not found so the
    # API does not disclose that the snapshot exists in another project.
    assert response.status_code == 404
