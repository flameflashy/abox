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

## 3. Pause GitOps while switching the experiment manifests

The release owns `retrieval-agent`. Flux can otherwise restore the release
version during the test.

```bash
flux suspend kustomization releases -n flux-system
flux get kustomizations -n flux-system
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
Ingest the evaluation corpus from ConfigMap kagent/agentic-retrieval-corpus exactly as your system instructions specify. Report every stored doc_id and the number of successful qdrant-store calls.
```

The trace must show one delegation to `k8s-agent` and eight `qdrant-store`
calls. Verify the collection independently:

```bash
kubectl -n qdrant port-forward service/qdrant 6333:6333 >/tmp/qdrant-port-forward.log 2>&1 &
QDRANT_PF_PID=$!

curl --fail --silent http://127.0.0.1:6333/collections/lab4-minilm \
  | python3 -m json.tool

curl --fail --silent \
  'http://127.0.0.1:6333/collections/lab4-minilm/points/count' \
  -H 'Content-Type: application/json' \
  -d '{"exact":true}' | python3 -m json.tool
```

Expected evidence is vector size 384 and exactly eight points. Keep the port
forward running for later checks.

## 7. Run the official-MCP retrieval queries

Use `docs/examples/lab4/evaluation-queries.tsv`. Start a new chat for each query
so earlier answers do not influence later ones. Prefix each query with:

```text
This is a retrieval-only evaluation. Search the indexed corpus, answer only from the retrieved documents, and list the returned doc_id values in order.
```

Record the tool trace, ordered IDs, answer, and elapsed time in ADR-005. Do not
correct the agent or retry a failed query silently; record the failure first.

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
Ingest the evaluation corpus from ConfigMap kagent/agentic-retrieval-corpus exactly as your system instructions specify. Report every stored doc_id and the number of successful vector_store calls.
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
flux resume kustomization releases -n flux-system
flux reconcile kustomization releases -n flux-system --with-source
flux get kustomizations -n flux-system
```

## 12. Complete the records

Replace every `pending` cell in ADR-005 with observed evidence. Add the release
revision, collection sizes, point counts, tool traces, per-query results, and
the final comparison. Then update `CHANGELOG.md` with what was deployed and
measured. Prepared manifests or expected dimensions are not execution results.
