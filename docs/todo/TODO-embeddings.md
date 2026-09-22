# Agent ToDo: Local Embedding Model in Codespace

Based on [ADR-003](../adr/003-embedding-model.md). Run all commands in **Bash in
the Linux terminal of Codespace**, from the Abox repository root. Here, local
means inside Codespace, outside Kubernetes. First transfer changes from the
Windows checkout to Codespace using your usual workflow; these working directories
do not synchronize automatically.

Follow the blocks in order. If a command fails, stop and inspect the output.
Written instructions do not mean the model is running.

## 1. Check the environment

- [ ] Check available resources and the state of the existing Abox installation.

```bash
mkdir -p .lab/embeddings/models
uname -m
nproc
free -h
df -h .
docker version
python3 --version
kubectl config current-context
kubectl get nodes
kubectl get pods -A
```

Docker, curl, sha256sum, and Python 3 are required. The initial server budget is
up to 2 CPUs and 3 GiB RAM, in addition to Abox resources. These are experimental
limits, not measured requirements. If free memory is low, review the budget first.

## 2. Download weights and pin the runtime

- [ ] Download the selected GGUF and verify its SHA-256.

```bash
curl --fail --location --retry 3 \
  'https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF/resolve/370f27d7550e0def9b39c1f16d3fbaa13aa67728/Qwen3-Embedding-0.6B-Q8_0.gguf' \
  --output .lab/embeddings/models/Qwen3-Embedding-0.6B-Q8_0.gguf
echo '06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439  .lab/embeddings/models/Qwen3-Embedding-0.6B-Q8_0.gguf' | sha256sum --check
```

GGUF contains weights and metadata. Do not continue if the SHA-256 does not match.

- [ ] Pull the official CPU image and save its immutable digest.

```bash
docker pull ghcr.io/ggml-org/llama.cpp:server
export LLAMA_IMAGE="$(docker image inspect ghcr.io/ggml-org/llama.cpp:server --format '{{index .RepoDigests 0}}')"
test -n "$LLAMA_IMAGE"
printf '%s\n' "$LLAMA_IMAGE" | tee .lab/embeddings/llama-image.txt
docker run --rm "$LLAMA_IMAGE" --version
```

`server` is a moving channel used for the initial download. After that, use the
saved `...@sha256:...`, including for the sidecar. To repeat the experiment, read
the saved digest instead of pulling again. The specific runtime is not pinned
until the first run.
Source: [llama.cpp Docker](https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md).

## 3. Start the server in a separate terminal

- [ ] Wait for the model to load.

```bash
export LLAMA_IMAGE="$(cat .lab/embeddings/llama-image.txt)"
docker run --rm --name abox-embeddings \
  --cpus 2 --memory 3g \
  -p 127.0.0.1:8081:8080 \
  -v "$PWD/.lab/embeddings/models:/models:ro" \
  "$LLAMA_IMAGE" \
  --model /models/Qwen3-Embedding-0.6B-Q8_0.gguf \
  --alias qwen3-embedding-0.6b \
  --embedding --pooling last \
  --ctx-size 2048 --batch-size 2048 --ubatch-size 2048 \
  --parallel 1 --threads 2 --n-gpu-layers 0 \
  --host 0.0.0.0 --port 8080
```

`--embedding` enables vector output; `--pooling last` selects the representation
of the last token. `--parallel 1` simplifies the CPU experiment. Host port `8081`
forwards to container port `8080`. Bind to `0.0.0.0` inside the container, but
publish only on `127.0.0.1` on the host. If forwarding the port through Codespaces,
keep its visibility Private.

## 4. Verify availability from a second terminal

- [ ] Check health and obtain an actual embedding response.

```bash
curl --fail --silent --show-error http://127.0.0.1:8081/health
curl --fail --silent --show-error http://127.0.0.1:8081/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3-embedding-0.6b","input":"Instruct: Retrieve relevant technical documentation.\nQuery:How does search in Qdrant work?","encoding_format":"float"}' \
  > .lab/embeddings/response.json
python3 -c 'import json; r=json.load(open(".lab/embeddings/response.json")); print("dimensions:", len(r["data"][0]["embedding"]))'
```

Expect HTTP 200 and **1024** numbers. A health check does not replace a POST request
to the model.
[Endpoint documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md#post-v1embeddings-openai-compatible-embeddings-api).

- [ ] Verify both dimensions and retrieval across three languages.

```bash
python3 scripts/verify-embeddings.py --url http://127.0.0.1:8081 \
  --output .lab/embeddings/local-check.json
```

The script validates vector length and numeric values, truncates and normalizes
vectors, and compares cosine similarity. Exit code 0 means the small smoke set
passed; it is not a full corpus evaluation. Investigate top-1 mismatches rather
than hiding them.

## 5. Record results and continue

- [ ] Add the actual image digest, `--version`, model revision, SHA-256, CPU/RAM,
  commands, and verification results to the [Changelog](../../CHANGELOG.md).
- [ ] Evaluate 30 queries as specified in ADR-003; compare Recall@5 for 1024 and 256.
- [ ] Release memory before running the sidecar: `docker stop abox-embeddings`.
- [ ] Continue with the [cluster instructions](TODO-embedding-deployment.md).

`.lab/` is excluded from Git; copy a useful summary without sensitive data into the Changelog.

| Client location | Address |
|---|---|
| Codespace terminal, Docker deployment | `http://127.0.0.1:8081/v1/embeddings` |
| Neighboring container in the same Pod | `http://127.0.0.1:8080/v1/embeddings` |
| Another Pod | Requires a separate Service and a server reachable at its Pod IP |

`localhost` in another Pod does not point to Codespace or the model's Pod.
Configuring a chat model in kagent does not connect an embedding model.

## Troubleshooting

- Connection refused: inspect `docker logs abox-embeddings` and wait for loading.
- Port already in use: choose another host port and update the check's `--url`.
- OOM/exit 137: check memory on the entire machine; reduce context or increase the
  available budget, then repeat verification.
- Unknown option or wrong dimensions: save the version and logs, then check the
  contract; do not accept an invalid response as success.
- Weights download on the host but not in KinD: check DNS/egress. The repository
  includes `make fix-egress`; read what it does before using it.
