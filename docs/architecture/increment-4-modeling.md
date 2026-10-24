# Increment 4 Modeling

## Scope

Increment 4 implements the M4 Modeling boundary from CRISP-DM. It consumes a
project-scoped Gold CSV artifact and a project-scoped problem-definition
artifact, executes a bounded local experiment and persists reproducible
candidate artifacts. The central orchestrator remains the only entry point for
module progression.

## Contract boundary

M4 uses contract version `v1.0`. The request declares:

- `classification`, `regression` or `descriptive` as the problem type;
- an explicit allowed technique list;
- `holdout`, `cross_validation` or `temporal_holdout`;
- the test fraction and, when applicable, the fold count or time column; and
- a random seed plus whether the execution environment should be recorded.

The current executable technique vocabulary is deliberately small:

- classification: `logistic_regression` and `decision_tree_classifier`;
- regression: `linear_regression` and `decision_tree_regressor`; and
- descriptive analytics: `descriptive_statistics`.

Supervised runs add a non-selectable comparison baseline internally:
majority-class for classification and mean prediction for regression. An
unsupported technique is rejected instead of being guessed or silently
ignored. Missing target values, invalid temporal values, insufficient class
support and unusable splits are terminal validation errors; rows are never
dropped silently.

## Outputs and approvals

Each successful execution creates:

1. one `experiment.m4` JSON artifact containing the input references, policy,
   split summary, candidate identifiers and reproducibility record;
2. one `model.pipeline` artifact per candidate; and
3. one `model.parameters` JSON artifact per candidate.

All artifacts are immutable, project-scoped and linked through the existing
`artifact_lineage` constraints. Supervised candidate results are measured
holdout or cross-validation observations. Descriptive output is a measured
profile. Neither is a formal M5 evaluation, a probability of success or a
business-impact estimate.

The output contains a `select_model_candidate` next action with
`requires_approval: true`. The approval must target the exact candidate
pipeline artifact and version. M4 does not select a candidate, invoke M5,
consume a model provider, create cloud resources or deploy a service.

## Persistence and security

M4 reuses the existing `executions`, `artifacts` and `artifact_lineage` tables;
no migration is needed. The input and output hashes are persisted in the
execution record and every artifact receives a server-calculated content hash.
The model pipeline is a local scikit-learn/joblib artifact. Loading it is an
explicitly local operation and must not be performed on untrusted artifact
bytes. The API never accepts a client-supplied predecessor or storage path.

## Known limits

M4 accepts Gold CSV only. Excel support remains at M2 ingestion; M3 is the
boundary that produces Gold. Model selection, formal evaluation, bias review,
deployment and monitoring are intentionally deferred to later increments.
Before experiments, the server also parses the problem-definition JSON and
rejects a problem type or declared target that conflicts with the M4 request.
