# TODO: Local Embedding Model

Goal:
Run nomic-embed-text-v1.5 locally using llama.cpp.

Tasks:

1. Install/build llama.cpp.

2. Download GGUF version of nomic-embed-text-v1.5.

3. Start llama-server with embeddings enabled.

4. Expose HTTP API:
   http://localhost:8080/v1/embeddings

5. Verify the endpoint:

curl http://localhost:8080/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Hello world"
  }'

6. Verify that the response contains an embedding vector.

7. Document how abox components can access the endpoint.