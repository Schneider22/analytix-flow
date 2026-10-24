# MVP Scope

Status: Increment 6 implements the bounded local deployment and consumption boundary; M7 and M8 remain pending.

## Objective

The MVP must prove one traceable, human-supervised analytical flow from business problem to locally executable analytical output. It must validate the orchestration model, persistent project context, artifact versioning and approval gates before expanding provider or cloud coverage.

## Included capabilities

### Project and business understanding

- Create a project with company, business need, objective, rules, restrictions and success criteria.
- Persist versioned project-context snapshots.
- Produce three to five analytical alternatives.
- Record evidence, assumptions, risks, limitations and a transparent adequacy score.
- Record the user's selected alternative through an explicit approval or decision.

### Data

- Upload CSV and Excel files. Parquet is explicitly deferred to a later phase.
- Preserve the original bytes and ingestion metadata.
- Profile structures, rows, columns, types, missing values, duplicates, temporal coverage and potential identifiers.
- Report ingestion errors and recovery options.
- Produce Bronze, Silver and Gold dataset artifacts.

### Preparation and modeling

- Propose transformations and show their impact.
- Require review for material data loss or semantic interpretation changes.
- Support tabular classification, tabular regression and basic descriptive analytics.
- Build reproducible pipelines with a declared split policy and parameters.
- Compare candidates against a baseline.
- Record metrics, limitations, potential bias and operating complexity.

Increment 4 implements a bounded local modeling execution. It supports
tabular classification, tabular regression and descriptive analytics through
an explicit technique vocabulary, declared split policy and recorded random
seed. It always emits a baseline for supervised problems, persists candidate
pipeline and parameter artifacts, and requests human approval before a
candidate is selected for formal evaluation. Preliminary metrics are measured
experiment observations, not effectiveness probabilities or business impact.

Increment 5 reviews the measured preliminary evidence emitted by M4. It
verifies project-scoped references, compares selected candidates with the
persisted baseline and records an immutable evaluation report. Because M4 does
not yet persist exact partition assignments and the current success criteria
are narrative, M5 reports insufficient evidence and requests human approval;
it does not retrain, select, deploy or infer effectiveness probabilities.

Increment 6 prepares a project-scoped, immutable local deployment package and
configuration artifact from an exact M4 model candidate. It requires an
approved `accept_model` approval, records a new `approve_deployment_action`
approval request for the exact package, and returns `awaiting_approval`.
Consumption is limited to hash-verified reads from the local ArtifactStore.
M6 may read model bytes for integrity verification, but does not deserialize or
execute model binaries, start processes, build images, create cloud resources
or invoke paid services.

### Local consumption and reporting

- Generate a local API or analytical service contract.
- Generate a model/package artifact and Docker build context.
- Produce a deployment plan without creating cloud resources.
- Provide an audit view, artifact registry and project-state view.
- Provide an executive dashboard that distinguishes measured results, estimates, hypotheses and documentary evidence.

## Explicit exclusions

- No autonomous agents with unsupervised external actions.
- No generic Data Lake or cloud connectors.
- No cloud deployment or cloud resource creation.
- No paid model, embedding or data service.
- No use of real credentials.
- No claim of model effectiveness without experimental evidence.
- No invented references, costs or success probabilities.
- No mandatory support for time-series forecasting, segmentation or deep learning.
- No complete production monitoring, drift remediation or automated rollback.
- No execution of a local process, Docker image build or cloud deployment from M6.

## Assumptions

- The MVP runs locally through Docker Compose.
- PostgreSQL is available as the local metadata store.
- Artifact bytes are stored in a local volume through an `ArtifactStore` interface.
- CSV and Excel are the only mandatory file inputs; Parquet is not part of the MVP.
- The initial RAG corpus is curated and registered with provenance.
- Module providers can be deterministic, human-assisted or locally available; the architecture must not require a paid provider.
- The initial execution model can use a PostgreSQL-backed worker queue.

## Product limits

- A module cannot advance the project directly.
- A module cannot modify an existing artifact version.
- An execution must be idempotent and correlated to one project and one module.
- Iterations must state a hypothesis, objective and success signal.
- The maximum number of iterations is configurable and must be approved as a product policy.
- Deployment targets are limited to local process and Docker artifact generation.
- Cost values are displayed only when measured or supported by a declared estimation source; otherwise they are marked unavailable.

## Success criteria

The MVP scope is considered validated when a test project can:

1. Record the business problem and criteria of success.
2. Receive three to five alternatives with evidence or explicit hypotheses.
3. Select an alternative through a recorded approval.
4. Ingest CSV and Excel without overwriting the original.
5. Review data-quality issues and approve material transformations.
6. Produce versioned Silver and Gold artifacts with lineage.
7. Execute a suitable tabular or descriptive analytical process.
8. Compare results with a baseline and record limitations.
9. Generate local consumption artifacts without cloud side effects.
10. Generate a local, human-gated consumption/deployment package without cloud side effects.
11. Display an auditable dashboard distinguishing measured, estimated and hypothetical claims.
12. Re-run an execution with the same data and configuration when the technique permits reproducibility.

## Evidence policy

An adequacy score is a documented decision aid, not a probability of success. A benefit estimate is not a measured business impact. A hypothesis is not an observed result. Every dashboard claim must identify its classification and its supporting artifact or citation.
