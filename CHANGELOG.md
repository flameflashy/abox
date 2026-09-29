# Changelog

## Unreleased — Laboratory 4 (2026-09-29)

### Prepared

- Added an official Qdrant MCP manifest pinned to
  `mcp-server-qdrant==0.8.1`, with FastEmbed and
  `sentence-transformers/all-MiniLM-L6-v2` writing to the isolated
  `lab4-minilm` collection.
- Added official and Abox variants of `retrieval-agent`. Both use
  `default-model-config`, the same ingestion/retrieval rules, and the same
  `k8s-agent` delegate; only the MCP server and vector tool names differ.
- Added an isolated `qdrant-mcp-lab4` instance of the release's Abox MCP image.
  It uses the same Nomic llama.cpp endpoint and writes to `lab4-nomic`, keeping
  the controlled corpus separate from release data in `abox-nomic`.
- Added a fixed eight-document Kubernetes corpus and eight predefined English,
  Ukrainian, and Russian queries with expected document IDs.
- Added [ADR-005](docs/adr/005-agentic-retrieval.md), the
  [execution runbook](docs/todo/TODO-agentic-retrieval.md), and a scorer for
  tool-use rate, Hit@1, Hit@3, grounded answer accuracy, unsupported claims,
  and median observed latency.

### Execution status

- Preflight inspection found the cluster on the main `releases:0.8.9` OCI
  artifact rather than `releases-llmd-embeddings`. `k8s-agent` was Ready on
  `default-model-config`, while `retrieval-agent` was not Ready because it still
  referenced `gemini-gemini-2-5-flash`.
- The OCI source was switched to `releases-llmd-embeddings:0.9.5` at digest
  `sha256:c64296f47365d94ea69d771425afbff663e683ab32daed0b778338e2ba113335`.
  Manual Kustomization reconciliation is still required because the Codespace
  does not have the `flux` CLI.
- A live `k8s-agent` chat reached OpenAI but returned 401 because the generated
  Secret contained the published `OPENAI_API_KEY` placeholder. The runbook now
  includes silent, out-of-band Secret replacement and agent rollout steps.
- Created `default-model-config` with a valid credential through the kagent UI;
  a new `kagent/k8s-agent` chat completed successfully.
- Applied the official comparison configuration to `retrieval-agent`. It is
  Ready on `default-model-config` with `qdrant-store` and `qdrant-find` from
  `qdrant-official-mcp`.
- Recorded the first official-MCP ingestion attempt: concurrent first writes
  caused seven collection-creation conflicts and stored only
  `DOC-08-inference-pool`. Updated the prompt and runbook to reset the dedicated
  collection and serialize `qdrant-store` calls for the controlled retry.
- The controlled retry reported eight successful sequential `qdrant-store`
  calls in DOC-01 through DOC-08 order. Independent inspection confirmed a
  384-dimensional named MiniLM vector with Cosine distance, nine total points,
  and eight unique IDs. After verifying the two `DOC-08-inference-pool`
  payloads were identical, removed one duplicate and confirmed the final count
  of eight points and eight unique IDs.
- Excluded Q02-Q08 attempts that unexpectedly used the release's Abox toolset
  before `abox-nomic` was indexed. Added a per-Agent Flux reconciliation guard
  to keep each comparison manifest active until its run is complete.
- Completed the eight-query official MiniLM run: 100% retrieval-tool use,
  87.5% Hit@1, 87.5% Hit@3, 75% grounded answer accuracy, and one unsupported
  claim. The UI did not expose latency, so no latency value was invented.
- Inspected the release-owned `abox-nomic` collection: it uses a
  768-dimensional Cosine vector and already contains nine unique operational
  documents. Preserved that data and prepared the isolated `lab4-nomic`
  collection for the controlled Abox run.
- Excluded the first isolated Abox ingestion because its eight points came from
  a different release corpus. Added a Flux reconciliation guard to the fixed
  corpus ConfigMap and exact expected-key validation to both Agent prompts.
- Completed the controlled Abox retry with eight sequential `vector_store`
  calls. Independent inspection confirmed the exact eight predefined IDs in
  eight points and a 768-dimensional `default` vector with Cosine distance.
  Retrieval answers then contradicted the fixed manifests. Payload inspection
  confirmed that old manifest text had been stored under the expected IDs, so
  the run was excluded from metrics.
- Added an exact corpus verifier that compares every indexed `document` payload
  with either the live ConfigMap or another Qdrant collection and reports
  SHA-256 fingerprints. Strengthened both ingestion prompts with live-read
  requirements and content sentinels.
- Added a direct ingestion-prompt generator that JSON-encodes the official
  collection payloads. This removes the unreliable Agent delegation
  hop, guarantees the same document bytes for both embedders, and retains eight
  sequential calls to the selected MCP store tool.
- Abox Agentic Retrieval measurements are pending.

## Unreleased — Laboratory 3 (2026-09-22)

### Prepared

- Updated [ADR-003](docs/adr/003-embedding-model.md): selected Qwen3-Embedding-0.6B
  instead of the initial Nomic v1.5 for Ukrainian, Russian, and English.
  Pinned the official Q8_0 GGUF, revision, SHA-256, API contract, and the
  1024 → 256 transformation with L2 normalization. Retained Nomic as a considered alternative.
- [Local ToDo](docs/todo/TODO-embeddings.md): CPU inference with llama.cpp through
  Docker in Codespace, image digest pinning, health checks, and an actual embedding POST.
- [ADR-004](docs/adr/004-embedding-deployment.md) and the
  [cluster ToDo](docs/todo/TODO-embedding-deployment.md): sidecar deployment and a
  separate llm-d plan with compatibility checks for the embedding route.
- [Sidecar template](docs/examples/embeddings-sidecar.yaml.template): two containers
  in one Pod, an init download with checksum verification, probes, and resource settings.
- [Smoke check](scripts/verify-embeddings.py): HTTP contract, finite numeric values,
  L2 norm, and three cross-language examples for 1024/256 dimensions.
- Translated both ADRs, both ToDo documents, and the Changelog into English;
  the remaining repository Markdown files were already in English.

### Execution status

- Abox is running in Codespace on x86_64 with 4 CPUs and 15 GiB RAM; approximately
  8.8 GiB RAM was available during inspection. The workspace/Docker filesystem
  had only 1.4 GiB free, so no additional Qwen image or weights were downloaded.
- A standalone Nomic llama.cpp Deployment and a Nomic llm-d ModelService were
  already running. These are deployment baselines and do not replace the selected
  multilingual Qwen model in ADR-003.
- The sidecar example has not been deployed. Qwen runtime performance and retrieval
  quality have not been measured.
- The Qdrant collection and application integration have not been created yet.

### Verified locally

- The Python script compiles. Synthetic HTTP responses verified 1024/256 processing
  and rejection of incorrect dimensions, NaN/Infinity, zero norms, and boolean values.
- `bash -n` successfully checked all 15 Bash instruction blocks.
- The sidecar template with a test placeholder digest was parsed by
  `kubectl kustomize`; this checks YAML structure, not server-side validation or
  container execution.
- Local Markdown links and `git diff --check` passed verification.

### Verified in Codespace

- Standalone llama.cpp returned `status: ok` and an OpenAI-compatible embedding:
  768 finite values with L2 norm `0.9999999631` for Nomic v1.5.
- Gateway path `/llmd/v1/embeddings` returned the same valid 768-dimensional Nomic
  response through the direct `llm-d-embedding` Service rule.
- Existing llm-d versions were recorded: ModelService chart `v0.3.17` (app
  `v0.3.0`), llama.cpp `server-b10920`, InferencePool/EPP `v1.5.0`, and model
  artifact `nomic-embed:v1.18.1-4ccc0ff`.
- `InferencePool/llm-d-pool` is accepted by agentgateway with resolved references.
  A temporary HTTPRoute targeting the InferencePool returned HTTP 200 for
  `/v1/embeddings`. EPP did not emit request logs at verbosity 1; because the pool
  is configured `FailOpen`, endpoint selection still needs metrics or tracing for
  independent proof.

### Complete after an actual run

| Evidence | Result |
|---|---|
| Codespace CPU/RAM and architecture | x86_64, 4 CPUs, 15 GiB RAM, about 8.8 GiB available |
| llama.cpp version + image digest | pending |
| GGUF SHA-256 matches | pending |
| Local POST: HTTP 200, 1024 values | pending |
| Local smoke check, 1024/256 | pending |
| Sidecar: Pod 2/2, call from client through localhost | pending |
| Recall@5 on the actual corpus, 1024/256 | pending |
| Nomic baseline POST | HTTP 200, 768 finite values, L2 norm approximately 1.0 |
| llm-d InferencePool route | HTTP 200; EPP selection evidence pending |

Replace `pending` only with an actual result and a reference to the command or
output with sensitive data removed. A prepared ToDo is not evidence of deployment.
