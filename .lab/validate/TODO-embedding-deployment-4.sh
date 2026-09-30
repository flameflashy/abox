kubectl -n embedding-lab describe pods -l app=embedding-sidecar
kubectl -n embedding-lab logs deployment/embedding-sidecar -c embeddings --tail=100
kubectl -n embedding-lab get events --sort-by=.metadata.creationTimestamp
