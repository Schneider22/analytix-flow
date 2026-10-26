# ADR-0011: M8 Dashboard and Evidence Consolidation Contracts

## Status

Accepted for Increment 8 MVP implementation.

## Context

The product rector document (`docs/AnalytixFlow.docx`, paragraphs 153–174) establishes Module 8 as "Dashboard ejecutivo y consolidación de evidencia", designed as the synthesis and decision-making engine of the CRISP-DM life-cycle.

Key responsibilities established in the rector document:
1. Synthesizing project evidence across all preceding phases (M1–M7) without altering empirical results.
2. Presenting an executive summary organized into six core sections:
   - Diagnóstico del negocio (`business_diagnosis`).
   - Estado y calidad de los datos (`data_quality`).
   - Estrategia analítica seleccionada (`analytical_strategy`).
   - Resultados y evaluación (`evaluation_results`).
   - Impacto, costos y recomendaciones (`impact_and_costs`).
   - Hoja de ruta (`roadmap`).
3. Enforcing the golden rule of evidence: strictly and explicitly distinguishing between:
   - Measured empirical facts (`measured`).
   - Numerical approximations or projections with declared assumptions (`estimated`).
   - Theoretical or unproven business expectations (`hypothesis`).
   - Documentary and methodological references (`documentary_evidence`).
4. Reusing existing repository infrastructure: `ArtifactStore`, immutable JSON artifacts verified via SHA-256, and relational lineage (`artifact_lineage`).
5. Absence of frontend UI: Module 8 is implemented as a backend analytical service that emits structured execution envelopes and generates canonical report artifacts. Future web frontends will consume these contracts directly.

Pre-existing contract definitions in `contracts/m8/` (`input.schema.json` and `output.schema.json`) and `contracts/common/` govern module input envelopes, claim validation policies, verifiable citations, section structures, and execution results.

## Decision

1. **Contracts and schemas in `backend/app/schemas.py`**:
   Implement strict Pydantic models (inheriting from `StrictModel` with `extra="forbid"`) that strictly mirror the Draft 2020-12 JSON Schemas:
   - `ContractCitation`: Implements `contracts/common/citation.schema.json` with verifiable source locator, evidence type (`technical_documentation`, `research`, `standard`, `project_artifact`, `experience_record`, `hypothesis`), optional timestamp, and limitations list.
   - `ClaimPolicy` (aliased as `M8ClaimPolicy`): Enforces `required_classification=True` (const), `require_source_reference=True` (const), and `allow_hypotheses` as strict boolean (`bool | None = Field(default=None, strict=True)`).
   - `M8ModuleInput`: Strictly requires `context_artifacts`, `result_artifacts`, and `claim_policy`.
   - `M8DashboardInput` (aliased as `M8DashboardRequest`): Full envelope input matching `contracts/common/execution-envelope.schema.json` and `contracts/m8/input.schema.json` with `module_id="m8"`.
   - `DashboardClaim` (aliased as `M8DashboardClaim`): Represents an individual assertion with `claim` text, mandatory `classification` enum, referenced `source_artifacts` (`list[ContractArtifactReference]`), and optional verifiable `citations` (`list[ContractCitation]`).
   - `DashboardSection` (aliased as `M8DashboardSection`): Represents an executive section with `section_id`, `title`, and `claims`.
   - `DashboardRoadmapItem` (aliased as `M8RoadmapItem`): Represents an actionable step in the project roadmap with `item`, `dependencies`, and verifiable `success_signal`.
   - `M8ModuleOutput`: Encapsulates `dashboard_artifact` (`ContractArtifactReference`), `sections` (`min_length=1`), and `roadmap`.
   - `M8NextAction`: Governed next action reference adhering to `execution-result.schema.json`.
   - `M8DashboardOutput` (aliased as `M8DashboardResult`): Full envelope output matching `contracts/common/execution-result.schema.json` and `contracts/m8/output.schema.json` with `module_id="m8"`.

2. **Claim classification and policy enforcement**:
   - The four epistemic classifications (`measured`, `estimated`, `hypothesis`, `documentary_evidence`) are strictly enforced at the schema level.
   - If `claim_policy.allow_hypotheses` is set to `False`, subsequent domain logic in Phase 2 must reject or disallow hypothesis claims. Reclassifying an unmeasured hypothesis as measured or documentary evidence is strictly prohibited.
   - `source_artifacts` references must point to valid `ContractArtifactReference` descriptors whose SHA-256 content hashes match physical storage.

3. **Roadmap vs. Executive Sections**:
   - `contracts/m8/output.schema.json` mandates `roadmap` as a dedicated top-level array within `module_output`.
   - To maintain perfect alignment with the six sections mandated by the document rector, `module_output.sections` contains the six executive sections (including `section_id="roadmap"` with narrative claims), while `module_output.roadmap` contains the structured, machine-actionable milestones (`DashboardRoadmapItem`).

4. **Persistence and Immutability**:
   - M8 will generate a canonical, immutable report artifact (`dashboard.report`) stored via `ArtifactStore` with deterministic SHA-256 verification.
   - No new database tables or migrations are required; relational persistence leverages `artifacts`, `artifact_lineage`, and `audit_events`.

## Consequences

- The executive dashboard input and output envelopes are fully specified, strictly typed, and bidirectional-tested against JSON Schema Draft 2020-12.
- Evaluated and unevaluated properties are strictly checked (`additionalProperties: false` and `unevaluatedProperties: false`).
- Full backward and forward compatibility with M1–M7 is guaranteed.
- Phase 2 can implement the domain aggregation logic in `backend/app/m8_dashboard.py` without requiring schema changes.
