# ADR 0007 M4 Modeling Boundary

## Status

Accepted for Increment 4.

## Context

The MVP must execute a reproducible analytical process after M3 produces a
Gold dataset, while preserving human control over model selection. The M4
contract requires a problem definition, an explicit model policy, a split
policy, reproducibility settings and versioned experiment and candidate
artifacts. The contract does not authorize formal evaluation, deployment or a
generic model-provider integration.

## Decision

Implement M4 as a deterministic local module behind the central orchestrator.
Use pandas for tabular loading and scikit-learn pipelines for the bounded
classification and regression techniques. Support descriptive statistics as a
non-predictive path. Fit preprocessing inside each training partition to avoid
data leakage, use the declared random seed, and record split details and
environment metadata when requested.

Persist the experiment, candidate pipeline and candidate parameter records as
immutable artifacts using the existing `executions`, `artifacts` and
`artifact_lineage` tables. The server verifies both input artifacts, project
scope, content hashes and exact versions, and checks that the problem-definition
JSON agrees with the declared problem type and target when one is provided. A
successful result requests an
artifact-scoped `select_model_candidate` approval; it does not select a
candidate or invoke M5.

## Consequences

- M4 is reproducible locally without paid providers, network access or cloud
  actions.
- Existing project-scoped foreign keys and artifact versioning protect the new
  lineage without a schema migration.
- Preliminary results are explicitly classified as measured observations, not
  effectiveness probabilities, formal evaluation or business impact.
- The technique vocabulary is intentionally narrower than all of scikit-learn;
  adding a technique requires a contract decision, tests and documentation.
- Joblib pipeline artifacts are local executable data and must not be loaded
  from untrusted sources.
- M5 remains responsible for formal evaluation and candidate selection.
