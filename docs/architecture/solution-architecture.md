# Solution Architecture

Status: Implemented through Increment 6 for the bounded local MVP path

## Purpose

This document defines the logical architecture for the AnalytixFlow MVP. It converts the product vision in `docs/AnalytixFlow.docx` into explicit boundaries, responsibilities, data flows and control points. Increments 1 through 6 implement only the persistence, ingestion, preparation, bounded modeling, evidence-evaluation and local deployment/consumption slices described below; the remaining modules are architectural boundaries, not completed features.

## Architectural principles

1. A single orchestrator is the only component allowed to advance the project flow.
2. The eight specialized modules are independently bounded and communicate through versioned contracts.
3. The project context is persistent, versioned and assembled from approved facts and artifacts.
4. Every relevant module execution produces a traceable result or a traceable failure.
5. Artifacts are immutable by version. A correction creates a new artifact version.
6. Human approval is required for material interpretation, data loss, model selection and deployment-related actions.
7. External, paid or cloud actions are behind explicit interfaces and approval gates.
8. RAG supplies evidence and context; it does not replace orchestration or decision ownership.
9. The MVP favors a small, reproducible local flow over broad provider coverage.

## Logical architecture

```text
React + TypeScript portal
          |
          v
FastAPI application API
          |
          v
Central project orchestrator ---- RAG / knowledge interfaces
          |
          v
Durable execution worker
          |
          +---- M1 Business and architecture
          +---- M2 Ingestion and Bronze
          +---- M3 Preparation and Silver/Gold
          +---- M4 Analytical modeling
          +---- M5 Evaluation and selection
          +---- M6 Deployment and consumption
          +---- M7 Governance and operations
          +---- M8 Executive dashboard
          |
          +---- PostgreSQL: state, decisions, approvals, audit and metadata
          +---- ArtifactStore: local files in the MVP, replaceable later
```

The portal sends user commands to the API. The API validates the command and delegates the requested transition to the orchestrator. The orchestrator checks prerequisites, creates an execution record and assigns the work to the worker. A module can read the approved project context and authorized artifacts, but it cannot directly invoke another module.

## Components and responsibilities

### Frontend

React and TypeScript provide:

- Project registration and business-understanding forms.
- Project timeline and current-state display.
- Review of alternatives, data issues, transformations and models.
- Approval and rejection commands scoped to a specific action and artifact version.
- Artifact, lineage and audit views.
- Executive dashboard and roadmap.

The frontend is not a source of truth for state. It renders server responses and sends commands identified by correlation and idempotency keys.

### API

FastAPI exposes resource and command endpoints for projects, executions, artifacts, approvals, decisions, dashboard views and audit records. It validates JSON contracts, enforces authorization and never bypasses the orchestrator for module progression.

### Orchestrator

The orchestrator owns:

- Project state and module state transitions.
- Prerequisite checks.
- Contract version selection.
- Approval gates.
- Iteration creation and configurable iteration limits.
- Idempotency and retry policy.
- Correlation of executions, artifacts, decisions and audit events.

### Worker

The worker performs bounded, durable executions outside the web process. The initial design uses PostgreSQL-backed work records, one or more workers, row locking and idempotency. A future queue technology may replace this implementation without changing module contracts.

### Specialized modules

Each module implements only its domain responsibility. A module receives a validated input contract, a read-only context view and a tool policy. It returns a structured result containing artifacts, warnings, errors and next actions. No module owns project progression.

### PostgreSQL

PostgreSQL stores transactional metadata: projects, context snapshots, executions, decisions, approvals, artifact metadata, datasets, experiments, citations, audit events and operational events. Large binary content is not stored in relational rows by default.

### ArtifactStore

The MVP uses a local filesystem implementation behind an interface. The interface must support immutable writes, content hashes, metadata lookup, read access and retention operations. An object-storage implementation can be added later without changing the domain model.

### RAG and provider interfaces

RAG is exposed through controlled interfaces for source ingestion, textual retrieval and citation resolution. Model providers, embedding providers and external connectors are also interfaces. The MVP does not require a paid provider or an external cloud connection.

## Data flow

1. The user creates a project and records business context.
2. The orchestrator stores a context snapshot and starts M1.
3. M1 produces problem, alternative and recommendation artifacts with citations or explicit hypotheses.
4. The user approves the selected alternative.
5. M2 ingests CSV or Excel files, preserves the original and creates Bronze metadata and profiling artifacts.
6. M3 proposes and applies approved transformations from its bounded v1.1 action vocabulary to create Silver and Gold artifacts.
7. M4 creates reproducible candidate pipelines for the selected analytical problem, records preliminary measured metrics and requests approval for candidate selection.
8. M5 compares candidates against a baseline and either recommends a candidate or creates a bounded iteration request.
9. M6 validates an approved M4 candidate, produces immutable local package and configuration artifacts, exposes hash-verified artifact consumption and records a deployment plan. It does not execute a process, build an image or create cloud infrastructure.
10. M7 records governance and operational evidence. M8 exposes a read-oriented dashboard built from approved artifacts.

All transitions and outputs are linked through `project_id`, `execution_id`, artifact identifiers, versions, content hashes and audit events.

## CRISP-DM mapping

| Product module | CRISP-DM responsibility |
|---|---|
| M1 | Business Understanding |
| M2 | Data Understanding |
| M3 | Data Preparation |
| M4 | Modeling |
| M5 | Evaluation |
| M6 | Deployment |
| M7 | Cross-cutting governance and operation |
| M8 | Cross-cutting communication, impact and roadmap |

The main flow is iterative. M5 can return to M3 or M4 with a concrete hypothesis. M2 can return to M1 or request a revised source interpretation. The orchestrator records each iteration instead of overwriting previous evidence.

## Main boundaries

- The API may read and command; it does not execute analytical jobs inline.
- The orchestrator may schedule modules; it does not contain module-specific analytical logic.
- Modules may read authorized inputs; they do not mutate prior artifacts.
- The RAG layer may retrieve evidence; it does not approve decisions.
- The ArtifactStore persists bytes; PostgreSQL persists metadata and relationships.
- M6 may generate local deployable artifacts; it cannot create cloud infrastructure in the MVP.
- M6 is plan-only: every deployment action remains behind an exact artifact-scoped human approval.

## Architectural decisions summarized

- Local Docker Compose is the execution target for the MVP.
- CSV and Excel are mandatory input formats; Parquet is deferred.
- Pandas is the initial dataframe engine, with an abstraction for a future Polars implementation.
- PostgreSQL is the system of record for state and traceability.
- Local artifact storage is replaceable through an interface.
- Initial RAG uses a controlled corpus, textual retrieval and verifiable references.
- All provider integrations are ports, not hard-coded dependencies.
- M3 transformation semantics are explicit and versioned; free-form actions are rejected rather than interpreted as executable code.
- M4 modeling semantics are explicit and versioned; the MVP supports only the documented local scikit-learn techniques and never presents preliminary metrics as business impact or a probability of success.
- M5 evaluation semantics are evidence-based and versioned; the MVP reuses
  measured M4 results, persists an immutable report and leaves acceptance or
  iteration behind explicit human approval.
