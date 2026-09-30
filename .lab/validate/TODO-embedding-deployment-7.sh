# Внутри подготовленного vLLM окружения; revision задан на шаге 1.
: "${VLLM_MODEL_REVISION:?Set the reviewed Hugging Face commit first}"
vllm serve Qwen/Qwen3-Embedding-0.6B \
  --revision "$VLLM_MODEL_REVISION" \
  --runner pooling \
  --served-model-name qwen3-embedding-0.6b \
  --max-model-len 2048 --host 0.0.0.0 --port 8000
