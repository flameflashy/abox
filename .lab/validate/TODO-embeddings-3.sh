export LLAMA_IMAGE="$(cat .lab/embeddings/llama-image.txt)"
docker run --rm --name abox-embeddings \
  --cpus 2 --memory 3g \
  -p 127.0.0.1:8081:8080 \
  -v "$PWD/.lab/embeddings/models:/models:ro" \
  "$LLAMA_IMAGE" \
  --model /models/Qwen3-Embedding-0.6B-Q8_0.gguf \
  --alias qwen3-embedding-0.6b \
  --embedding --pooling last \
  --ctx-size 2048 --batch-size 2048 --ubatch-size 2048 \
  --parallel 1 --threads 2 --n-gpu-layers 0 \
  --host 0.0.0.0 --port 8080
