docs/adr/003-embedding-model.md

# ADR-003: Text Embedding Model

## Status
Accepted

## Context

Abox requires a text embedding model for semantic search
and vector storage in Qdrant.

## Decision

Use nomic-embed-text-v1.5.

Use llama.cpp as the local inference runtime.

Use 256-dimensional Matryoshka embeddings.

## Reasons

- open source
- local execution
- 8192 token context
- Matryoshka support
- reduced vector storage
- compatible with vector search / Qdrant

## Alternatives

- all-MiniLM
- BGE
- Ollama embedding models

## Consequences

Positive:
- no external API required
- smaller embeddings
- easier local development

Negative:
- model must be downloaded locally
- CPU inference consumes local resources