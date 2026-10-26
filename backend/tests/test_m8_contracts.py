from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from referencing import Registry, Resource

from app.schemas import (
    ClaimPolicy,
    ContractArtifactReference,
    ContractCitation,
    DashboardClaim,
    DashboardRoadmapItem,
    DashboardSection,
    M8ClaimPolicy,
    M8DashboardClaim,
    M8DashboardInput,
    M8DashboardOutput,
    M8DashboardRequest,
    M8DashboardResult,
    M8DashboardSection,
    M8ModuleInput,
    M8ModuleOutput,
    M8NextAction,
    M8RoadmapItem,
)


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


def _sample_artifact_ref(
    artifact_id: str = "art-1",
    artifact_type: str = "report",
    version: str = "v1",
    version_number: int = 1,
    layer: str = "report",
    produced_by: str = "m8",
) -> ContractArtifactReference:
    return ContractArtifactReference(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        artifact_version=version,
        version_number=version_number,
        version_id="ver-1",
        content_hash="sha256:" + "a" * 64,
        layer=layer,
        produced_by_module=produced_by,
    )


def _sample_citation(
    citation_id: str = "cite-1",
    source_id: str = "adr-0010",
    locator: str = "section-governance",
    evidence_type: str = "standard",
) -> ContractCitation:
    return ContractCitation(
        citation_id=citation_id,
        source_id=source_id,
        locator=locator,
        evidence_type=evidence_type,
        retrieved_at=datetime.now(timezone.utc),
        limitations=["Applicable to local MVP environment"],
    )


def test_m8_claim_policy_validation():
    # Valid default policy
    policy = ClaimPolicy()
    assert policy.required_classification is True
    assert policy.require_source_reference is True
    assert policy.allow_hypotheses is None

    # Valid explicit hypotheses settings
    p_false = ClaimPolicy(allow_hypotheses=False)
    assert p_false.allow_hypotheses is False
    p_true = ClaimPolicy(allow_hypotheses=True)
    assert p_true.allow_hypotheses is True

    # Alias check
    assert M8ClaimPolicy is ClaimPolicy

    # Invalid: required_classification must be True
    with pytest.raises(ValidationError):
        ClaimPolicy.model_validate({"required_classification": False, "require_source_reference": True})

    # Invalid: require_source_reference must be True
    with pytest.raises(ValidationError):
        ClaimPolicy.model_validate({"required_classification": True, "require_source_reference": False})

    # Invalid: allow_hypotheses must be boolean
    with pytest.raises(ValidationError):
        ClaimPolicy.model_validate({
            "required_classification": True,
            "require_source_reference": True,
            "allow_hypotheses": "yes",
        })

    # Invalid: extra properties forbidden
    with pytest.raises(ValidationError):
        ClaimPolicy.model_validate({
            "required_classification": True,
            "require_source_reference": True,
            "unknown_policy": 123,
        })


def test_m8_module_input_validation():
    art = _sample_artifact_ref()
    policy = ClaimPolicy(allow_hypotheses=False)

    valid_input = M8ModuleInput(
        context_artifacts=[art],
        result_artifacts=[art],
        claim_policy=policy,
    )
    assert len(valid_input.context_artifacts) == 1
    assert len(valid_input.result_artifacts) == 1
    assert valid_input.claim_policy.allow_hypotheses is False

    # Missing context_artifacts raises ValidationError
    with pytest.raises(ValidationError):
        M8ModuleInput.model_validate({
            "result_artifacts": [art.model_dump(mode="json")],
            "claim_policy": policy.model_dump(mode="json"),
        })

    # Missing result_artifacts raises ValidationError
    with pytest.raises(ValidationError):
        M8ModuleInput.model_validate({
            "context_artifacts": [art.model_dump(mode="json")],
            "claim_policy": policy.model_dump(mode="json"),
        })

    # Missing claim_policy raises ValidationError
    with pytest.raises(ValidationError):
        M8ModuleInput.model_validate({
            "context_artifacts": [art.model_dump(mode="json")],
            "result_artifacts": [art.model_dump(mode="json")],
        })

    # Extra property forbidden
    with pytest.raises(ValidationError):
        M8ModuleInput.model_validate({
            "context_artifacts": [art.model_dump(mode="json")],
            "result_artifacts": [art.model_dump(mode="json")],
            "claim_policy": policy.model_dump(mode="json"),
            "extra_field": "disallowed",
        })


def test_contract_citation_validation():
    for etype in [
        "technical_documentation",
        "research",
        "standard",
        "project_artifact",
        "experience_record",
        "hypothesis",
    ]:
        cite = _sample_citation(evidence_type=etype)
        assert cite.evidence_type == etype

    # Invalid evidence type
    with pytest.raises(ValidationError):
        ContractCitation(
            citation_id="cite-bad",
            source_id="src",
            locator="loc",
            evidence_type="invalid_type",
        )

    # Empty citation_id forbidden
    with pytest.raises(ValidationError):
        ContractCitation(
            citation_id="",
            source_id="src",
            locator="loc",
            evidence_type="standard",
        )

    # Extra field forbidden
    with pytest.raises(ValidationError):
        ContractCitation(
            citation_id="cite-1",
            source_id="src",
            locator="loc",
            evidence_type="standard",
            extra="forbidden",
        )


def test_dashboard_claim_validation():
    art = _sample_artifact_ref()
    cite = _sample_citation()

    for classification in ["measured", "estimated", "hypothesis", "documentary_evidence"]:
        claim = DashboardClaim(
            claim=f"Test statement with classification {classification}",
            classification=classification,
            source_artifacts=[art],
            citations=[cite],
        )
        assert claim.classification == classification
        assert len(claim.source_artifacts) == 1
        assert len(claim.citations) == 1

    # Aliases
    assert M8DashboardClaim is DashboardClaim

    # Invalid classification
    with pytest.raises(ValidationError):
        DashboardClaim(
            claim="Invalid claim classification",
            classification="unsupported_class",
            source_artifacts=[art],
        )

    # Empty claim text forbidden
    with pytest.raises(ValidationError):
        DashboardClaim(
            claim="",
            classification="measured",
            source_artifacts=[art],
        )

    # Missing source_artifacts forbidden
    with pytest.raises(ValidationError):
        DashboardClaim.model_validate({
            "claim": "Missing sources",
            "classification": "measured",
        })

    # Extra field forbidden
    with pytest.raises(ValidationError):
        DashboardClaim(
            claim="Valid claim",
            classification="measured",
            source_artifacts=[art],
            unrecognized="field",
        )


def test_dashboard_section_validation():
    art = _sample_artifact_ref()
    claim = DashboardClaim(
        claim="F1 score measured at 0.91",
        classification="measured",
        source_artifacts=[art],
    )

    section = DashboardSection(
        section_id="evaluation_results",
        title="Resultados y evaluación",
        claims=[claim],
    )
    assert section.section_id == "evaluation_results"
    assert len(section.claims) == 1

    # Aliases
    assert M8DashboardSection is DashboardSection

    # Empty section_id forbidden
    with pytest.raises(ValidationError):
        DashboardSection(
            section_id="",
            title="Title",
            claims=[claim],
        )

    # Empty title forbidden
    with pytest.raises(ValidationError):
        DashboardSection(
            section_id="valid_id",
            title="",
            claims=[claim],
        )

    # Missing claims forbidden
    with pytest.raises(ValidationError):
        DashboardSection.model_validate({
            "section_id": "sec-1",
            "title": "Title",
        })

    # Extra field forbidden
    with pytest.raises(ValidationError):
        DashboardSection(
            section_id="sec-1",
            title="Title",
            claims=[claim],
            extra="disallowed",
        )


def test_dashboard_roadmap_item_validation():
    item = DashboardRoadmapItem(
        item="Deploy container to staging",
        dependencies=["model_registry_approval"],
        success_signal="Service responds 200 to health check",
    )
    assert item.item == "Deploy container to staging"
    assert item.dependencies == ["model_registry_approval"]
    assert item.success_signal == "Service responds 200 to health check"

    # Aliases
    assert M8RoadmapItem is DashboardRoadmapItem

    # Empty item forbidden
    with pytest.raises(ValidationError):
        DashboardRoadmapItem(
            item="",
            dependencies=[],
            success_signal="OK",
        )

    # Empty success_signal forbidden
    with pytest.raises(ValidationError):
        DashboardRoadmapItem(
            item="Item",
            dependencies=[],
            success_signal="",
        )

    # Extra field forbidden
    with pytest.raises(ValidationError):
        DashboardRoadmapItem(
            item="Item",
            dependencies=[],
            success_signal="OK",
            unknown=True,
        )


def test_m8_module_output_validation():
    art = _sample_artifact_ref(artifact_type="dashboard.report", layer="report", produced_by="m8")
    claim = DashboardClaim(
        claim="Model accuracy confirmed",
        classification="measured",
        source_artifacts=[art],
    )
    section = DashboardSection(
        section_id="evaluation",
        title="Evaluation",
        claims=[claim],
    )
    roadmap_item = DashboardRoadmapItem(
        item="Post-deployment audit",
        dependencies=[],
        success_signal="Audit verified",
    )

    out = M8ModuleOutput(
        dashboard_artifact=art,
        sections=[section],
        roadmap=[roadmap_item],
    )
    assert out.dashboard_artifact.artifact_id == "art-1"
    assert len(out.sections) == 1
    assert len(out.roadmap) == 1

    # Empty sections forbidden (min_length=1)
    with pytest.raises(ValidationError):
        M8ModuleOutput(
            dashboard_artifact=art,
            sections=[],
            roadmap=[roadmap_item],
        )

    # Missing dashboard_artifact forbidden
    with pytest.raises(ValidationError):
        M8ModuleOutput.model_validate({
            "sections": [section.model_dump(mode="json")],
            "roadmap": [roadmap_item.model_dump(mode="json")],
        })

    # Extra field forbidden
    with pytest.raises(ValidationError):
        M8ModuleOutput(
            dashboard_artifact=art,
            sections=[section],
            roadmap=[roadmap_item],
            extra="disallowed",
        )


def test_m8_input_envelope_jsonschema_conformance():
    schemas, registry = _schemas()
    input_validator = Draft202012Validator(
        schemas["https://analytixflow.local/contracts/m8/input.schema.json"],
        registry=registry,
    )

    art = _sample_artifact_ref()
    policy = ClaimPolicy(
        required_classification=True,
        require_source_reference=True,
        allow_hypotheses=False,
    )

    req = M8DashboardInput(
        project_id="proj-m8-001",
        execution_id="exec-m8-01",
        module_id="m8",
        contract_version="v1.0",
        context_snapshot_id="ctx-m8-01",
        correlation_id="corr-m8-01",
        idempotency_key="idem-m8-01",
        status="requested",
        requested_by="user-qa",
        requested_at=datetime.now(timezone.utc),
        module_input=M8ModuleInput(
            context_artifacts=[art],
            result_artifacts=[art],
            claim_policy=policy,
        ),
    )

    # Verify alias
    assert isinstance(req, M8DashboardRequest)

    # Valid payload must pass Draft 2020-12 schema validation
    dumped = req.model_dump(mode="json", exclude_none=True)
    input_validator.validate(dumped)

    # Negative test 1: wrong module_id
    invalid_1 = dict(dumped)
    invalid_1["module_id"] = "m7"
    assert len(list(input_validator.iter_errors(invalid_1))) > 0

    # Negative test 2: missing module_input
    invalid_2 = dict(dumped)
    del invalid_2["module_input"]
    assert len(list(input_validator.iter_errors(invalid_2))) > 0

    # Negative test 3: claim_policy required_classification false
    invalid_3 = json.loads(json.dumps(dumped))
    invalid_3["module_input"]["claim_policy"]["required_classification"] = False
    assert len(list(input_validator.iter_errors(invalid_3))) > 0

    # Negative test 4: claim_policy require_source_reference false
    invalid_4 = json.loads(json.dumps(dumped))
    invalid_4["module_input"]["claim_policy"]["require_source_reference"] = False
    assert len(list(input_validator.iter_errors(invalid_4))) > 0

    # Negative test 5: extra property in module_input (additionalProperties: false)
    invalid_5 = json.loads(json.dumps(dumped))
    invalid_5["module_input"]["extra_key"] = "forbidden"
    assert len(list(input_validator.iter_errors(invalid_5))) > 0

    # Negative test 6: unevaluated property in root envelope (unevaluatedProperties: false)
    invalid_6 = json.loads(json.dumps(dumped))
    invalid_6["unknown_root_prop"] = 42
    assert len(list(input_validator.iter_errors(invalid_6))) > 0


def test_m8_output_envelope_jsonschema_conformance():
    schemas, registry = _schemas()
    output_validator = Draft202012Validator(
        schemas["https://analytixflow.local/contracts/m8/output.schema.json"],
        registry=registry,
    )

    art = _sample_artifact_ref(artifact_type="dashboard.report", layer="report", produced_by="m8")
    citation = _sample_citation()

    claim_1 = DashboardClaim(
        claim="Precision and Recall evaluated on test holdout set.",
        classification="measured",
        source_artifacts=[art],
        citations=[citation],
    )
    claim_2 = DashboardClaim(
        claim="Inference computation cost estimated based on local throughput.",
        classification="estimated",
        source_artifacts=[art],
    )
    claim_3 = DashboardClaim(
        claim="Expected churn decrease of 4% over quarterly cycle.",
        classification="hypothesis",
        source_artifacts=[art],
    )
    claim_4 = DashboardClaim(
        claim="System complies with ISO/IEC 25010 maintainability guidelines.",
        classification="documentary_evidence",
        source_artifacts=[art],
        citations=[citation],
    )

    section_1 = DashboardSection(section_id="business_diagnosis", title="Diagnóstico del negocio", claims=[claim_3])
    section_2 = DashboardSection(section_id="data_quality", title="Estado y calidad de los datos", claims=[claim_1])
    section_3 = DashboardSection(section_id="analytical_strategy", title="Estrategia analítica seleccionada", claims=[claim_4])
    section_4 = DashboardSection(section_id="evaluation_results", title="Resultados y evaluación", claims=[claim_1])
    section_5 = DashboardSection(section_id="impact_and_costs", title="Impacto, costos y recomendaciones", claims=[claim_2])
    section_6 = DashboardSection(section_id="roadmap", title="Hoja de ruta", claims=[claim_4])

    roadmap_item = DashboardRoadmapItem(
        item="Production shadow deployment",
        dependencies=["governance_audit_verified"],
        success_signal="Zero regression in latency for 72h",
    )

    result = M8DashboardOutput(
        project_id="proj-m8-001",
        execution_id="exec-m8-01",
        module_id="m8",
        contract_version="v1.0",
        context_snapshot_id="ctx-m8-01",
        correlation_id="corr-m8-01",
        status="succeeded",
        artifacts=[art],
        next_actions=[
            M8NextAction(
                action="executive_review",
                requires_approval=True,
                target_module="m8",
                hypothesis=None,
            )
        ],
        completed_at=datetime.now(timezone.utc),
        output_hash="sha256:" + "c" * 64,
        module_output=M8ModuleOutput(
            dashboard_artifact=art,
            sections=[section_1, section_2, section_3, section_4, section_5, section_6],
            roadmap=[roadmap_item],
        ),
    )

    # Verify alias
    assert isinstance(result, M8DashboardResult)

    dumped = result.model_dump(mode="json", exclude_none=True)
    output_validator.validate(dumped)

    # Negative test 1: wrong module_id
    invalid_1 = dict(dumped)
    invalid_1["module_id"] = "m7"
    assert len(list(output_validator.iter_errors(invalid_1))) > 0

    # Negative test 2: empty sections (minItems: 1)
    invalid_2 = json.loads(json.dumps(dumped))
    invalid_2["module_output"]["sections"] = []
    assert len(list(output_validator.iter_errors(invalid_2))) > 0

    # Negative test 3: invalid classification enum
    invalid_3 = json.loads(json.dumps(dumped))
    invalid_3["module_output"]["sections"][0]["claims"][0]["classification"] = "unsupported_type"
    assert len(list(output_validator.iter_errors(invalid_3))) > 0

    # Negative test 4: missing roadmap in module_output
    invalid_4 = json.loads(json.dumps(dumped))
    del invalid_4["module_output"]["roadmap"]
    assert len(list(output_validator.iter_errors(invalid_4))) > 0

    # Negative test 5: roadmap item missing success_signal
    invalid_5 = json.loads(json.dumps(dumped))
    del invalid_5["module_output"]["roadmap"][0]["success_signal"]
    assert len(list(output_validator.iter_errors(invalid_5))) > 0

    # Negative test 6: extra property in module_output
    invalid_6 = json.loads(json.dumps(dumped))
    invalid_6["module_output"]["extra_prop"] = "invalid"
    assert len(list(output_validator.iter_errors(invalid_6))) > 0

    # Negative test 7: extra property in claim
    invalid_7 = json.loads(json.dumps(dumped))
    invalid_7["module_output"]["sections"][0]["claims"][0]["spurious"] = True
    assert len(list(output_validator.iter_errors(invalid_7))) > 0

    # Negative test 8: unevaluated root property
    invalid_8 = json.loads(json.dumps(dumped))
    invalid_8["unevaluated_root"] = 123
    assert len(list(output_validator.iter_errors(invalid_8))) > 0


def test_m8_roundtrip_serialization():
    art = _sample_artifact_ref()
    cite = _sample_citation()

    input_model = M8DashboardInput(
        project_id="proj-001",
        execution_id="exec-01",
        module_id="m8",
        contract_version="v1.0",
        context_snapshot_id="ctx-01",
        correlation_id="corr-01",
        idempotency_key="key-01",
        status="requested",
        module_input=M8ModuleInput(
            context_artifacts=[art],
            result_artifacts=[art],
            claim_policy=ClaimPolicy(
                required_classification=True,
                require_source_reference=True,
                allow_hypotheses=False,
            ),
        ),
    )

    dumped_input = input_model.model_dump(mode="json")
    reloaded_input = M8DashboardInput.model_validate(dumped_input)
    assert reloaded_input == input_model

    output_model = M8DashboardOutput(
        project_id="proj-001",
        execution_id="exec-01",
        module_id="m8",
        contract_version="v1.0",
        context_snapshot_id="ctx-01",
        correlation_id="corr-01",
        status="succeeded",
        module_output=M8ModuleOutput(
            dashboard_artifact=art,
            sections=[
                DashboardSection(
                    section_id="sec-1",
                    title="Section 1",
                    claims=[
                        DashboardClaim(
                            claim="Claim statement",
                            classification="measured",
                            source_artifacts=[art],
                            citations=[cite],
                        )
                    ],
                )
            ],
            roadmap=[
                DashboardRoadmapItem(
                    item="Item 1",
                    dependencies=["dep-1"],
                    success_signal="OK",
                )
            ],
        ),
    )

    dumped_output = output_model.model_dump(mode="json")
    reloaded_output = M8DashboardOutput.model_validate(dumped_output)
    assert reloaded_output == output_model
