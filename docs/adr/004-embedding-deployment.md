# ADR-004: Embeddings as a Sidecar and Through llm-d

## Status

The sidecar approach is accepted as the next lab experiment and has not been
deployed. An existing Nomic/llama.cpp llm-d deployment was inspected and tested
on 2026-09-22. Qwen deployment through llm-d remains future work.
We interpret `llmd` in the assignment as the [llm-d](https://llm-d.ai/) project.
The model and text preparation are defined in [ADR-003](003-embedding-model.md).

## Context

Abox runs in KinD inside Codespace. It includes agentgateway, kagent, Qdrant,
Flux, a standalone Nomic llama.cpp server, and a separate Nomic llm-d deployment.
Assignment item 3 requires an ADR/ToDo for sidecar and llm-d approaches.

## Decision: start with a sidecar

```text
Pod embedding-lab
  client (lab HTTP client) ---> localhost:8080 ---> llama-server
  initContainer download-model ---> shared emptyDir containing the GGUF
```

A sidecar is a supporting container in **the same Pod**, so the client calls it
through localhost. It is not a separate Deployment behind a Service or the Qdrant
container. The lab client stands in for a future application; the demonstration
does not require changes to kagent.

The [template](../examples/embeddings-sidecar.yaml.template) uses a conventional
multi-container layout: client and llama-server are listed under `containers`.
This is the sidecar pattern, not the Kubernetes native sidecar mechanism using
`initContainers[].restartPolicy: Always`. Both approaches are described in the
[Kubernetes documentation](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/).
Startup order for ordinary containers is not guaranteed; wait for readiness before calling the model.

Use the same GGUF, checksum, and llama.cpp image digest as in the local experiment.
The init container downloads and verifies the model. `emptyDir` survives container
restarts but is lost when the Pod is replaced; downloading again is acceptable
for this lab. Regular operation would require a separate choice of PVC storage
or an image containing the weights.

The server has startup, readiness, and liveness probes, plus resource requests
and limits. Limits are an initial budget to adjust using measurements. Scaling
the application also duplicates the model weights and resource usage; the model
cannot scale independently of the client. The benefit is a simple call without
a separate Service. The drawback is a shared lifecycle and model cost per Pod.

## Decision: llm-d as a separate inference pool

```text
client ---> llm-d Router (proxy + EPP) ---> InferencePool ---> model-server Pods
```

The [llm-d architecture](https://llm-d.ai/docs/architecture) separates routing,
model-server Pod selection, and model execution. llm-d does not replace the runtime.
The inspected deployment uses llama.cpp as that runtime:

| Component | Observed version/configuration |
|---|---|
| ModelService chart | `llm-d-modelservice-v0.3.17`, app `v0.3.0` |
| Model server | `ghcr.io/ggml-org/llama.cpp:server-b10920` |
| Model artifact | `ghcr.io/den-vasyliev/abox/nomic-embed:v1.18.1-4ccc0ff` |
| Model storage | Kubernetes image volume mounted read-only at `/model-cache` |
| InferencePool chart | `inferencepool-1.5.0+bc6b00e127fe`, app `v1.5.0` |
| Endpoint picker | `registry.k8s.io/gateway-api-inference-extension/epp:v1.5.0` |
| Pool selector | `llm-d.ai/model: nomic-embed-text-v1-5` |
| Backend port | `8000` |

The model artifact image supplies weights independently from the llama.cpp runtime
image. This avoids downloading weights in an init container and allows the model
artifact and runtime to be versioned separately.

The existing HTTPRoute exposes two distinct paths:

| External path | Backend | Meaning |
|---|---|---|
| `/llmd/v1/embeddings` | Service `llm-d-embedding` | Rewrites to `/v1/embeddings` and bypasses InferencePool/EPP |
| `/llmd/*` | InferencePool `llm-d-pool` | Uses the InferencePool path and its endpoint picker |

Because the first path is a more specific match, ordinary embedding requests use
the Service directly. A temporary route pointing `/llmd-pool/v1/embeddings` at
the InferencePool was accepted with resolved references and returned HTTP 200
with an embedding response. The EPP runs with log verbosity 1 and emitted no
request log. Since the pool uses `failureMode: FailOpen`, that test proves the
InferencePool data path is functional but does not independently prove which
endpoint-selection decision the EPP made. Metrics or higher-verbosity tracing
are required for that stronger claim.

Embedding requests do not generate a sequence of new tokens. Do not enable
prefill/decode disaggregation or assume that generative KV-cache policies improve
this workload. The deployed resource calls its only model-server role `decode`
because of chart conventions; this does not turn embedding inference into a
decode-stage workload.

The running Nomic path is the deployment baseline. The selected multilingual
Qwen model must use a separate model identity and vector index. Do not mix Nomic
and Qwen vectors or compare them as if they shared one embedding space.

## Abox integration and consequences

Apply the demonstration from `docs/examples` explicitly; it is not yet included
in `releases/kustomization.yaml`. This allows the lab experiment to be tested
separately. After a successful experiment, package a regular component according
to Abox conventions: CRDs before applications, explicit chart/image versions,
observability, and all resources reported as Ready by `flux get all`.

Flux reads OCI artifacts, not automatically updated Git files. Adding local YAML
does not change the cluster. Before publishing, check the actual `oci_registry`:
the bootstrap default points to upstream, not the student's fork.

The installed InferencePool reports `Accepted=True` and `ResolvedRefs=True` under
the existing agentgateway. Do not replace shared Gateway API or Inference Extension
CRDs without checking Flux ownership and compatibility. Any Qwen experiment must
use explicit versions and a separate model/index identity.

Criteria and commands: [deployment ToDo](../todo/TODO-embedding-deployment.md).
