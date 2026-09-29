# ToDo: Run the Agentic Retrieval Comparison

This runbook implements Laboratory 4 without mixing the MiniLM and Nomic vector
spaces. Run all commands from the Abox repository in the Codespace.

## 1. Verify the release and cluster baseline

The release URL must end in `releases-llmd-embeddings`. Pod names alone do not
prove which OCI artifact Flux reconciled.

```bash
kubectl -n flux-system get ocirepository releases \
  -o jsonpath='{.spec.url}{"\n"}{.spec.ref.tag}{"\n"}{.status.artifact.revision}{"\n"}'

kubectl get pods -A
kubectl -n kagent get agent,mcpserver,modelconfig
kubectl -n qdrant get statefulset,pod,service
kubectl -n llm-d get deployment,pod,inferencepool
```

Expected OCI repository:

```text
oci://ghcr.io/den-vasyliev/abox/releases-llmd-embeddings
```

Record the actual tag and revision in the ADR results notes.

If the cluster still reports `oci://ghcr.io/den-vasyliev/abox/releases`, switch
all three levels of the GitOps configuration. The input provider discovers the
branch tags, the ResourceSet template defines the generated source URL, and the
OCIRepository is patched immediately so the change does not wait for the next
five-minute provider poll.

Inspect the ResourceSet first. Its first rendered resource must be the
`OCIRepository/releases` object:

```bash
kubectl -n flux-system get resourceset releases \
  -o jsonpath='{range .spec.resources[*]}{.kind}{" => "}{.spec.url}{"\n"}{end}'
```

Then switch to the feature release:

```bash
RELEASE_URL='oci://ghcr.io/den-vasyliev/abox/releases-llmd-embeddings'

kubectl -n flux-system patch resourcesetinputprovider releases-image \
  --type=merge \
  -p "{\"spec\":{\"url\":\"${RELEASE_URL}\",\"defaultValues\":{\"tag\":\"0.9.5\"}}}"

kubectl -n flux-system patch resourceset releases \
  --type=json \
  -p "[{\"op\":\"replace\",\"path\":\"/spec/resources/0/spec/url\",\"value\":\"${RELEASE_URL}\"}]"

kubectl -n flux-system patch ocirepository releases \
  --type=merge \
  -p "{\"spec\":{\"url\":\"${RELEASE_URL}\",\"ref\":{\"tag\":\"0.9.5\"}}}"

SOURCE_REQUEST="$(date -u +%s)-source"
kubectl -n flux-system annotate ocirepository releases \
  reconcile.fluxcd.io/requestedAt="${SOURCE_REQUEST}" --overwrite
kubectl -n flux-system wait ocirepository/releases \
  --for="jsonpath={.status.lastHandledReconcileAt}=${SOURCE_REQUEST}" \
  --timeout=5m
kubectl -n flux-system wait ocirepository/releases \
  --for=condition=Ready=True --timeout=5m

CRDS_REQUEST="$(date -u +%s)-crds"
kubectl -n flux-system annotate kustomization releases-crds \
  reconcile.fluxcd.io/requestedAt="${CRDS_REQUEST}" --overwrite
kubectl -n flux-system wait kustomization/releases-crds \
  --for="jsonpath={.status.lastHandledReconcileAt}=${CRDS_REQUEST}" \
  --timeout=10m
kubectl -n flux-system wait kustomization/releases-crds \
  --for=condition=Ready=True --timeout=10m

RELEASE_REQUEST="$(date -u +%s)-release"
kubectl -n flux-system annotate kustomization releases \
  reconcile.fluxcd.io/requestedAt="${RELEASE_REQUEST}" --overwrite
kubectl -n flux-system wait kustomization/releases \
  --for="jsonpath={.status.lastHandledReconcileAt}=${RELEASE_REQUEST}" \
  --timeout=10m
kubectl -n flux-system wait kustomization/releases \
  --for=condition=Ready=True --timeout=10m
```

Wait for reconciliation and verify that the source URL, tag, revision, and both
Kustomizations are ready:

```bash
kubectl -n flux-system get ocirepository releases \
  -o jsonpath='{.spec.url}{"\n"}{.spec.ref.tag}{"\n"}{.status.artifact.revision}{"\n"}'

kubectl -n flux-system get ocirepository releases
kubectl -n flux-system get kustomization releases-crds releases
kubectl get pods -A
```

The switch is reversible by setting the three URLs back to
`oci://ghcr.io/den-vasyliev/abox/releases`, the input provider fallback tag back
to the desired main release, and the child tag to the same value. Do not run
`tofu apply` from the old main checkout during the experiment because its
bootstrap configuration hardcodes the main artifact and would revert these
objects.

## 2. Verify the agent model configuration

`default-model-config` is the reasoning/chat model. It is independent from the
MiniLM and Nomic embedding models.

```bash
kubectl -n kagent get agent retrieval-agent k8s-agent \
  -o custom-columns='NAME:.metadata.name,MODEL_CONFIG:.spec.declarative.modelConfig,READY:.status.conditions[?(@.type=="Ready")].status'

kubectl -n kagent get modelconfig default-model-config -o yaml
```

Both agents must reference `default-model-config`. If `k8s-agent` does not, make
the model selection explicit:

```bash
kubectl -n kagent patch agent k8s-agent --type=merge \
  -p '{"spec":{"declarative":{"modelConfig":"default-model-config"}}}'
```

Re-run the first command and record the result. Do not point an Agent at llm-d's
Nomic endpoint: that endpoint produces embeddings and has no generation head.

`Ready` or `Accepted` validates the Kubernetes configuration; it does not make
an authenticated request to the model provider. Inspect the Secret reference
without printing its value:

```bash
kubectl -n kagent get modelconfig default-model-config \
  -o jsonpath='{.spec.provider}{"\n"}{.spec.model}{"\n"}{.spec.apiKeySecret}{"\n"}{.spec.apiKeySecretKey}{"\n"}'
```

For the OpenAI configuration shipped by release 0.9.5, the last two lines must
be `kagent-openai` and `OPENAI_API_KEY`. A 401 error that masks the supplied key
as `OPENAI_A***_KEY` means the chart's literal development placeholder reached
the provider. If the ModelConfig is absent, create it in the kagent UI with the
name `default-model-config`, provider `OpenAI`, model `gpt-4.1-mini`, and a real
API key. Keep this exact name because both lab Agent manifests reference it.

Alternatively, when the ModelConfig and its Secret reference already exist,
replace only the live Secret by entering the real key silently:

```bash
read -rsp 'OpenAI API key: ' KAGENT_OPENAI_KEY
echo

printf 'OPENAI_API_KEY=%s\n' "$KAGENT_OPENAI_KEY" | \
  kubectl -n kagent create secret generic kagent-openai \
    --from-env-file=/dev/stdin \
    --dry-run=client -o yaml | \
  kubectl apply -f -

unset KAGENT_OPENAI_KEY
```

The pipeline sends the generated Secret manifest directly to the API server;
it does not print the key. Do not paste the key or decoded Secret into the lab
records. Restart the generated agent Deployments so processes that loaded the
old Secret value at startup receive the new value:

```bash
while read -r deployment; do
  [ -z "$deployment" ] && continue
  kubectl -n kagent rollout restart "$deployment"
  kubectl -n kagent rollout status "$deployment" --timeout=5m
done < <(
  kubectl -n kagent get deployment -o name | \
    grep -E '(k8s-agent|retrieval-agent)' || true
)
```

Open a new chat session and send a simple message to `kagent/k8s-agent`. A new
session avoids reusing runtime state created with the invalid credential.

This live Secret update is suitable for the lab. A Helm upgrade can restore the
placeholder because the published release sets `providers.openAI.apiKey`
inline. A durable environment must remove that inline value, reference a Secret
created outside the chart, and populate it with a secret manager or another
out-of-band mechanism.

## 3. Pause GitOps while switching the experiment manifests

The release owns `retrieval-agent`. Flux can otherwise restore the release
version during the test.

```bash
kubectl -n flux-system patch kustomization releases \
  --type=merge -p '{"spec":{"suspend":true}}'
kubectl -n flux-system get kustomization releases \
  -o custom-columns='NAME:.metadata.name,SUSPENDED:.spec.suspend,READY:.status.conditions[?(@.type=="Ready")].status,REVISION:.status.lastAppliedRevision'
```

Resume it after the experiment in step 11.

## 4. Deploy the fixed corpus and official Qdrant MCP

```bash
kubectl apply -f docs/examples/lab4/retrieval-corpus.yaml
kubectl apply -f docs/examples/lab4/qdrant-official-mcp.yaml

kubectl -n kagent get mcpserver qdrant-official-mcp -w
```

Stop the watch after the server is Ready. Then inspect the generated workload:

```bash
kubectl -n kagent get deployment,pod,service \
  -l app.kubernetes.io/instance=qdrant-official-mcp -o wide

kubectl -n kagent describe mcpserver qdrant-official-mcp
kubectl -n kagent logs deployment/qdrant-official-mcp --all-containers --tail=200
```

If the label selector returns no objects, list the namespace and use the exact
generated Deployment name:

```bash
kubectl -n kagent get deployment,pod,service | grep qdrant-official
```

The first start downloads the pinned Python package. The official server creates
its FastEmbed `TextEmbedding` provider during startup, so the Pod may remain
unready while `sentence-transformers/all-MiniLM-L6-v2` is downloaded.

## 5. Attach the official MCP tools and prompt

```bash
kubectl apply -f docs/examples/lab4/retrieval-agent-official.yaml

kubectl -n kagent get agent retrieval-agent -o jsonpath='{.spec.declarative.modelConfig}{"\n"}'
kubectl -n kagent get agent retrieval-agent -o jsonpath='{range .spec.declarative.tools[*]}{.mcpServer.name}{" => "}{.mcpServer.toolNames}{"\n"}{end}'
kubectl -n kagent describe agent retrieval-agent
```

Expected vector toolset:

```text
qdrant-official-mcp => [qdrant-store qdrant-find]
```

The system prompt permits delegation to `k8s-agent` only during ingestion and
requires `qdrant-find` during retrieval.

## 6. Index with MiniLM through the official MCP

Open a new `retrieval-agent` chat in the kagent UI and send this exact request:

```text
Ingest the evaluation corpus from ConfigMap kagent/agentic-retrieval-corpus exactly as your system instructions specify. Call qdrant-store strictly one at a time in DOC-01 through DOC-08 order, waiting for each result before starting the next call. Never issue parallel tool calls. Stop on the first error. Report every stored doc_id and the number of successful qdrant-store calls.
```

The trace must show one delegation to `k8s-agent` and eight `qdrant-store`
calls. The sequential requirement avoids a first-write race in the official
server's automatic collection creation. If a failed attempt partially populated
the dedicated collection, delete only `lab4-minilm` before retrying so duplicate
points cannot contaminate the comparison:

```bash
kubectl -n qdrant port-forward service/qdrant 6333:6333 >/tmp/qdrant-port-forward.log 2>&1 &
QDRANT_PF_PID=$!

curl --fail --silent -X DELETE \
  http://127.0.0.1:6333/collections/lab4-minilm \
  | python3 -m json.tool
```

Open a new chat after reapplying the Agent manifest and repeat the request. Then
verify the collection independently:

```bash
curl --fail --silent http://127.0.0.1:6333/collections/lab4-minilm | \
python3 -c '
import json, sys
response = json.load(sys.stdin)
result = response["result"]
vectors = result["config"]["params"]["vectors"]
named_vectors = {"default": vectors} if "size" in vectors else vectors
print("status:", response["status"])
for name, config in named_vectors.items():
    print("vector_name:", name)
    print("vector_size:", config["size"])
    print("distance:", config["distance"])
print("reported_points_count:", result["points_count"])
'

curl --fail --silent \
  'http://127.0.0.1:6333/collections/lab4-minilm/points/count' \
  -H 'Content-Type: application/json' \
  -d '{"exact":true}' | python3 -m json.tool

curl --fail --silent \
  'http://127.0.0.1:6333/collections/lab4-minilm/points/scroll' \
  -H 'Content-Type: application/json' \
  -d '{"limit":100,"with_payload":true,"with_vector":false}' | \
python3 -c '
import json, sys
points = json.load(sys.stdin)["result"]["points"]
doc_ids = sorted(point["payload"]["metadata"]["doc_id"] for point in points)
print("stored_doc_ids:", *doc_ids, sep="\n  ")
print("unique_doc_ids:", len(set(doc_ids)))
'
```

The official server uses a named vector, so the vector configuration is a map
whose value contains `size` and `distance`. Expected evidence is vector size
384, exactly eight points, and eight unique document IDs. Keep the port forward
running for later checks.

If the exact count is nine but there are eight unique IDs because the partial
attempt's `DOC-08-inference-pool` survived, remove one copy only after verifying
that the two complete payloads are identical. The cleanup script in the
experiment notes must abort for any other shape; do not start retrieval with a
duplicate because it can occupy two of the five returned result slots.

## 7. Run the official-MCP retrieval queries

Use `docs/examples/lab4/evaluation-queries.tsv`. Start a new chat for each query
so earlier answers do not influence later ones. Prefix each query with:

```text
This is a retrieval-only evaluation. Search the indexed corpus, answer only from the retrieved documents, and list the returned doc_id values in order.
```

Record the tool trace, ordered IDs, answer, and elapsed time in ADR-005. Do not
correct the agent or retry a failed query silently; record the failure first.
Add one tab-separated row to `evaluation-results.tsv` after each run. For
example:

```text
official	Q01	qdrant-find	DOC-01-qdrant-storage,DOC-07-abox-qdrant-mcp	1	0	3.42
```

The columns mean: configuration, query ID, tool observed in the trace, returned
document IDs in tool order, whether every answer claim is grounded (`1` or
`0`), number of unsupported factual claims, and elapsed seconds. The example is
only a format illustration; record the actual trace and latency.

## 8. Switch to the Abox MCP toolset

The release's `qdrant-mcp` uses Nomic through llama.cpp and stores in
`abox-nomic`. Check whether the collection already contains unrelated data:

```bash
curl --silent http://127.0.0.1:6333/collections/abox-nomic \
  | python3 -m json.tool
```

For a new lab cluster, the collection is normally absent. If it contains data,
do not count the run as controlled until the collection has been isolated or
cleared.

Apply the alternate agent manifest:

```bash
kubectl apply -f docs/examples/lab4/retrieval-agent-abox.yaml

kubectl -n kagent get agent retrieval-agent -o jsonpath='{range .spec.declarative.tools[*]}{.mcpServer.name}{" => "}{.mcpServer.toolNames}{"\n"}{end}'
```

Expected vector toolset:

```text
qdrant-mcp => [vector_store vector_find]
```

## 9. Index the identical corpus with the Abox MCP

Start a new `retrieval-agent` chat and send:

```text
Ingest the evaluation corpus from ConfigMap kagent/agentic-retrieval-corpus exactly as your system instructions specify. Call vector_store strictly one at a time in DOC-01 through DOC-08 order, waiting for each result before starting the next call. Never issue parallel tool calls. Stop on the first error. Report every stored doc_id and the number of successful vector_store calls.
```

Verify the collection:

```bash
curl --fail --silent http://127.0.0.1:6333/collections/abox-nomic \
  | python3 -m json.tool

curl --fail --silent \
  'http://127.0.0.1:6333/collections/abox-nomic/points/count' \
  -H 'Content-Type: application/json' \
  -d '{"exact":true}' | python3 -m json.tool
```

Expected evidence is vector size 768. Eight short inputs should produce eight
points; if chunking creates more, record the actual count and inspect why.

## 10. Run and score the Abox-MCP queries

Repeat the queries from step 7 in new chats. Score both configurations with the
definitions fixed in ADR-005:

```text
Tool-use rate = correct retrieval-tool calls / 8
Hit@1         = expected document first / 8
Hit@3         = expected document in first three / 8
Answer accuracy = answers supported by retrieved text / 8
```

Report English and Ukrainian/Russian failures individually. An aggregate score
alone can hide a multilingual retrieval weakness.

Enter one row per run in
`docs/examples/lab4/evaluation-results.tsv`. `returned_doc_ids` is a
comma-separated list in the exact order returned by the tool. Set `grounded` to
1 only when every factual part of the answer is supported by the retrieved
text. Then calculate the aggregate table:

```bash
python3 scripts/score-agentic-retrieval.py
```

The script exits with status 2 and lists missing runs until all sixteen rows
have been recorded.

## 11. Restore GitOps and stop temporary processes

Choose which agent variant should remain as the repository result. ADR-005 uses
the official variant as the selected configuration, so apply it before resuming
only if the release artifact has also been updated to contain that manifest.
Otherwise Flux will deliberately restore the published release version.

```bash
kill "$QDRANT_PF_PID"
kubectl -n flux-system patch kustomization releases \
  --type=merge -p '{"spec":{"suspend":false}}'

RELEASE_REQUEST="$(date -u +%s)-release"
kubectl -n flux-system annotate kustomization releases \
  reconcile.fluxcd.io/requestedAt="${RELEASE_REQUEST}" --overwrite
kubectl -n flux-system wait kustomization/releases \
  --for="jsonpath={.status.lastHandledReconcileAt}=${RELEASE_REQUEST}" \
  --timeout=10m
kubectl -n flux-system wait kustomization/releases \
  --for=condition=Ready=True --timeout=10m
kubectl -n flux-system get kustomization releases
```

## 12. Complete the records

Replace every `pending` cell in ADR-005 with observed evidence. Add the release
revision, collection sizes, point counts, tool traces, per-query results, and
the final comparison. Then update `CHANGELOG.md` with what was deployed and
measured. Prepared manifests or expected dimensions are not execution results.
