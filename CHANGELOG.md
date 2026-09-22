# Changelog

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
