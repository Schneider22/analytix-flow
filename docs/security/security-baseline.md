# Security Baseline

Status: Proposed for Increment 0

## Scope

This baseline defines the minimum security behavior for the local MVP. It is a design and verification baseline, not a claim that the controls are already implemented.

## Project isolation

- Every project-owned query and artifact operation is scoped by `project_id` and organization scope.
- The API must authorize the user before returning project context, artifacts, decisions or approvals.
- Module context packages contain only the artifacts and sources authorized for that project and execution.
- Cross-project references are rejected unless an explicit, approved sharing policy exists.
- Audit records include the actor, project and correlation identifier.

## Roles and approvals

The minimum role model is:

- `owner`: manages the project and can request or approve permitted project decisions.
- `reviewer`: reviews evidence and approves or rejects scoped actions.
- `operator`: runs permitted local operations but cannot approve business or deployment decisions by default.

An approval must identify the action, execution, artifact identifier, artifact version and scope hash. An interface approval does not grant credentials or cloud permissions. Cost-bearing, external-data, credential and deployment actions require a dedicated approval gate.

## File and dataset controls

- Accept only CSV and Excel in the MVP.
- Validate extension and detected content rather than trusting the filename.
- Apply configurable size, row and processing-time limits.
- Reject path traversal, unsupported archive behavior and malformed files.
- Preserve originals as immutable artifacts.
- Store uploads outside executable paths.
- Do not place raw data in logs, error messages or model prompts unless the policy explicitly permits it.
- Record classification and retention metadata.

## Secrets and providers

- No real credentials are required for the MVP.
- Secrets must not be committed, stored in artifacts or returned in errors.
- Provider interfaces must receive credentials through a runtime secret mechanism, not project context.
- External provider use must record provider, model, request policy and usage or cost information when available.
- The default execution policy denies external network access for data and model jobs unless explicitly enabled.

## Execution isolation

- Analytical work runs in a worker separate from the API process.
- Workers use least privilege and a restricted filesystem.
- Container processes should not require root privileges.
- Tools exposed to modules are allowlisted and typed.
- Arbitrary shell commands and arbitrary outbound HTTP are not module capabilities.
- Resource limits and cancellation behavior must be defined before running untrusted or large inputs.

## Errors and observability

Errors are classified as validation, prerequisite, data-quality, approval, policy, retryable execution or terminal execution failures. User-facing messages explain recovery without exposing stack traces, secrets or raw sensitive data. Internal diagnostics remain linked to the execution and audit trail.

## Security verification

The MVP verification plan must include:

- Authorization tests for project isolation.
- Approval-scope and replay tests.
- Malformed-file, path-traversal and size-limit tests.
- Secret-redaction tests.
- Network-policy and tool-allowlist tests.
- Worker restart and idempotency tests.
- Audit completeness tests.
- Contract validation tests that reject unknown or malformed fields where the runtime validator is configured to do so.

## Data retention and deletion

Retention, deletion and backup policy require product and compliance approval. Until those decisions are made, the MVP should expose metadata needed to implement retention without silently deleting artifacts or audit history.
