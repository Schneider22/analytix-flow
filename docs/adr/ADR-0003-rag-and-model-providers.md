# ADR 0003 RAG and Model Providers

Status: Accepted for MVP planning

## Context

The product document defines RAG as reusable technical memory and evidence, not merely a chat surface. It also requires that model and RAG providers remain replaceable and that the MVP not consume paid services or invent references.

## Decision

Separate RAG into two logical scopes:

1. A controlled general knowledge corpus with provenance, dates, scope, methodology and limitations.
2. Versioned project context containing approved business facts, decisions, artifacts and experiment results.

The MVP starts with metadata filtering and textual search over registered sources. Embeddings and vector retrieval remain optional adapters for a later phase. Every retrieved source is represented by a citation that can be resolved to a source and locator.

Agents receive a read-only context package assembled by the orchestrator. The RAG layer cannot change project state, approve a decision or invoke another module.

Model, embedding and retrieval providers are accessed through interfaces that return provider identity, model identity, request metadata and usage or cost information when available. If cost information is unavailable, the result must say so rather than invent a value.

## Provider boundaries

- `ModelProvider`: structured generation under a declared policy.
- `Retriever`: controlled retrieval of source chunks and project artifacts.
- `CitationResolver`: verifies source and locator references.
- `EmbeddingProvider`: optional future vectorization capability.
- `DataSourceConnector`: future authorized source connectors.
- `DeploymentTarget`: local and Docker targets in the MVP; cloud targets only after approval.

No provider interface may bypass the orchestrator or write unapproved project facts.

## Evidence rules

- A source must be registered before it can be cited.
- A citation must include its source identifier and locator.
- A recommendation without supporting evidence must be labeled as a hypothesis.
- A heuristic adequacy score must not be represented as a calibrated probability.
- Project context is appended as versioned facts and artifacts, not rewritten destructively.

## Consequences

The MVP can be tested without a paid provider and can later adopt embeddings, hosted models or cloud retrieval without changing module contracts. The initial textual search may have lower recall than a vector index, so retrieval quality and citation coverage must be tested before expanding the corpus.
