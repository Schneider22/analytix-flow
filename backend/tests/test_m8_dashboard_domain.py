from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from app.domain.hashing import canonical_json, sha256_canonical
from app.m8_dashboard import (
    M8DashboardModule,
    REQUIRED_SECTION_IDS,
    SECTION_BUSINESS_DIAGNOSIS,
    SECTION_DATA_QUALITY,
    SECTION_ANALYTICAL_STRATEGY,
    SECTION_EVALUATION_RESULTS,
    SECTION_IMPACT_AND_COSTS,
    SECTION_ROADMAP,
)
from app.schemas import (
    ClaimPolicy,
    ContractArtifactReference,
    DashboardClaim,
    DashboardRoadmapItem,
    DashboardSection,
    M8DashboardInput,
    M8DashboardOutput,
    M8ModuleInput,
)
from app.services import ValidationError
from app.storage import LocalArtifactStore


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
    layer: str = "report",
    produced_by: str = "m1",
    content_hash: str | None = None,
    uri: str | None = None,
    version_id: str | None = None,
) -> ContractArtifactReference:
    return ContractArtifactReference(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        artifact_version="v1",
        version_number=1,
        version_id=version_id or f"ver-{artifact_id}",
        content_hash=content_hash or ("sha256:" + "a" * 64),
        uri=uri or f"local-artifact://{artifact_id}",
        layer=layer,
        produced_by_module=produced_by,
    )


def _sample_input(
    project_id: str = "proj-m8-001",
    context_artifacts: list[ContractArtifactReference] | None = None,
    result_artifacts: list[ContractArtifactReference] | None = None,
    allow_hypotheses: bool = False,
) -> M8DashboardInput:
    ctx = context_artifacts if context_artifacts is not None else [
        _sample_artifact_ref("ctx-art-1", "business_understanding", "source", "m1")
    ]
    res = result_artifacts if result_artifacts is not None else [
        _sample_artifact_ref("res-eval-1", "report.evaluation", "report", "m5"),
        _sample_artifact_ref("res-gov-1", "governance.audit", "audit", "m7"),
    ]
    return M8DashboardInput(
        project_id=project_id,
        execution_id="exec-m8-001",
        module_id="m8",
        contract_version="v1.0",
        context_snapshot_id="ctx-snap-001",
        correlation_id="corr-m8-001",
        idempotency_key="key-m8-001",
        status="requested",
        module_input=M8ModuleInput(
            context_artifacts=ctx,
            result_artifacts=res,
            claim_policy=ClaimPolicy(
                required_classification=True,
                require_source_reference=True,
                allow_hypotheses=allow_hypotheses,
            ),
        ),
    )


# 1. Test generation of six contractual sections
def test_generation_of_six_contractual_sections():
    module = M8DashboardModule()
    req = _sample_input()
    sections = module.synthesize_sections(
        context_artifacts=req.module_input.context_artifacts,
        result_artifacts=req.module_input.result_artifacts,
        policy=req.module_input.claim_policy,
        project_id=req.project_id,
    )

    assert len(sections) == 6
    generated_ids = [s.section_id for s in sections]
    assert generated_ids == REQUIRED_SECTION_IDS

    for sec in sections:
        assert sec.title
        assert len(sec.claims) >= 1
        for claim in sec.claims:
            assert claim.claim
            assert claim.classification in {"measured", "estimated", "hypothesis", "documentary_evidence"}
            assert len(claim.source_artifacts) >= 1


# 2. Test valid structure of roadmap
def test_valid_structure_of_roadmap():
    module = M8DashboardModule()
    req = _sample_input()
    roadmap = module.build_roadmap(req.module_input.result_artifacts)

    assert len(roadmap) >= 1
    for item in roadmap:
        assert isinstance(item, DashboardRoadmapItem)
        assert item.item and len(item.item) > 0
        assert isinstance(item.dependencies, list)
        assert item.success_signal and len(item.success_signal) > 0


# 3. Test rejection of hypotheses when forbidden
def test_rejection_of_hypotheses_when_forbidden():
    module = M8DashboardModule()
    art = _sample_artifact_ref()
    auth_refs = {art.artifact_id: art}
    policy = ClaimPolicy(allow_hypotheses=False)

    hypothesis_claim = DashboardClaim(
        claim="Speculative ROI benefit projected at 15%",
        classification="hypothesis",
        source_artifacts=[art],
    )

    with pytest.raises(ValidationError, match="allow_hypotheses is False"):
        module.validate_claim(hypothesis_claim, policy, auth_refs)


# 4. Test acceptance of hypotheses when allowed
def test_acceptance_of_hypotheses_when_allowed():
    module = M8DashboardModule()
    art = _sample_artifact_ref()
    auth_refs = {art.artifact_id: art}
    policy = ClaimPolicy(allow_hypotheses=True)

    hypothesis_claim = DashboardClaim(
        claim="Target retention rate hypothesis projected at 92%",
        classification="hypothesis",
        source_artifacts=[art],
    )

    # Should not raise
    module.validate_claim(hypothesis_claim, policy, auth_refs)

    # Also test synthesis includes hypothesis when allowed
    req = _sample_input(allow_hypotheses=True)
    sections = module.synthesize_sections(
        context_artifacts=req.module_input.context_artifacts,
        result_artifacts=req.module_input.result_artifacts,
        policy=req.module_input.claim_policy,
        project_id=req.project_id,
    )
    all_claims = [c for s in sections for c in s.claims]
    hyp_claims = [c for c in all_claims if c.classification == "hypothesis"]
    assert len(hyp_claims) >= 1


# 5. Test rejection of references to unauthorized artifacts
def test_rejection_of_unauthorized_artifact_references():
    module = M8DashboardModule()
    art_auth = _sample_artifact_ref("auth-art", "report")
    art_unauth = _sample_artifact_ref("unauth-art-99", "report")
    auth_refs = {art_auth.artifact_id: art_auth}
    policy = ClaimPolicy(allow_hypotheses=False)

    claim = DashboardClaim(
        claim="Measured empirical accuracy 0.94",
        classification="measured",
        source_artifacts=[art_unauth],
    )

    with pytest.raises(ValidationError, match="unauthorized artifact 'unauth-art-99'"):
        module.validate_claim(claim, policy, auth_refs)


# 6. Test rejection of references with incorrect hashes
def test_rejection_of_references_with_incorrect_hashes():
    module = M8DashboardModule()
    art_auth = _sample_artifact_ref("art-1", "report", content_hash="sha256:" + "a" * 64)
    art_corrupted = _sample_artifact_ref("art-1", "report", content_hash="sha256:" + "b" * 64)
    auth_refs = {art_auth.artifact_id: art_auth}
    policy = ClaimPolicy(allow_hypotheses=False)

    claim = DashboardClaim(
        claim="Statement with forged or modified content_hash",
        classification="documentary_evidence",
        source_artifacts=[art_corrupted],
    )

    with pytest.raises(ValidationError, match="hash mismatch"):
        module.validate_claim(claim, policy, auth_refs)

    # Also test storage verification failure
    with TemporaryDirectory() as tmpdir:
        store = LocalArtifactStore(Path(tmpdir), max_bytes=1024 * 1024)
        stored = store.put(b'{"content": "real"}')
        # Reference claims a different hash than what was actually put
        bad_ref = _sample_artifact_ref(
            "stored-art",
            "report",
            content_hash="sha256:" + "0" * 64,
            uri=stored.uri,
        )
        with pytest.raises(ValidationError, match="failed content hash integrity check"):
            module.verify_artifact_reference(bad_ref, store, expected_project_id="proj-1")


# 7. Test project isolation
def test_project_isolation():
    module = M8DashboardModule()
    with TemporaryDirectory() as tmpdir:
        store = LocalArtifactStore(Path(tmpdir), max_bytes=1024 * 1024)
        # Store an artifact belonging to alien project
        alien_payload = {"project_id": "alien-project-999", "data": "foreign"}
        stored = store.put(json.dumps(alien_payload).encode("utf-8"))

        ref = _sample_artifact_ref(
            "alien-art",
            "report",
            content_hash=stored.content_hash,
            uri=stored.uri,
        )

        with pytest.raises(ValidationError, match="violating project isolation"):
            module.verify_artifact_reference(ref, store, expected_project_id="target-project-001")


# 8. Test rejection of claims without source when required
def test_rejection_of_claims_without_source_when_required():
    module = M8DashboardModule()
    policy = ClaimPolicy(require_source_reference=True)

    with pytest.raises(ValidationError):
        # Pydantic model requires source_artifacts, but passing [] with policy requires source
        claim = DashboardClaim(
            claim="Claim without any backing artifacts",
            classification="measured",
            source_artifacts=[],
        )
        module.validate_claim(claim, policy, {})


# 9. Test absence of invented metrics when evidence is missing
def test_absence_of_invented_metrics_when_evidence_is_missing():
    module = M8DashboardModule()
    # Provide only a generic business context artifact, without M5 evaluation or M2 profile metrics
    ctx = [_sample_artifact_ref("ctx-only", "context", "source", "m1")]
    res = [_sample_artifact_ref("gov-only", "governance.audit", "audit", "m7")]

    req = _sample_input(context_artifacts=ctx, result_artifacts=res)
    sections = module.synthesize_sections(
        context_artifacts=req.module_input.context_artifacts,
        result_artifacts=req.module_input.result_artifacts,
        policy=req.module_input.claim_policy,
        project_id=req.project_id,
    )

    eval_sec = next(s for s in sections if s.section_id == SECTION_EVALUATION_RESULTS)
    data_sec = next(s for s in sections if s.section_id == SECTION_DATA_QUALITY)

    # In evaluation_results, because no M5 metrics exist, no claims should be marked as "measured"
    for claim in eval_sec.claims:
        assert claim.classification != "measured"
        assert "not produced" in claim.claim.lower() or "criteria" in claim.claim.lower()

    # In data_quality, without empirical numbers, claim should be documentary_evidence
    for claim in data_sec.claims:
        assert claim.classification == "documentary_evidence"


# 10. Test deterministic canonical serialization and reproducible SHA-256 hash
def test_deterministic_canonical_serialization_and_reproducible_hash():
    module = M8DashboardModule()
    req = _sample_input()

    out1 = module.build_dashboard(req)
    out2 = module.build_dashboard(req)

    # The canonical output hashes must be exactly identical
    assert out1.output_hash == out2.output_hash
    assert out1.artifacts[0].content_hash == out2.artifacts[0].content_hash

    # Check payload serialization determinism
    p1 = module.build_canonical_report_payload(
        req.project_id,
        req.execution_id,
        out1.module_output.sections,
        out1.module_output.roadmap,
        req.module_input.claim_policy,
    )
    p2 = module.build_canonical_report_payload(
        req.project_id,
        req.execution_id,
        out2.module_output.sections,
        out2.module_output.roadmap,
        req.module_input.claim_policy,
    )

    assert canonical_json(p1) == canonical_json(p2)
    assert sha256_canonical(p1) == sha256_canonical(p2)


# 11. Test validation of output against M8 Pydantic model and JSON schema
def test_validation_of_output_against_m8_pydantic_model():
    module = M8DashboardModule()
    with TemporaryDirectory() as tmpdir:
        store = LocalArtifactStore(Path(tmpdir), max_bytes=1024 * 1024)

        # Pre-seed verified context and result artifacts in store
        ctx_data = {
            "project_id": "proj-m8-001",
            "business_need": "Executive dashboard validation",
        }
        stored_ctx = store.put(json.dumps(ctx_data).encode("utf-8"))
        ctx_art = _sample_artifact_ref(
            "ctx-m1",
            "business_understanding",
            "source",
            "m1",
            content_hash=stored_ctx.content_hash,
            uri=stored_ctx.uri,
        )

        eval_data = {
            "project_id": "proj-m8-001",
            "metrics": {"accuracy": 0.942, "f1_score": 0.915, "roc_auc": 0.967},
        }
        stored_eval = store.put(json.dumps(eval_data).encode("utf-8"))
        res_eval = _sample_artifact_ref(
            "eval-m5",
            "report.evaluation",
            "report",
            "m5",
            content_hash=stored_eval.content_hash,
            uri=stored_eval.uri,
        )

        req = _sample_input(context_artifacts=[ctx_art], result_artifacts=[res_eval])
        output = module.build_dashboard(req, artifact_store=store)

        # Validate Pydantic model
        assert isinstance(output, M8DashboardOutput)
        dumped = output.model_dump(mode="json", exclude_none=True)
        reloaded = M8DashboardOutput.model_validate(dumped)
        assert reloaded.execution_id == output.execution_id

        # Validate against JSON schema Draft 2020-12
        schemas, registry = _schemas()
        validator = Draft202012Validator(
            schemas["https://analytixflow.local/contracts/m8/output.schema.json"],
            registry=registry,
        )
        validator.validate(dumped)

        # Verify that evaluation section has measured metrics
        eval_sec = next(s for s in output.module_output.sections if s.section_id == SECTION_EVALUATION_RESULTS)
        measured_claims = [c for c in eval_sec.claims if c.classification == "measured"]
        assert len(measured_claims) == 1
        assert "0.942" in measured_claims[0].claim or "0.915" in measured_claims[0].claim


# 12. Test explicit handling of missing required artifacts
def test_explicit_handling_of_missing_required_artifacts():
    module = M8DashboardModule()

    # Empty context and result artifacts
    empty_req = _sample_input(context_artifacts=[], result_artifacts=[])
    with pytest.raises(ValidationError, match="requires at least one context or result artifact"):
        module.build_dashboard(empty_req)

    # Missing section in manual section validation
    art = _sample_artifact_ref()
    auth_refs = {art.artifact_id: art}
    policy = ClaimPolicy()
    incomplete_sections = [
        DashboardSection(
            section_id=SECTION_BUSINESS_DIAGNOSIS,
            title="Business",
            claims=[
                DashboardClaim(
                    claim="Objective",
                    classification="documentary_evidence",
                    source_artifacts=[art],
                )
            ],
        )
    ]
    with pytest.raises(ValidationError, match="Missing required executive section"):
        module.validate_sections(incomplete_sections, policy, auth_refs)
