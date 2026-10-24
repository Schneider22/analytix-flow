# ADR-0009: M6 local deployment and consumption boundary

## Status

Accepted for Increment 6 MVP implementation.

## Context

The MVP must produce a locally consumable analytical output while preserving
human control over model acceptance and deployment-related actions. The
existing model artifacts are immutable local ArtifactStore entries and M5
does not authorize automatic deployment. Cloud resources, paid providers and
real credentials are out of scope.

## Decision

M6 is a plan-only module coordinated by the central orchestrator. It requires
an exact server-verified `accept_model` approval for a successful M4
`model.pipeline` artifact, writes canonical `deployment.config` and
`deployment.package` artifacts with project-scoped lineage, and creates a
pending exact-package `approve_deployment_action` approval. It returns
`awaiting_approval` and exposes only hash-verified, project-scoped artifact
consumption.

The module never deserializes or executes model binaries, starts processes,
builds Docker images, creates cloud resources or invokes external providers.
It may read model bytes solely for SHA-256 verification. Docker and cloud
targets are represented as local descriptors; `cloud_execution_allowed` is
always false. Existing `executions`, `artifacts`, `artifact_lineage`,
`approvals` and `audit_events` tables are sufficient, so no Alembic migration
is introduced.

## Consequences

M6 is reproducible and auditable without adding provider coupling or cloud
costs. A later increment must implement any actual model-serving runtime,
image build, deployment executor, authentication and rollback semantics behind
new contracts and approvals. The generated descriptor is not evidence that a
model is effective or that a deployment has succeeded.
