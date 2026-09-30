curl --fail --silent --show-error http://127.0.0.1:8081/health
curl --fail --silent --show-error http://127.0.0.1:8081/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3-embedding-0.6b","input":"Instruct: Retrieve relevant technical documentation.\nQuery:Як працює пошук у Qdrant?","encoding_format":"float"}' \
  > .lab/embeddings/response.json
python3 -c 'import json; r=json.load(open(".lab/embeddings/response.json")); print("dimensions:", len(r["data"][0]["embedding"]))'
