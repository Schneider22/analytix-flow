# ADR 0001 Technology Stack

Status: Accepted for MVP planning

## Context

AnalytixFlow needs a web portal, a Python analytical backend, durable project state, reproducible local execution and a path to future provider and cloud integrations. The MVP must stay testable and must not depend on paid services or cloud infrastructure.

## Decision

Use the following stack for the MVP:

- Frontend: React with TypeScript.
- Backend API: Python with FastAPI.
- Persistence: PostgreSQL.
- Analytical engine: Pandas and scikit-learn.
- Execution: Docker Compose for local development and verification.
- Artifact bytes: local filesystem behind an `ArtifactStore` interface.
- Contracts: versioned JSON Schema, validated in the API and at module boundaries.
- Provider integrations: explicit interfaces for model, embedding, retrieval, data-source and deployment providers.

## Rationale

React and TypeScript support a stateful review workflow with typed API clients and clear separation between project views, approvals and dashboard views.

FastAPI is suitable for contract-oriented HTTP APIs and Python-based analytical execution. PostgreSQL provides transactional state, versioned metadata, audit records and a durable coordination mechanism for the initial worker.

Pandas is the initial dataframe engine because the MVP targets structured files and scikit-learn pipelines. The data-processing boundary must remain abstract enough to support Polars later if volume or performance requires it.

Docker Compose provides a reproducible local environment without introducing cloud cost or provider-specific deployment assumptions.

Storing large files in a local artifact volume rather than PostgreSQL keeps relational tables focused on metadata and traceability. The interface makes a future object-storage implementation possible.

## Consequences

Positive consequences:

- A small local stack can exercise the complete flow.
- Contracts and artifact hashes are independent of provider choices.
- PostgreSQL can persist state across worker restarts.
- Analytical code remains close to the Python ecosystem.

Trade-offs:

- Local artifact storage needs explicit retention and backup procedures.
- PostgreSQL-backed work coordination is sufficient for the MVP but is not a substitute for a distributed workflow engine at larger scale.
- Pandas may require a later performance review for larger datasets.
- Provider interfaces require adapters and test doubles before external integrations are enabled.

## Rejected for the MVP

- Generic cloud connectors.
- Cloud-native orchestration services.
- A mandatory vector database.
- A mandatory paid model provider.
- A distributed task queue before local durability and idempotency are proven.

## Revisit triggers

Revisit this decision if dataset volume exceeds the local processing envelope, if multiple workers require higher-throughput coordination, if a cloud target is approved, or if the chosen analytical workloads require capabilities not supported by Pandas and scikit-learn.
