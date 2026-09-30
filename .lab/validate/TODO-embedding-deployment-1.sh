kubectl apply --dry-run=client -f .lab/embeddings/sidecar.yaml
kubectl apply -f .lab/embeddings/sidecar.yaml
kubectl -n embedding-lab rollout status deployment/embedding-sidecar --timeout=600s
kubectl -n embedding-lab get pods -l app=embedding-sidecar
kubectl -n embedding-lab logs deployment/embedding-sidecar -c download-model
