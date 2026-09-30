docker pull ghcr.io/ggml-org/llama.cpp:server
export LLAMA_IMAGE="$(docker image inspect ghcr.io/ggml-org/llama.cpp:server --format '{{index .RepoDigests 0}}')"
test -n "$LLAMA_IMAGE"
printf '%s\n' "$LLAMA_IMAGE" | tee .lab/embeddings/llama-image.txt
docker run --rm "$LLAMA_IMAGE" --version
