# ADR-004: Embeddings as a Sidecar and Through llm-d

## Status

The sidecar approach is accepted as the next lab experiment. llm-d is a proposed
plan subject to compatibility checks; it has not been deployed.
We interpret `llmd` in the assignment as the [llm-d](https://llm-d.ai/) project.
The model and text preparation are defined in [ADR-003](003-embedding-model.md).

## Context

Abox already runs in KinD inside Codespace. It includes agentgateway, kagent,
Qdrant, and Flux; these components do not imply an embedding server is present.
Assignment item 3 requires an ADR/ToDo for two deployment approaches.

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
For the experiment, plan to use vLLM with the original Qwen3-Embedding-0.6B in
pooling mode, rather than passing our GGUF to an arbitrary vLLM image.

vLLM provides a pooling/embeddings API, but this **does not prove** that the selected
llm-d Router/EPP version can serve `/v1/embeddings` with the required configuration.
Check two boundaries separately: the direct backend endpoint and requests through
the Router. Source: [vLLM embeddings](https://docs.vllm.ai/en/latest/models/pooling_models/embed/).

The plan builds on [llm-d v0.9.0 optimized-baseline](https://github.com/llm-d/llm-d/tree/v0.9.0/guides/optimized-baseline).
This is a starting point for adaptation, not a ready-made embedding recipe. Its
default large generative model and replica/GPU budget do not suit a small Codespace.
A CPU example does not guarantee support for every CPU machine: first check
processor instructions, the image, and available memory.

Embedding requests do not generate a sequence of new tokens. Therefore, do not
enable prefill/decode disaggregation or assume that generative KV-cache policies
will help. Choose a routing policy that supports the pooling backend and its
available metrics. If incompatible, record the specific blocker; an ordinary
Service in front of llama.cpp is not a working llm-d deployment.

Different runtimes and precision levels can produce different vectors. First
compare direct vLLM access with llm-d using the same vLLM backend, then separately
compare with GGUF/llama.cpp. Use a separate index for this experiment; do not mix
its vectors into an existing index.

## Abox integration and consequences

Apply the demonstration from `docs/examples` explicitly; it is not yet included
in `releases/kustomization.yaml`. This allows the lab experiment to be tested
separately. After a successful experiment, package a regular component according
to Abox conventions: CRDs before applications, explicit chart/image versions,
observability, and all resources reported as Ready by `flux get all`.

Flux reads OCI artifacts, not automatically updated Git files. Adding local YAML
does not change the cluster. Before publishing, check the actual `oci_registry`:
the bootstrap default points to upstream, not the student's fork.

For llm-d, start with a separate namespace and verify Gateway API/GAIE compatibility
with the installed agentgateway. Do not blindly replace existing shared CRDs.
A standalone Router allows the experiment to start without changing Abox's existing ingress.

Criteria and commands: [deployment ToDo](../todo/TODO-embedding-deployment.md).
