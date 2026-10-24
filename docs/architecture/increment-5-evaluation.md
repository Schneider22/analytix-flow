# Increment 5 Evaluation

## Scope

M5 is the CRISP-DM Evaluation boundary. It consumes successful M4 evidence
only: the project-scoped Gold artifact, the M4 experiment artifact and one or
more M4 `model.pipeline` candidate artifacts. All references must belong to
the same project and the same M4 execution.

## Evidence policy

M4 currently persists measured preliminary metrics, the split strategy, the
random seed and candidate configuration. It does not persist exact row
indices or fold assignments. M5 therefore performs an evidence review rather
than retraining or independently replaying a split. The evaluation report
marks the evidence as `measured_preliminary`, records the limitation and does
not convert narrative success criteria into invented thresholds.

The report also records requested metrics, baseline comparisons,
reproducibility and leakage-review status, bias checks that are unavailable
without subgroup evidence, and limitations. Missing metrics, inconsistent
references, incompatible split strategies and unsuccessful or cross-project
M4 executions are rejected.
Before reuse, M5 verifies the persisted hash of the M4 execution result so
the measured evidence cannot be silently replaced in the transaction record.

Each evaluated candidate must carry one approved, artifact-scoped
`select_model_candidate` approval. The server resolves the approval by ID and
checks its project, action, status, scope hash and exact artifact version;
client-provided approval metadata is never trusted by itself.

## Human control and persistence

The central orchestrator is the only entry point for M5. The module persists
an immutable `evaluation.m5` report through the existing ArtifactStore and
`artifacts`/`artifact_lineage` tables. The output is `awaiting_approval` and
requests `record_insufficient_evidence`; M5 does not select, retrain, deploy,
call cloud infrastructure or call a paid provider. Replaying the same
idempotency key after completion returns the exact stored result. A duplicate
request observed while the first execution is still running returns a
conflict and cannot create a second execution or report.

## Deliberate deferrals

- independent split replay requires a future M4 contract revision that stores
  exact partition assignments or equivalent reproducible evidence;
- machine-evaluable success thresholds are deferred until a product decision
  defines their semantics;
- formal subgroup bias analysis, model selection, M6 deployment and M7/M8
  capabilities remain outside this increment.
