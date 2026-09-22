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

## B. llm-d: preparation and compatibility checks

This section is a ToDo, not a claim that llm-d is running. Assignment item 3 asks
for an ADR/ToDo. A generative model response or a successful direct call to one
vLLM Pod does not prove that the full embedding route works.

### 1. Record the environment and versions

- [ ] Read [optimized-baseline in llm-d v0.9.0](https://github.com/llm-d/llm-d/tree/v0.9.0/guides/optimized-baseline)
  and choose an appropriate CPU/GPU backend. Check the resource budget, CPU
  capabilities, and model support in the selected vLLM image. Stop the sidecar
  before starting a resource-intensive experiment.

```bash
kubectl get nodes -o wide
kubectl get nodes -o json > .lab/embeddings/nodes.json
kubectl get gatewayclass
kubectl get crd | grep -E 'gateway|inference'
lscpu
free -h
git clone --branch v0.9.0 --depth 1 https://github.com/llm-d/llm-d.git .lab/llm-d
git -C .lab/llm-d rev-parse HEAD
```

Do not clone again if the directory exists; check its HEAD instead. Record the
commit, chart versions, GAIE, proxy/EPP, vLLM image digest, and revision of the
original `Qwen/Qwen3-Embedding-0.6B`. The llm-d version alone does not pin every
external image or chart. Replace moving `main`, `nightly`, and `v0` references
from upstream examples with specific versions before deploying your configuration.

### 2. Verify the model independently of the router

- [ ] Prepare one vLLM model-server Pod in namespace `embedding-llmd-lab` for the
  available hardware, with resource requests/limits, `/health` probes, and a
  weight cache. Use the original Hugging Face weights for this runtime, not the
  Q8_0 GGUF file.
- [ ] Check `vllm serve --help` in the pinned image. The target configuration below
  defines the behavior; select the image/backend in the previous step:

```bash
# Inside the prepared vLLM environment; revision was set in step 1.
: "${VLLM_MODEL_REVISION:?Set the reviewed Hugging Face commit first}"
vllm serve Qwen/Qwen3-Embedding-0.6B \
  --revision "$VLLM_MODEL_REVISION" \
  --runner pooling \
  --served-model-name qwen3-embedding-0.6b \
  --max-model-len 2048 --host 0.0.0.0 --port 8000
```

Source: [vLLM pooling/embeddings](https://docs.vllm.ai/en/latest/models/pooling_models/embed/).
Choose dtype and CPU/GPU environment settings using the documentation for the
specific image. If it does not support the model or hardware, record a blocker
with the version and error; do not mark the task done or substitute chat completion.

- [ ] With port-forwarding on `18081:8000`, run
  `python3 scripts/verify-embeddings.py --url http://127.0.0.1:18081 --output .lab/embeddings/vllm-direct.json`.
  Verify correct last-token pooling, 1024 values, and query/document preparation.
  Connect the Router only after this succeeds.

### 3. Prepare the llm-d Router and InferencePool

- [ ] Adapt the pinned upstream guide for a **standalone Router**, a separate
  namespace, and one model server for the first experiment. Do not copy the
  example's large generative model, replica count, and GPU budget.
- [ ] Compare GAIE CRDs with the installed Gateway API/agentgateway. Check versions
  and Flux ownership. Do not blindly replace shared CRDs: if there is a conflict,
  use a separate test cluster or a coordinated upgrade.
- [ ] Install CRDs before Router/EPP and InferencePool. Ensure the pool selector
  matches model-server Pod labels and targetPort matches backend port `8000`.
- [ ] Inspect the schema of the installed version:

```bash
kubectl api-resources | grep -i inference
kubectl explain inferencepool.spec
```

- [ ] Verify proxy and EPP configuration for **`POST /v1/embeddings`**: parsing of
  `model`/`input`, the non-streaming response format, and pooling backend health
  and metrics. Select a supported policy without assuming a generative KV cache
  exists. Do not enable prefill/decode disaggregation for this experiment.
- [ ] Save adapted values/manifests and run `helm template` /
  `kubectl apply --dry-run=server` before installation. Add the version lock and
  installation commands to this ToDo once the selected combination is confirmed.

### 4. Demonstrate inference through llm-d

- [ ] Port-forward the **Router Service**, for example on `18082`, and run the same
  smoke script with `--url http://127.0.0.1:18082`.
- [ ] Compare against direct responses from the same vLLM backend: dimensions,
  values within a justified numerical tolerance, ranking, and HTTP status codes.
- [ ] Use Router/EPP logs to show which backend received the request. If resources
  permit, start a second backend and verify routing and behavior when one replica
  becomes unavailable. One successful backend verifies the route, not load balancing.
- [ ] For performance, measure full embedding request duration, throughput,
  p50/p95, CPU/RAM, and errors. Generation TTFT is not a substitute for embedding latency.
- [ ] If incompatible, record the exact version combination and observed error,
  and leave the step incomplete. Do not count an ordinary Kubernetes Service as llm-d.

### 5. Results and regular integration

- [ ] Record actual checks, versions, limitations, and status in the Changelog.
- [ ] Only after a successful experiment, package permanent charts/resources
  according to CONTRIBUTING.md, with CRDs before applications and explicit versions.
- [ ] Before OCI publication, check `flux get all`, your fork's registry, and the
  diff. `make push` publishes a release; it is not needed to run this demonstration.
- [ ] For cleanup, use the recorded resource list to delete only releases and
  Deployments created for the experiment. Do not delete shared Gateway API CRDs
  or resources belonging to the running Abox installation.
