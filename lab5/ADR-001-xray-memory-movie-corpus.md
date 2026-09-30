# ADR-001: xray-memory for the movie knowledge corpus

- Status: Accepted
- Date: 2026-09-30

## Context

Lab 5 requires a self-built data corpus for agent memory, an evaluation of an
agent using that corpus, and an architecture decision record. The corpus must
support semantic questions about English-language films from the 1990s and
2000s, including film facts and selected sequel relationships.

The source corpus contains 20 films. Every record has an English text suitable
for embedding plus structured attributes such as title, director, year, decade,
genre, series, and part number. Four `SEQUEL_TO` links model the Matrix and
The Lord of the Rings trilogies.

## Decision

Use xray-memory snapshot mode as the memory backend.

1. Store the source dataset in `corpus/movies-90s-2000s.catalog.json` using
   xray-memory's `servicemap` catalog format (`name`, `kind`, `text`, `attrs`,
   and optional `links`).
2. Build the dataset into `movies-90s-2000s.graph.gob.gz` with the
   `nomic-embed-text` model and 256 embedding dimensions.
3. Place the snapshot on the writable xray-memory PVC at `/maps`. xray-memory
   discovers the map and exposes semantic graph search through MCP.
4. Register xray as a `RemoteMCPServer` in the `kagent` namespace at
   `http://xray-memory.xray-memory:8085/mcp`.
5. Use a dedicated read-only `movie-memory-agent`. It has only
   `search_graph`, `get_graph_node`, and `get_graph_stats`; it cannot modify
   the catalog or write conversational notes.

## Consequences

### Positive

- The corpus is reproducible from JSON and can be independently inspected.
- Semantic search supports natural-language questions, while graph links allow
  the agent to explain sequel relationships.
- Snapshot serving avoids re-embedding the complete corpus at every pod start.
- Limiting the agent to read-only tools prevents accidental corruption of the
  evaluation corpus.

### Negative

- Updating the source JSON requires rebuilding and uploading a new snapshot.
- A snapshot must use the same embedding fingerprint as the serving xray
  instance; an incompatible dimension is rejected.
- The xray UI and MCP endpoint are cluster-internal and must remain private,
  because this Lab deployment has no application-level authentication.

## Alternatives considered

- **Qdrant only:** simpler vector retrieval, but it does not preserve the
  explicit sequel edges used in this corpus.
- **Neo4j plus Qdrant:** suitable for the Lab 4 retrieval agent, but adds two
  stores and a custom ingestion path where one xray snapshot is sufficient.
- **LLM-only answers:** rejected because answers would not be grounded in the
  self-built corpus and cannot be evaluated reliably.

## Evaluation evidence

The evaluation suite is in `evaluation/movie-retrieval-cases.json`. It measures
whether the expected document is retrieved in the top 1 and top 3 results, and
whether the agent's final answer contains the required facts. Results are
recorded in `evaluation/RESULTS.md`.

Baseline result: 8 of 10 questions were answered correctly (80% answer
accuracy and observed top-1/top-3 recall). The agent correctly refused the
negative-control question about *Titanic*. Two records (`The Matrix Reloaded`
and `WALL-E`) produced false negatives, so aliases and a query-expansion retry
are identified as a future improvement rather than silently changing the
baseline.
