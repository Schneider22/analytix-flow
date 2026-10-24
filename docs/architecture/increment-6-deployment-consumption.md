# Increment 6 — Deployment and Consumption

## Scope

M6 is a controlled boundary between the evaluated model evidence and local
consumption. It accepts one exact, project-scoped `model.pipeline` artifact
produced by a successful M4 execution and an approved `accept_model` approval.
It creates two immutable artifacts:

- `deployment.config`: a redacted, canonical JSON configuration descriptor.
- `deployment.package`: a canonical JSON package descriptor that references
  the selected model and configuration artifacts.

The package is a local descriptor, not an executed model or a built image.
M6 may read selected model bytes solely to verify the stored SHA-256; it never
deserializes or executes them. A consumer can retrieve an exact artifact
version through the project-scoped content endpoint, which verifies the
stored SHA-256 before returning bytes. Reading this endpoint does not activate
or deploy the package; the exact deployment action remains approval-gated.

## Human control and security boundary

M6 verifies the approval action, logical identity, physical `version_id`,
version label, version number, content hash, project and source M4 execution
on the server. It creates a pending `approve_deployment_action` approval bound
to the generated package version and returns `awaiting_approval`.

M6 does not resolve that approval, start a local process, load a joblib model,
build a Docker image, create cloud resources, call a cloud provider or use
real credentials. `cloud_execution_allowed` is always false. Secret-like
configuration keys are redacted before persistence, and runtime secret access
is rejected by the MVP boundary.

## Idempotency and traceability

The existing project/module/idempotency key constraint makes repeated M6
requests return the original result when the request hash and execution ID
match. Package and configuration artifacts are version `v1` with logical
identities derived from the execution ID. Their lineage points to the exact
selected model; the package also points to its configuration artifact.
Executions, approvals, artifacts, lineage and audit events remain in the
existing PostgreSQL persistence model. No new Alembic migration is required.

## Target semantics

`local_process` produces a local plan descriptor. `docker_artifact` produces a
descriptor suitable for a future local Docker build-context implementation;
M6 does not invoke Docker. `cloud_plan_only` records an informational plan
with `cost_status: not_available`; it has no cloud side effect.

## Non-goals

M6 does not implement runtime model serving, automatic model selection,
production authentication, cloud deployment, CI/CD, monitoring, drift
remediation, automatic rollback or provider-specific integrations. Those
capabilities require later increments and additional human-approved
decisions.
