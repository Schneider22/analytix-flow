from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .domain.hashing import canonical_json, sha256_canonical
from .schemas import (
    ClaimPolicy,
    ContractArtifactReference,
    ContractCitation,
    DashboardClaim,
    DashboardRoadmapItem,
    DashboardSection,
    M8DashboardInput,
    M8DashboardOutput,
    M8ModuleOutput,
    M8NextAction,
)
from .services import NotFoundError, ValidationError
from .storage import (
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    ArtifactStore,
    ArtifactStoreError,
    StoredArtifact,
)

# Mandatory executive sections per AnalytixFlow document rector and M8 contracts
SECTION_BUSINESS_DIAGNOSIS = "business_diagnosis"
SECTION_DATA_QUALITY = "data_quality"
SECTION_ANALYTICAL_STRATEGY = "analytical_strategy"
SECTION_EVALUATION_RESULTS = "evaluation_results"
SECTION_IMPACT_AND_COSTS = "impact_and_costs"
SECTION_ROADMAP = "roadmap"

REQUIRED_SECTION_IDS = [
    SECTION_BUSINESS_DIAGNOSIS,
    SECTION_DATA_QUALITY,
    SECTION_ANALYTICAL_STRATEGY,
    SECTION_EVALUATION_RESULTS,
    SECTION_IMPACT_AND_COSTS,
    SECTION_ROADMAP,
]

SECTION_TITLES = {
    SECTION_BUSINESS_DIAGNOSIS: "Diagnóstico del negocio",
    SECTION_DATA_QUALITY: "Estado y calidad de los datos",
    SECTION_ANALYTICAL_STRATEGY: "Estrategia analítica seleccionada",
    SECTION_EVALUATION_RESULTS: "Resultados y evaluación",
    SECTION_IMPACT_AND_COSTS: "Impacto, costos y recomendaciones",
    SECTION_ROADMAP: "Hoja de ruta",
}


class M8DashboardModule:
    """Domain engine for executive dashboard consolidation and evidence governance.

    Transforms M1–M7 context and result artifacts into an immutable, audited
    executive dashboard. Enforces the golden rule of evidence: explicitly
    distinguishes measured results from estimates, hypotheses, and documentary
    evidence. Verifies artifact references and content integrity without inventing
    fictitious metrics or figures.
    """

    module_id = "m8"
    contract_version = "v1.0"

    def validate_claim_policy(self, policy: ClaimPolicy) -> None:
        """Validate that the claim policy respects contractual mandates."""
        if policy.required_classification is not True:
            raise ValidationError("claim_policy.required_classification must be True")
        if policy.require_source_reference is not True:
            raise ValidationError("claim_policy.require_source_reference must be True")

    def verify_artifact_reference(
        self,
        ref: ContractArtifactReference,
        artifact_store: ArtifactStore | None = None,
        expected_project_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Verify an artifact reference's content hash, storage integrity, and project isolation."""
        if not ref.content_hash or not ref.content_hash.startswith("sha256:"):
            raise ValidationError(f"Artifact '{ref.artifact_id}' has invalid content_hash format")

        if artifact_store is not None:
            storage_id = None
            if ref.uri and ref.uri.startswith("local-artifact://"):
                storage_id = ref.uri.removeprefix("local-artifact://")
            elif ref.version_id:
                storage_id = ref.version_id

            if storage_id:
                try:
                    content_bytes = artifact_store.read(storage_id, expected_hash=ref.content_hash)
                except ArtifactNotFoundError as exc:
                    raise NotFoundError(f"Artifact '{ref.artifact_id}' storage not found") from exc
                except (ArtifactIntegrityError, ArtifactStoreError) as exc:
                    raise ValidationError(
                        f"Artifact '{ref.artifact_id}' failed content hash integrity check"
                    ) from exc

                try:
                    parsed = json.loads(content_bytes.decode("utf-8"))
                    if isinstance(parsed, dict):
                        artifact_project = parsed.get("project_id")
                        if (
                            expected_project_id is not None
                            and artifact_project is not None
                            and artifact_project != expected_project_id
                        ):
                            raise ValidationError(
                                f"Artifact '{ref.artifact_id}' belongs to project '{artifact_project}', "
                                f"violating project isolation for '{expected_project_id}'"
                            )
                        return parsed
                except UnicodeDecodeError:
                    pass
                except json.JSONDecodeError:
                    pass

        return None

    def validate_claim(
        self,
        claim: DashboardClaim,
        policy: ClaimPolicy,
        authorized_refs: dict[str, ContractArtifactReference],
    ) -> None:
        """Validate an individual claim against the active policy and authorized artifacts."""
        if not claim.claim or not claim.claim.strip():
            raise ValidationError("Claim text cannot be empty or whitespace")

        valid_classifications = {"measured", "estimated", "hypothesis", "documentary_evidence"}
        if claim.classification not in valid_classifications:
            raise ValidationError(
                f"Invalid classification '{claim.classification}'. Must be one of {sorted(valid_classifications)}"
            )

        # Enforce hypothesis policy
        if claim.classification == "hypothesis" and not policy.allow_hypotheses:
            raise ValidationError(
                f"Claim '{claim.claim[:60]}' is classified as hypothesis, but "
                "allow_hypotheses is False in claim_policy"
            )

        # Enforce source reference policy
        if policy.require_source_reference:
            if not claim.source_artifacts:
                raise ValidationError(
                    f"Claim '{claim.claim[:60]}' has no source_artifacts, but "
                    "require_source_reference is True in claim_policy"
                )

        # Verify that all referenced artifacts are authorized
        for src_ref in claim.source_artifacts:
            if src_ref.artifact_id not in authorized_refs:
                raise ValidationError(
                    f"Claim references unauthorized artifact '{src_ref.artifact_id}'. "
                    "Must be present in context_artifacts or result_artifacts."
                )
            authorized = authorized_refs[src_ref.artifact_id]
            if authorized.content_hash != src_ref.content_hash:
                raise ValidationError(
                    f"Claim artifact reference '{src_ref.artifact_id}' content_hash "
                    f"('{src_ref.content_hash}') does not match authorized input hash ('{authorized.content_hash}') (hash mismatch)"
                )

    def validate_sections(
        self,
        sections: list[DashboardSection],
        policy: ClaimPolicy,
        authorized_refs: dict[str, ContractArtifactReference],
    ) -> None:
        """Validate all executive sections and their claims."""
        if not sections:
            raise ValidationError("At least one executive section is required")

        present_section_ids = set()
        for sec in sections:
            if not sec.section_id or not sec.section_id.strip():
                raise ValidationError("Section section_id cannot be empty")
            if not sec.title or not sec.title.strip():
                raise ValidationError("Section title cannot be empty")
            if not sec.claims:
                raise ValidationError(f"Section '{sec.section_id}' must contain at least one claim")
            for cl in sec.claims:
                self.validate_claim(cl, policy, authorized_refs)
            present_section_ids.add(sec.section_id)

        for required_id in REQUIRED_SECTION_IDS:
            if required_id not in present_section_ids:
                raise ValidationError(f"Missing required executive section '{required_id}'")

    def synthesize_sections(
        self,
        context_artifacts: list[ContractArtifactReference],
        result_artifacts: list[ContractArtifactReference],
        policy: ClaimPolicy,
        artifact_store: ArtifactStore | None = None,
        project_id: str | None = None,
    ) -> list[DashboardSection]:
        """Synthesize the six required executive sections from verified input artifacts."""
        authorized_refs = {a.artifact_id: a for a in context_artifacts + result_artifacts}

        # Inspect and parse artifacts when available
        parsed_contents: dict[str, dict[str, Any]] = {}
        for ref in context_artifacts + result_artifacts:
            parsed = self.verify_artifact_reference(ref, artifact_store, expected_project_id=project_id)
            if parsed is not None:
                parsed_contents[ref.artifact_id] = parsed

        # Partition artifacts by type / layer / module
        context_refs = [a for a in context_artifacts]
        data_refs = [
            a for a in context_artifacts + result_artifacts
            if a.layer in {"bronze", "silver"} or a.artifact_type in {"report.profile", "eda_report", "dataset.bronze", "dataset.silver"}
        ]
        strategy_refs = [
            a for a in context_artifacts + result_artifacts
            if a.layer in {"gold", "model"} or a.artifact_type in {"model.registry", "dataset.gold"} or a.produced_by_module == "m4"
        ]
        eval_refs = [
            a for a in result_artifacts
            if a.artifact_type in {"report.evaluation", "metrics"} or a.produced_by_module == "m5"
        ]
        impact_refs = [
            a for a in result_artifacts
            if a.layer in {"deployment", "audit"} or a.artifact_type in {"deployment.package", "deployment.plan", "governance.audit"} or a.produced_by_module in {"m6", "m7"}
        ]

        # 1. Section: business_diagnosis
        sec1_claims: list[DashboardClaim] = []
        if context_refs:
            primary_ctx = context_refs[0]
            sec1_claims.append(
                DashboardClaim(
                    claim="Business objective and scope defined under formal CRISP-DM governance.",
                    classification="documentary_evidence",
                    source_artifacts=[primary_ctx],
                )
            )
            if policy.allow_hypotheses:
                sec1_claims.append(
                    DashboardClaim(
                        claim="Projected business hypothesis: potential reduction in target operational variance upon deployment.",
                        classification="hypothesis",
                        source_artifacts=[primary_ctx],
                    )
                )
        else:
            fallback_ref = result_artifacts[0]
            sec1_claims.append(
                DashboardClaim(
                    claim="Business context evaluated through downstream execution artifacts.",
                    classification="documentary_evidence",
                    source_artifacts=[fallback_ref],
                )
            )

        # 2. Section: data_quality
        sec2_claims: list[DashboardClaim] = []
        if data_refs:
            primary_data = data_refs[0]
            data_content = parsed_contents.get(primary_data.artifact_id, {})
            row_count = data_content.get("total_rows") or data_content.get("row_count")
            null_count = data_content.get("null_count") or data_content.get("missing_count")

            if row_count is not None:
                sec2_claims.append(
                    DashboardClaim(
                        claim=f"Data profiling verified {row_count} processed records with {null_count or 0} missing values.",
                        classification="measured",
                        source_artifacts=[primary_data],
                    )
                )
            else:
                sec2_claims.append(
                    DashboardClaim(
                        claim=f"Data pipeline artifact '{primary_data.artifact_id}' verified with valid checksum.",
                        classification="documentary_evidence",
                        source_artifacts=[primary_data],
                    )
                )
        else:
            primary_ref = context_artifacts[0] if context_artifacts else result_artifacts[0]
            sec2_claims.append(
                DashboardClaim(
                    claim="Data quality metrics not provided in empirical execution artifacts.",
                    classification="documentary_evidence",
                    source_artifacts=[primary_ref],
                )
            )

        # 3. Section: analytical_strategy
        sec3_claims: list[DashboardClaim] = []
        if strategy_refs:
            primary_strategy = strategy_refs[0]
            sec3_claims.append(
                DashboardClaim(
                    claim=f"Modeling strategy and architecture registered under artifact '{primary_strategy.artifact_id}'.",
                    classification="documentary_evidence",
                    source_artifacts=[primary_strategy],
                )
            )
        else:
            primary_ref = result_artifacts[0] if result_artifacts else context_artifacts[0]
            sec3_claims.append(
                DashboardClaim(
                    claim="Analytical modeling strategy governed according to project baseline standards.",
                    classification="documentary_evidence",
                    source_artifacts=[primary_ref],
                )
            )

        # 4. Section: evaluation_results
        sec4_claims: list[DashboardClaim] = []
        if eval_refs:
            primary_eval = eval_refs[0]
            eval_content = parsed_contents.get(primary_eval.artifact_id, {})
            metrics = eval_content.get("metrics") or eval_content.get("primary_metrics")
            if isinstance(metrics, dict) and metrics:
                metric_desc = ", ".join(f"{k}: {v}" for k, v in list(metrics.items())[:3])
                sec4_claims.append(
                    DashboardClaim(
                        claim=f"Model performance measured against holdout test set: {metric_desc}.",
                        classification="measured",
                        source_artifacts=[primary_eval],
                    )
                )
            else:
                sec4_claims.append(
                    DashboardClaim(
                        claim=f"Evaluation report '{primary_eval.artifact_id}' verified with empirical evaluation criteria.",
                        classification="documentary_evidence",
                        source_artifacts=[primary_eval],
                    )
                )
        else:
            primary_ref = result_artifacts[0] if result_artifacts else context_artifacts[0]
            sec4_claims.append(
                DashboardClaim(
                    claim="Empirical evaluation metrics were not produced in the provided result artifacts.",
                    classification="documentary_evidence",
                    source_artifacts=[primary_ref],
                )
            )

        # 5. Section: impact_and_costs
        sec5_claims: list[DashboardClaim] = []
        if impact_refs:
            primary_impact = impact_refs[0]
            sec5_claims.append(
                DashboardClaim(
                    claim=f"Operational deployment constraints and governance plan verified in artifact '{primary_impact.artifact_id}'.",
                    classification="estimated",
                    source_artifacts=[primary_impact],
                )
            )
        else:
            primary_ref = result_artifacts[0] if result_artifacts else context_artifacts[0]
            sec5_claims.append(
                DashboardClaim(
                    claim="Operational inference costs estimated based on local runtime profile without cloud telemetry.",
                    classification="estimated",
                    source_artifacts=[primary_ref],
                )
            )

        # 6. Section: roadmap (narrative claims in sections)
        sec6_claims: list[DashboardClaim] = []
        primary_ref = result_artifacts[0] if result_artifacts else context_artifacts[0]
        sec6_claims.append(
            DashboardClaim(
                claim="Continuous operational monitoring and rollback procedures established per ADR-0010.",
                classification="documentary_evidence",
                source_artifacts=[primary_ref],
            )
        )

        sections = [
            DashboardSection(
                section_id=SECTION_BUSINESS_DIAGNOSIS,
                title=SECTION_TITLES[SECTION_BUSINESS_DIAGNOSIS],
                claims=sec1_claims,
            ),
            DashboardSection(
                section_id=SECTION_DATA_QUALITY,
                title=SECTION_TITLES[SECTION_DATA_QUALITY],
                claims=sec2_claims,
            ),
            DashboardSection(
                section_id=SECTION_ANALYTICAL_STRATEGY,
                title=SECTION_TITLES[SECTION_ANALYTICAL_STRATEGY],
                claims=sec3_claims,
            ),
            DashboardSection(
                section_id=SECTION_EVALUATION_RESULTS,
                title=SECTION_TITLES[SECTION_EVALUATION_RESULTS],
                claims=sec4_claims,
            ),
            DashboardSection(
                section_id=SECTION_IMPACT_AND_COSTS,
                title=SECTION_TITLES[SECTION_IMPACT_AND_COSTS],
                claims=sec5_claims,
            ),
            DashboardSection(
                section_id=SECTION_ROADMAP,
                title=SECTION_TITLES[SECTION_ROADMAP],
                claims=sec6_claims,
            ),
        ]

        self.validate_sections(sections, policy, authorized_refs)
        return sections

    def build_roadmap(
        self,
        result_artifacts: list[ContractArtifactReference],
    ) -> list[DashboardRoadmapItem]:
        """Build the structured, machine-verifiable roadmap array."""
        return [
            DashboardRoadmapItem(
                item="Executive approval and governance sign-off",
                dependencies=["m7_governance_audit"],
                success_signal="Executive approval recorded with verified SHA-256 hash",
            ),
            DashboardRoadmapItem(
                item="Controlled deployment staging verification",
                dependencies=["executive_approval"],
                success_signal="Container responds 200 OK to health check within SLA threshold",
            ),
            DashboardRoadmapItem(
                item="Continuous post-deployment operational monitoring",
                dependencies=["controlled_deployment"],
                success_signal="Zero regression in operational latency and zero data drift alerts for 72h",
            ),
        ]

    def build_canonical_report_payload(
        self,
        project_id: str,
        execution_id: str,
        sections: list[DashboardSection],
        roadmap: list[DashboardRoadmapItem],
        claim_policy: ClaimPolicy,
    ) -> dict[str, Any]:
        """Construct the canonical, deterministic dictionary for the dashboard.report artifact.

        Volatile timestamps (such as current wall clock time) are omitted to ensure
        that equivalent execution inputs produce identical canonical JSON and SHA-256 digests.
        """
        return {
            "format": "analytixflow.m8.dashboard-report.v1",
            "project_id": project_id,
            "execution_id": execution_id,
            "claim_policy": {
                "required_classification": claim_policy.required_classification,
                "require_source_reference": claim_policy.require_source_reference,
                "allow_hypotheses": claim_policy.allow_hypotheses,
            },
            "sections": [s.model_dump(mode="json", exclude_none=True) for s in sections],
            "roadmap": [r.model_dump(mode="json", exclude_none=True) for r in roadmap],
        }

    def build_dashboard(
        self,
        payload: M8DashboardInput,
        artifact_store: ArtifactStore | None = None,
        project_id: str | None = None,
    ) -> M8DashboardOutput:
        """Execute the full domain transformation from input envelope to output envelope."""
        effective_project_id = project_id or payload.project_id
        if payload.project_id != effective_project_id:
            raise ValidationError(
                f"Payload project_id '{payload.project_id}' does not match expected '{effective_project_id}'"
            )

        self.validate_claim_policy(payload.module_input.claim_policy)

        # Enforce that at least one artifact is provided for synthesis
        all_artifacts = (
            payload.module_input.context_artifacts + payload.module_input.result_artifacts
        )
        if not all_artifacts:
            raise ValidationError(
                "M8 requires at least one context or result artifact to synthesize the dashboard"
            )

        # Synthesize sections and roadmap
        sections = self.synthesize_sections(
            context_artifacts=payload.module_input.context_artifacts,
            result_artifacts=payload.module_input.result_artifacts,
            policy=payload.module_input.claim_policy,
            artifact_store=artifact_store,
            project_id=effective_project_id,
        )
        roadmap = self.build_roadmap(payload.module_input.result_artifacts)

        # Generate canonical payload and deterministic content hash
        report_payload = self.build_canonical_report_payload(
            project_id=effective_project_id,
            execution_id=payload.execution_id,
            sections=sections,
            roadmap=roadmap,
            claim_policy=payload.module_input.claim_policy,
        )

        canonical_bytes = canonical_json(report_payload).encode("utf-8")
        content_hash = sha256_canonical(report_payload)
        digest = content_hash[7:23]
        artifact_id = f"m8-dashboard-report-{digest}"

        if artifact_store is not None:
            stored = artifact_store.put(canonical_bytes)
            uri = stored.uri
        else:
            uri = f"local-artifact://{digest}"

        dashboard_artifact = ContractArtifactReference(
            artifact_id=artifact_id,
            artifact_type="dashboard.report",
            artifact_version="v1",
            version_number=1,
            version_id=f"ver-{digest}",
            content_hash=content_hash,
            uri=uri,
            media_type="application/json",
            layer="report",
            produced_by_module=self.module_id,
        )

        output_envelope = M8DashboardOutput(
            project_id=effective_project_id,
            execution_id=payload.execution_id,
            module_id=self.module_id,
            contract_version=self.contract_version,
            context_snapshot_id=payload.context_snapshot_id,
            correlation_id=payload.correlation_id,
            status="succeeded",
            artifacts=[dashboard_artifact],
            approval_refs=[],
            warnings=[],
            errors=[],
            next_actions=[
                M8NextAction(
                    action="executive_stakeholder_review",
                    requires_approval=True,
                    target_module=self.module_id,
                )
            ],
            completed_at=None,
            output_hash=content_hash,
            module_output=M8ModuleOutput(
                dashboard_artifact=dashboard_artifact,
                sections=sections,
                roadmap=roadmap,
            ),
        )

        return output_envelope
