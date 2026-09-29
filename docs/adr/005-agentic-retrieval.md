# ADR-005: Compare Agentic Retrieval with Official Qdrant MCP and Abox Qdrant MCP

- Status: Accepted
- Date: 2026-09-29
- Owners: Abox laboratory team

## Context

The `feat/llmd-embeddings` release already deploys Qdrant and an Abox-specific
`qdrant-mcp`. That server exposes `vector_store` and `vector_find`, sends text to
an external llama.cpp embeddings endpoint, and stores 768-dimensional
`nomic-embed-text-v1.5` vectors in `abox-nomic`.

The laboratory also requires the official `qdrant/mcp-server-qdrant`. Version
0.8.1 exposes `qdrant-store` and `qdrant-find`. It embeds in process with
FastEmbed and defaults to `sentence-transformers/all-MiniLM-L6-v2`, which
produces 384-dimensional vectors.

The chat model used by a kagent Agent and the embedding model used by an MCP
server solve different problems. `default-model-config` controls tool selection
and answer generation for both `retrieval-agent` and `k8s-agent`. MiniLM or
Nomic converts documents and queries into vectors inside the selected MCP
implementation.

## Decision

Run both retrieval configurations against the same eight-document corpus and
the same eight queries. Keep the following variables fixed:

- agent name: `retrieval-agent`;
- agent model: `default-model-config`;
- corpus text and metadata;
- system-prompt rules and answer format;
- query order and expected document IDs;
- Qdrant instance and search limit of five.

Change only the vector toolset and its embedding implementation:

| Configuration | MCPServer | Store/find tools | Embedding model | Collection | Dimensions |
|---|---|---|---|---|---:|
| Official | `qdrant-official-mcp` | `qdrant-store`, `qdrant-find` | `sentence-transformers/all-MiniLM-L6-v2` | `lab4-minilm` | 384 |
| Abox baseline | `qdrant-mcp-lab4` | `vector_store`, `vector_find` | `nomic-ai/nomic-embed-text-v1.5` through llama.cpp | `lab4-nomic` | 768 |

Separate collections are mandatory. Their dimensions and embedding spaces are
different, so vectors cannot be copied or mixed. The original text must be
re-embedded by each MCP server.

The release-owned `abox-nomic` collection already contained nine operational
documents when inspected. The experiment therefore uses `qdrant-mcp-lab4`, an
isolated instance of the same `ghcr.io/den-vasyliev/abox/qdrant-mcp:0.4.0`
image with the same command, tools, Qdrant service, and external llama.cpp
endpoint. Only its Kubernetes resource name and collection name differ. This
preserves the release data and prevents unrelated documents from changing the
retrieval ranks.

The official server runs as a kagent-managed stdio MCPServer. It is launched by
the official `uv` container with the Python package pinned to
`mcp-server-qdrant==0.8.1`. This avoids relying on an unrelated third-party
container image while retaining the upstream implementation.

## Corpus and query design

The corpus is stored in ConfigMap `kagent/agentic-retrieval-corpus`. Each key is
one independent Kubernetes manifest document and becomes the `doc_id` metadata
field. The corpus covers Qdrant storage, sidecar networking, Flux OCI
reconciliation, llm-d routing, MCP tools, agent model selection, the Abox MCP,
and InferencePool endpoint selection.

The query set includes English, Ukrainian, and Russian. This intentionally tests
cross-language retrieval because the target project uses all three languages.
The expected document for each query is declared before running the experiment
in `docs/examples/lab4/evaluation-queries.tsv`.

## Evaluation method

For each configuration:

1. Apply the matching `retrieval-agent` manifest.
2. Start a new agent chat to avoid conversation carry-over.
3. Ingest the fixed corpus and verify eight successful store calls. For the
   Abox retry, generate the input from the measured official payloads and
   verify byte-for-byte equality before retrieval.
4. Run each query in a separate new chat.
5. Record the tool called, ordered `doc_id` values, final answer, and elapsed
   time shown by the client trace.
6. Score retrieval and answer quality without changing the expected IDs.

Metrics:

- **Tool-use rate:** queries where the required find tool was called / 8.
- **Hit@1:** queries where the first returned `doc_id` is expected / 8.
- **Hit@3:** queries where the expected `doc_id` is in the first three / 8.
- **Grounded answer accuracy:** answers supported by the retrieved manifest / 8.
- **Unsupported-claim count:** factual claims absent from retrieved documents.
- **Median observed latency:** median end-to-end duration from the agent trace.

## Preflight evidence

The first cluster inspection on 2026-09-29 found that the experiment had not
yet started from the required feature release:

| Check | Observed value | Interpretation |
|---|---|---|
| OCI source | `oci://ghcr.io/den-vasyliev/abox/releases` | Main release stream, not the required feature stream |
| OCI revision | `0.8.9@sha256:ae9363e44d98d9ad7aeba35485bfde2f5e683598869b95ea48ac6bcf08c77b40` | Step 1 not complete |
| `retrieval-agent` model | `gemini-gemini-2-5-flash`, Ready `Unknown` | Stale reference from the main 0.8.9 release |
| `k8s-agent` model | `default-model-config`, Ready `True` | Correct |
| default model | OpenAI `gpt-4.1-mini`, Accepted `True` | Valid shared reasoning model |
| first `k8s-agent` chat | OpenAI 401; key shown as `OPENAI_A***_KEY` | Published placeholder reached the provider; live Secret needs a real credential |
| existing MCP image | `ghcr.io/den-vasyliev/abox/qdrant-mcp:0.4.0` | Abox MCP, not the official Qdrant MCP |

The OCI source was then switched successfully to
`releases-llmd-embeddings:0.9.5@sha256:c64296f47365d94ea69d771425afbff663e683ab32daed0b778338e2ba113335`.
The local `flux` CLI was unavailable, so the Kustomizations were not manually
reconciled by that command and the live `retrieval-agent` still held its old
model reference. The runbook therefore performs manual reconciliation through
the Flux CRD annotations with `kubectl`. The model must be Ready before either
retrieval configuration is measured; otherwise that failure would confound the
embedding comparison.

The missing `default-model-config` was subsequently created through the kagent
UI with a valid OpenAI credential. A new `kagent/k8s-agent` chat completed
successfully, which verifies the reasoning model path independently of the
embedding and vector-store paths. No credential value is recorded in this ADR.

The official comparison manifest was then applied to `retrieval-agent`. The
Agent reported Ready `True`, referenced `default-model-config`, and exposed the
official `qdrant-store` and `qdrant-find` tools from
`qdrant-official-mcp`. Corpus ingestion and retrieval scoring were pending at
that point.

The first ingestion attempt issued the eight store calls concurrently. One call
created `lab4-minilm` and stored `DOC-08-inference-pool`; the other seven failed
with collection-already-exists conflicts. This is consistent with a race in the
official server's automatic check-then-create path. This partial attempt is
excluded from retrieval metrics. The dedicated collection will be reset and
the retry will issue store calls strictly sequentially. The retry subsequently
reported eight successful calls in DOC-01 through DOC-08 order with no errors.
Independent inspection confirmed the named vector `fast-all-minilm-l6-v2` with
size 384 and Cosine distance. It also found nine points but eight unique IDs:
`DOC-08-inference-pool` appeared twice because the first attempt's successful
point survived before the eight-point retry. The two complete payloads were
verified as identical, one duplicate point was removed, and the final collection
contained eight points with eight unique document IDs.

## Results

Every value below is based on an observed run; no expected value is presented
as a measured result.

| Metric | Official MiniLM MCP | Abox Nomic MCP |
|---|---:|---:|
| Indexed documents | 8 (exact count; 8 unique IDs) | 8 (exact count; 8 unique IDs) |
| Collection vector size | 384 (`fast-all-minilm-l6-v2`, Cosine) | 768 (`default`, Cosine) |
| Tool-use rate | 100.0% | 100.0% |
| Hit@1 | 87.5% | 100.0% |
| Hit@3 | 87.5% | 100.0% |
| Grounded answer accuracy | 75.0% | 100.0% |
| Unsupported claims | 1 | 0 |
| Median observed latency | not recorded by UI | not recorded by UI |

### Per-query observations

| Query | Expected | Official returned IDs | Official answer | Abox returned IDs | Abox answer |
|---|---|---|---|---|---|
| Q01 | DOC-01-qdrant-storage | DOC-01, DOC-05, DOC-07, DOC-06, DOC-08 | Correct and grounded: `/qdrant/storage`, 5Gi | DOC-01, DOC-05, DOC-07, DOC-06, DOC-04 | Correct and grounded |
| Q02 | DOC-02-sidecar-network | DOC-02, DOC-05, DOC-07, DOC-01, DOC-03 | Correct and grounded: localhost URL and shared Pod network | DOC-02, DOC-04, DOC-05, DOC-07, DOC-08 | Correct and grounded |
| Q03 | DOC-03-flux-oci | DOC-05, DOC-01, DOC-02, DOC-03, DOC-06 | Incorrect: claimed insufficient evidence although DOC-03 was fourth | DOC-03, DOC-08, DOC-07, DOC-02, DOC-05 | Correct and grounded: OCIRepository plus Kustomization |
| Q04 | DOC-04-llmd-route | DOC-04, DOC-08, DOC-07, DOC-02, DOC-05 | Correct and grounded: `llm-d-embedding` route and rewrite | DOC-04, DOC-08, DOC-05, DOC-07, DOC-03 | Correct and grounded |
| Q05 | DOC-05-official-qdrant-mcp | DOC-05, DOC-06, DOC-07, DOC-01, DOC-08 | Correct and grounded: `qdrant-store`, `qdrant-find` | DOC-05, DOC-07, DOC-06, DOC-01, DOC-08 | Correct and grounded |
| Q06 | DOC-06-agent-model | DOC-06, DOC-05, DOC-07, DOC-02, DOC-04 | Correct and grounded: reasoning model is independent from embedder | DOC-06, DOC-07, DOC-05, DOC-04, DOC-02 | Correct and grounded |
| Q07 | DOC-07-abox-qdrant-mcp | DOC-07, DOC-05, DOC-08, DOC-06, DOC-02 | Incomplete: identified the server but omitted `vector_store` and `vector_find` | DOC-07, DOC-04, DOC-05, DOC-02, DOC-03 | Correct and grounded: `vector_store`, `vector_find` |
| Q08 | DOC-08-inference-pool | DOC-08, DOC-04, DOC-07, DOC-06, DOC-05 | Correct and grounded: matching Pods and one candidate | DOC-08, DOC-04, DOC-07, DOC-05, DOC-06 | Correct and grounded |

Before the remaining official runs, the live Agent reverted to the release's
Abox toolset. The attempted Q02 through Q08 runs therefore called `vector_find`
against the not-yet-created `abox-nomic` collection and returned no documents.
They are precondition failures, not MiniLM measurements, and are excluded from
both configurations' scores. The experiment manifests now disable Flux
reconciliation on this specific Agent; the annotation is removed when GitOps is
restored.

The later Abox preflight found that `abox-nomic` had become available with a
768-dimensional Cosine vector and nine unique release documents. Their IDs
covered Qdrant, Flux, llm-d, kagent, and sidecar resources, but none were the
fixed `DOC-01` through `DOC-08` evaluation records. This collection is retained
unchanged and excluded from scoring; the controlled Abox run uses the isolated
`lab4-nomic` collection described above.

The first isolated Abox ingestion produced the expected 768-dimensional Cosine
vector and eight unique points, but its `DOC-04` through `DOC-08` IDs belonged
to a different release corpus: `DOC-04-abox-mcpserver`,
`DOC-05-abox-mcpagent`, `DOC-06-abox-httproute`, `DOC-07-inference-pool`, and
`DOC-08-abox-configmap`. Because it did not use the same documents as the
official run, it is excluded from all comparison metrics. The corpus ConfigMap
and both Agent prompts now carry reconciliation and exact-key guards; the
dedicated `lab4-nomic` collection must be reset before the controlled retry.

The second ingestion attempt reported eight successful sequential `vector_store`
calls in DOC-01 through DOC-08 order. Independent Qdrant inspection confirmed
the `default` vector with size 768 and Cosine distance, eight total points,
eight unique IDs, and the exact predefined ID list. The subsequent answers,
however, cited manifest values that differ from the fixed corpus. Payload text
comparison confirmed that `lab4-nomic` stored an older corpus under those IDs:
for example, Qdrant storage was a 10Gi local PV at `/mnt/data/qdrant`, while the
live ConfigMap and official collection both contained the 5Gi StatefulSet
volume at `/qdrant/storage`. This run is a precondition failure and is excluded
from all metrics. The retry requires an exact payload-to-ConfigMap comparison,
not only matching IDs and point counts.

The final controlled retry used a generated `DOCUMENTS_JSON` prompt built from
the already measured `lab4-minilm` payloads. The retrieval Agent passed those
JSON strings to eight sequential `vector_store` calls without a delegation
hop. Independent verification then compared every `lab4-nomic` document
byte-for-byte with its `lab4-minilm` counterpart. All eight IDs and all eight
SHA-256 fingerprints matched, so the Abox collection is valid for retrieval
evaluation. This guarantees identical evaluation text while still exercising
the default Abox MCP store tool.

### Evaluation conclusion

Use the Abox Nomic MCP configuration as the retrieval baseline for this
project. In this controlled run it ranked the expected document first for all
eight English, Ukrainian, and Russian queries, while the official MiniLM
configuration did so for seven. It also produced eight grounded answers,
compared with six for the official configuration. Both configurations selected
their retrieval tool for every query.

This result applies to the fixed eight-document corpus and one observed Agent
run. It does not establish that Nomic is universally better than MiniLM; a
larger corpus, repeated runs, and recorded latency would be required for that
claim. Latency is excluded because the UI did not expose a value for either
configuration.

## Consequences

- The experiment compares complete agent behavior, including whether the model
  chooses the correct tool, rather than measuring vector similarity alone.
- Multilingual queries may expose limitations of both embedding models; results
  must be reported by query instead of hidden behind one aggregate score.
- The official server performs embedding in its Pod, so it has a higher memory
  requirement and a cold-start model download. The Abox server keeps MCP memory
  small but depends on the external llama.cpp embedding service.
- Agent-generated ingestion can fail or skip calls. Collection point counts are
  therefore required evidence before retrieval is evaluated.

## References

- <https://github.com/qdrant/mcp-server-qdrant>
- <https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2>
- <https://github.com/den-vasyliev/abox/tree/feat/llmd-embeddings>
