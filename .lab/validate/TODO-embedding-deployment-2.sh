set -o pipefail
kubectl -n embedding-lab exec -i deployment/embedding-sidecar -c client -- \
  python - --url http://127.0.0.1:8080 \
  < scripts/verify-embeddings.py | tee .lab/embeddings/sidecar-check.json
