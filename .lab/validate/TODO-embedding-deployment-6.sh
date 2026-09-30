kubectl get nodes -o wide
kubectl get nodes -o json > .lab/embeddings/nodes.json
kubectl get gatewayclass
kubectl get crd | grep -E 'gateway|inference'
lscpu
free -h
git clone --branch v0.9.0 --depth 1 https://github.com/llm-d/llm-d.git .lab/llm-d
git -C .lab/llm-d rev-parse HEAD
