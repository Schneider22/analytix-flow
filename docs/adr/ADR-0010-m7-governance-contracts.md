# ADR-0010: M7 Governance and Operational Contracts

## Status

Accepted for Increment 7 MVP implementation.

## Context

The product rector document (`docs/AnalytixFlow.docx`, paragraphs 140–152) establishes Module 7 as "Gobierno, trazabilidad y operación continua", deliberately separated from deployment (M6) to distinguish release from operational maintenance.

Its core responsibilities include:
1. Recording which agent performed each action and with which inputs.
2. Versioning datasets, transformations, configurations and models.
3. Maintaining a history of decisions and human approvals.
4. Monitoring errors, latency, availability and consumption.
5. Tracking data quality and data freshness.
6. Planning model drift detection for when production data becomes available.
7. Documenting incident management, alerts, rollbacks and new versions.
8. Recording costs and comparing them with initial estimates.
9. Maintaining the project flow state: completed modules, modules awaiting approval, failed modules, and prerequisites to continue.
10. Delivering an audit log, artifact registry, operational indicators and maintenance procedures.

In the local MVP, there are no live cloud inference runtimes or paid external telemetry services. Cost cannot be labeled as a measured real value without an experimental or telemetry measurement backing it; in the absence of cloud consumption, cost is marked as not applicable or not available rather than claiming an unmeasured `$0.00`.

## Decision

1. **Contracts and schemas**: Define strict Pydantic schemas in `backend/app/schemas.py` that strictly mirror the existing Draft 2020-12 JSON Schemas (`contracts/m7/input.schema.json` and `contracts/m7/output.schema.json`):
   - `M7OperationalPolicy`: Declares audit retention requirements, quality check names and freshness check names.
   - `M7ModuleInput`: Validates unique execution IDs, referenced project artifacts and the operational policy.
   - `M7GovernanceRequest`: Full execution envelope for M7 with `module_id="m7"`, `contract_version="v1.0"`, idempotency key, correlation ID, context snapshot and request status.
   - `M7ProjectState`: Structured project flow state containing `current_phase`, a mapping of module statuses (`module_statuses`), and a list of blocking reasons (`blocked_reasons`).
   - `M7OperationalIndicator`: Typed indicator entry with name, mandatory evidence classification (`measured`, `estimated`, `hypothesis`, `documentary_evidence`), value status string, and optional source artifact reference.
   - `M7MaintenancePlan`: Concrete procedures (`procedures`) and future production controls (`future_controls`).
   - `M7ModuleOutput` and `M7GovernanceResult`: Typed result structures matching `execution-result.schema.json`.

2. **Classification and cost policy**: Operational indicators must strictly adhere to the project's evidence classification. Cost claims without direct telemetry cannot be marked as `measured`; they are represented as `not_applicable` or `not_available` under `documentary_evidence`.

3. **Distinction between project phase and module status**: `current_phase` represents the CRISP-DM life-cycle stage of the project, while `module_statuses` records the execution status of each module (`m1` through `m7`).

4. **Persistence and immutability**: M7 will produce a canonical, immutable audit artifact (`governance.audit`) stored in the `ArtifactStore`, linked via `artifacts` and `artifact_lineage`, with SHA-256 verification. No new database tables or Alembic migrations are introduced; existing relational tables (`projects`, `executions`, `artifacts`, `artifact_lineage`, `approvals`, `decisions`, `audit_events`) are sufficient.

## Consequences

- The project flow state, audit log, and operational metrics are inspectable through typed, schema-validated contracts.
- Compatibility with M1–M6 is preserved; orchestrator remains the single point of module transition.
- Module 8 (Dashboard) can reliably consume the structured governance outputs and audit artifacts without inventing state or bypass logic.
