# Agent ToDo: Sidecar and llm-d

Based on [ADR-004](../adr/004-embedding-deployment.md). Run in Bash **inside
Codespace** after [local verification](TODO-embeddings.md).
The cluster already exists; another `make run` is not required.

## A. Sidecar: a reproducible lab experiment

- [ ] Stop the local server with `docker stop abox-embeddings` to avoid keeping
  two models in memory. Check `kubectl config current-context`: the commands below
  must target the Abox lab cluster.
- [ ] Insert the verified image digest into the template.

```bash
python3 - <<'PY'
from pathlib import Path
import re
image = Path('.lab/embeddings/llama-image.txt').read_text().strip()
if not re.fullmatch(r'ghcr\.io/ggml-org/llama\.cpp@sha256:[0-9a-f]{64}', image):
    raise SystemExit('Expected the llama.cpp digest saved by the local run')
template = Path('docs/examples/embeddings-sidecar.yaml.template').read_text()
Path('.lab/embeddings/sidecar.yaml').write_text(template.replace('__LLAMA_IMAGE__', image))
PY
```

This does not silently download a new runtime version. The init container
separately downloads the same GGUF at the pinned revision and checks SHA-256;
it needs outbound HTTPS access. The first startup takes longer because it must
download approximately 639 MB of weights as well as container images.

- [ ] Apply the demonstration and wait for both containers to become ready.

```bash
kubectl apply --dry-run=client -f .lab/embeddings/sidecar.yaml
kubectl apply -f .lab/embeddings/sidecar.yaml
kubectl -n embedding-lab rollout status deployment/embedding-sidecar --timeout=600s
kubectl -n embedding-lab get pods -l app=embedding-sidecar
kubectl -n embedding-lab logs deployment/embedding-sidecar -c download-model
```

Expect `2/2 Running`, a successful rollout, and a log message confirming SHA-256
verification. Readiness does not prove successful embedding inference; perform
the next step.

- [ ] Call the model **from the client container in the same Pod**.

```bash
set -o pipefail
kubectl -n embedding-lab exec -i deployment/embedding-sidecar -c client -- \
  python - --url http://127.0.0.1:8080 \
  < scripts/verify-embeddings.py | tee .lab/embeddings/sidecar-check.json
```

This is the key evidence for the sidecar: the HTTP request uses the Pod's shared
network. `pipefail` preserves a verification failure even if `tee` succeeds.
Acceptance criteria: exit code 0, 1024 original values, 256 after transformation,
and successful cross-language examples. The script does not create a Qdrant collection.

- [ ] If needed, call the same endpoint from the Codespace terminal.

```bash
kubectl -n embedding-lab port-forward deployment/embedding-sidecar 8081:8080
```

Leave this command running. In a second terminal, repeat the local check with
`--url http://127.0.0.1:8081`. No Service is needed here. Other Pods do not
automatically gain access to the sidecar API; sharing the model requires a
separate Service architecture.

- [ ] Record the digest, checksum, Pod status, verification logs, and measured
  resources in the Changelog. For CPU/RAM, use `kubectl top pod -n embedding-lab`
  if Metrics Server is installed; its absence does not indicate a model failure.

If the Pod is not ready:

```bash
kubectl -n embedding-lab describe pods -l app=embedding-sidecar
kubectl -n embedding-lab logs deployment/embedding-sidecar -c embeddings --tail=100
kubectl -n embedding-lab get events --sort-by=.metadata.creationTimestamp
```

`Pending` often indicates insufficient resources; `ImagePullBackOff` indicates an
image download problem; init failures may indicate download/checksum problems;
`OOMKilled` indicates a memory limit was exceeded. The startup probe begins after
the init download; the rollout timeout also includes download time.

Remove **only this experiment** when it is no longer needed:

```bash
kubectl -n embedding-lab delete deployment embedding-sidecar
```

This deletes the Pod and its model in `emptyDir`. The namespace remains; the
command does not target Abox components.

## B. llm-d: inspect and verify the existing deployment

The course cluster already contains a Nomic/llama.cpp llm-d deployment. Treat it
as a baseline for understanding the architecture. It does not deploy the selected
multilingual Qwen model.

### 1. Record resources and version locks

- [x] Confirm the cluster, model server, InferencePool, and EPP are Ready.
- [x] Record the chart and image versions shown in ADR-004.
- [ ] Record immutable image digests in addition to tags.

```bash
helm list -A | grep -E 'llama|llm-d|inference' || true
kubectl -n llm-d get deployment,service,pod -o wide
kubectl -n llm-d get inferencepool llm-d-pool -o yaml
kubectl -n llm-d get httproute llm-d-embedding -o yaml
kubectl -n llm-d get pods \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{range .status.containerStatuses[*]}{.imageID}{"\n"}{end}{end}'
```

The model server uses `ghcr.io/ggml-org/llama.cpp:server-b10920`. Model weights
come from the image volume `nomic-embed:v1.18.1-4ccc0ff`, mounted read-only at
`/model-cache`. The InferencePool selects Pods labelled
`llm-d.ai/model: nomic-embed-text-v1-5` and sends traffic to port 8000.

### 2. Verify the direct Nomic backend

- [x] Verify `/health`.
- [x] Call `/v1/embeddings` and confirm 768 finite values with L2 norm close to 1.

The verified direct request used the Nomic retrieval prefix:

```bash
curl --fail --silent --show-error http://127.0.0.1:18090/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "nomic-embed-text-v1.5",
    "input": "search_query: How does Qdrant store vectors?",
    "encoding_format": "float"
  }' > /tmp/nomic-embedding.json
```

Do not use `scripts/verify-embeddings.py` for this baseline: that script implements
the Qwen contract (1024 dimensions, last-token pooling, and Qwen instructions).

### 3. Understand the two Gateway paths

The existing HTTPRoute has two rules:

- `/llmd/v1/embeddings` rewrites to `/v1/embeddings` and uses the Service directly.
- `/llmd/*` uses `InferencePool/llm-d-pool`.

Because the first match is more specific, this request verifies agentgateway and
the model Service but bypasses EPP:

```bash
GATEWAY_IP="$(kubectl -n agentgateway-system get gateway \
  agentgateway-external -o jsonpath='{.status.addresses[0].value}')"
curl --fail --silent --show-error \
  "http://${GATEWAY_IP}/llmd/v1/embeddings" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "nomic-embed-text-v1.5",
    "input": "search_query: How does Qdrant store vectors?",
    "encoding_format": "float"
  }' > /tmp/llmd-direct-embedding.json
```

This path returned HTTP 200 and the expected 768-dimensional normalized vector.

### 4. Verify the InferencePool path

- [x] Create a temporary HTTPRoute with a non-overlapping prefix,
  `/llmd-pool/v1/embeddings`, and an InferencePool backend.
- [x] Confirm `Accepted=True` and `ResolvedRefs=True`.
- [x] Receive HTTP 200 and an embedding response through that path.
- [ ] Obtain independent evidence of EPP endpoint selection.

The EPP runs at verbosity 1 and produced no per-request log. The pool also uses
`failureMode: FailOpen`; therefore, HTTP 200 proves that the InferencePool data
path works, but it does not by itself prove the EPP scheduling decision.

For additional evidence, expose the EPP metrics port in one terminal:

```bash
kubectl -n llm-d port-forward service/llm-d-pool-epp 19090:9090
```

In another terminal, capture relevant counters before and after one request:

```bash
curl --fail --silent http://127.0.0.1:19090/metrics \
  | grep -Ei 'request|endpoint|pick|schedule|ext_proc' \
  > /tmp/epp-metrics-before.txt

curl --fail --silent --show-error \
  "http://${GATEWAY_IP}/llmd-pool/v1/embeddings" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "nomic-embed-text-v1.5",
    "input": "search_query: How does Qdrant store vectors?",
    "encoding_format": "float"
  }' > /tmp/llmd-pool-embedding.json

curl --fail --silent http://127.0.0.1:19090/metrics \
  | grep -Ei 'request|endpoint|pick|schedule|ext_proc' \
  > /tmp/epp-metrics-after.txt
diff -u /tmp/epp-metrics-before.txt /tmp/epp-metrics-after.txt || true
```

If the exposed metrics do not provide request-level evidence, temporarily raise
EPP verbosity or enable tracing through the version-controlled Helm values. Do
not edit the Flux-managed Deployment directly and present the result as durable.

After evidence has been saved, remove only the temporary route:

```bash
kubectl -n llm-d delete httproute llm-d-embedding-pool-test
```

Do not delete the course-managed `llm-d-embedding` route, InferencePool, shared
Gateway API CRDs, or llm-d Helm releases.

### 5. Adapt the architecture for Qwen

- [ ] Resolve the low disk-space condition before downloading Qwen.
- [ ] Package Qwen weights as a pinned model artifact or use another reproducible
  storage method. Keep runtime and model artifact versions explicit.
- [ ] Use a new model label, route identity, and Qdrant collection. Do not reuse
  the Nomic collection or its 768-dimensional schema.
- [ ] Run `scripts/verify-embeddings.py` directly against Qwen, then through its
  Gateway Service path, and finally through a non-overlapping InferencePool path.
- [ ] Measure Recall@5 for 1024 and 256 dimensions before accepting truncation.
- [ ] Record actual results and limitations in the Changelog.

Only after a successful experiment should permanent resources be added according
to CONTRIBUTING.md, with CRDs before applications and explicit versions. Before
OCI publication, verify `flux get all`, the registry for your fork, and the diff.
