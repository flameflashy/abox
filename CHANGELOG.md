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

- The owner reports that Abox infrastructure is already running in Codespace.
- Documents and the example were prepared in the local working copy. This session
  has not started the model in Codespace or deployed the sidecar or llm-d in the cluster.
- The runtime image digest will be pinned on the first run. Actual inference speed,
  RAM usage, and quality have not been measured yet.
- The Qdrant collection and application integration have not been created yet.

### Verified locally

- The Python script compiles. Synthetic HTTP responses verified 1024/256 processing
  and rejection of incorrect dimensions, NaN/Infinity, zero norms, and boolean values.
- `bash -n` successfully checked all 15 Bash instruction blocks.
- The sidecar template with a test placeholder digest was parsed by
  `kubectl kustomize`; this checks YAML structure, not server-side validation or
  container execution.
- Local Markdown links and `git diff --check` passed verification.

### Complete after an actual run

| Evidence | Result |
|---|---|
| Codespace CPU/RAM and architecture | pending |
| llama.cpp version + image digest | pending |
| GGUF SHA-256 matches | pending |
| Local POST: HTTP 200, 1024 values | pending |
| Local smoke check, 1024/256 | pending |
| Sidecar: Pod 2/2, call from client through localhost | pending |
| Recall@5 on the actual corpus, 1024/256 | pending |
| llm-d: version lock, backend API, Router API, or a specific blocker | pending |

Replace `pending` only with an actual result and a reference to the command or
output with sensitive data removed. A prepared ToDo is not evidence of deployment.
