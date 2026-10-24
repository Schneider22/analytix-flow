# Increment 2 API Inventory

Base path: `/api/v1`

## Health

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Checks API and database connectivity. |

## Projects

| Method | Path | Purpose |
|---|---|---|
| POST | `/projects` | Creates a project. |
| GET | `/projects` | Lists projects with `limit` and `offset`. |
| GET | `/projects/{project_id}` | Retrieves one project. |

## Context snapshots

| Method | Path | Purpose |
|---|---|---|
| POST | `/projects/{project_id}/context` | Creates the next immutable context version. |
| GET | `/projects/{project_id}/context` | Lists context versions in ascending order. |

## Decisions

| Method | Path | Purpose |
|---|---|---|
| POST | `/projects/{project_id}/decisions` | Records a decision or pending decision. |
| GET | `/projects/{project_id}/decisions` | Lists project decisions. |

## Artifacts

| Method | Path | Purpose |
|---|---|---|
| POST | `/projects/{project_id}/artifacts/content` | Stores raw bytes locally, calculates the server-side hash and registers the artifact version. |
| POST | `/projects/{project_id}/artifacts` | Registers metadata for bytes already stored by the server; `storage_id` is required and the hash is verified. |
| GET | `/projects/{project_id}/artifacts` | Lists artifact metadata. |

`artifact_id` is the logical artifact identity. `version_id` is the server-side physical row identifier for one immutable version. New versions use `vN`: the first is `v1`, and the server automatically links each later version to the immediately previous version of the same project and identity. A repeated logical identity cannot skip a version or supply its own predecessor.

Historical rows created before the chain migration are returned with `legacy_version: true` and a null `version_number`; they remain readable but cannot be extended through the strict versioning endpoint.

## M2 ingestion

| Method | Path | Purpose |
|---|---|---|
| POST | `/projects/{project_id}/executions/m2` | Runs the deterministic CSV/Excel profile for registered source artifacts and creates an immutable Bronze manifest artifact. |

The source bytes must first be registered through `/artifacts/content`. The M2 request references exact artifact versions, a project context snapshot, a contract version and an idempotency key. The server verifies the content hash and project scope, preserves the original bytes, profiles CSV/XLSX/XLS inputs and records warnings, blocking issues and recovery options. M2 never overwrites a source artifact and never invokes M3 directly.

## Approvals

| Method | Path | Purpose |
|---|---|---|
| POST | `/projects/{project_id}/approvals` | Creates a pending approval with a project, artifact or execution scope. The server calculates `scope_hash`. |
| GET | `/projects/{project_id}/approvals` | Lists approvals. |
| POST | `/projects/{project_id}/approvals/{approval_id}/resolve` | Resolves a pending approval as approved or rejected. |

## M3 preparation

| Method | Path | Purpose |
|---|---|---|
| POST | `/projects/{project_id}/executions/m3` | Applies the bounded M3 preparation plan to project-scoped Bronze artifacts and creates Silver and Gold artifacts when quality and approval gates pass. |

M3 uses contract version `v1.1`. Supported actions are
`normalize_column_names`, `drop_duplicate_rows`, `fill_missing_values`,
`parse_date_columns` and `drop_empty_rows`. A material rule requires an
approved `approve_transformations` artifact approval for every input Bronze
version. Before that approval, the response is `awaiting_approval` and does
not include Silver or Gold artifact references.

## M4 modeling

| Method | Path | Purpose |
|---|---|---|
| POST | `/projects/{project_id}/executions/m4` | Runs bounded local modeling over a project-scoped Gold CSV and problem-definition artifact, then creates reproducible candidate artifacts. |

M4 uses contract version `v1.0`. It supports tabular classification,
regression and descriptive analytics with an explicit local technique
vocabulary, declared split policy and random seed. Supervised executions
always include a baseline candidate and report preliminary metrics as measured
observations. Every successful execution returns a `select_model_candidate`
next action requiring an artifact-scoped approval; M4 does not select a model,
run formal evaluation or deploy anything. The current implementation stores
scikit-learn pipelines locally as immutable artifacts and records the
environment when requested by the contract.

## M5 evaluation

| Method | Path | Purpose |
|---|---|---|
| POST | `/projects/{project_id}/executions/m5` | Reviews project-scoped M4 candidate evidence against a declared baseline and persists an immutable evaluation report. |

M5 uses contract version `v1.0`. Candidate pipeline references must come from
the same successful M4 execution as the declared Gold artifact. The module
reuses measured preliminary metrics and verifies the recorded split policy; it
does not retrain candidates because M4 did not persist enough partition detail
for an independent replay. The response is `awaiting_approval`, includes a
human decision request and can record insufficient evidence or a bounded
iteration request. Each candidate must include an approved,
artifact-scoped `select_model_candidate` approval for its exact artifact
version. It never selects or deploys a model automatically.

## Audit

| Method | Path | Purpose |
|---|---|---|
| GET | `/projects/{project_id}/audit` | Lists append-only audit events for a project. |

## Error behavior

- `404`: project, artifact or approval does not exist in the requested project scope.
- `409`: an approval was already resolved or an artifact identifier is duplicated.
- `422`: request validation or domain validation failed.
- `503`: persistence is unavailable; internal database details are not returned.

Mutating requests may send `X-Correlation-ID`. The value is returned in the response and persisted in audit events. Artifact content requests are limited by `MAX_ARTIFACT_BYTES`; metadata is limited by `MAX_METADATA_BYTES`.

Enterprise authentication, complete multi-user authorization and orchestration commands are intentionally outside this increment.
