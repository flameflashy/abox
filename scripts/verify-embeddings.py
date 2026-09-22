#!/usr/bin/env python3
"""Small multilingual HTTP smoke check; Python standard library only."""

import argparse
import json
import math
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MODEL = "qwen3-embedding-0.6b"
INSTRUCTION = "Retrieve relevant technical documentation that answers the question."
DOCUMENTS = [
    "Qdrant stores embedding vectors and retrieves documents by vector similarity.",
    "Контейнери одного Kubernetes Pod спільно використовують мережу і можуть "
    "звертатися один до одного через localhost.",
    "Flux автоматически сверяет состояние Kubernetes с опубликованными "
    "OCI-артефактами и применяет изменения ресурсов.",
]
QUERIES = [
    ("uk", "Де зберігати вектори для семантичного пошуку документів?", 0),
    ("ru", "Как обратиться к соседнему контейнеру внутри одного Pod?", 1),
    ("en", "What reconciles Kubernetes resources from OCI artifacts?", 2),
]


def normalize(vector, dimensions):
    selected = vector[:dimensions]
    norm = math.sqrt(math.fsum(x * x for x in selected))
    if not math.isfinite(norm) or norm <= 0:
        raise ValueError("Embedding has zero or invalid norm")
    return [x / norm for x in selected]


def validate_response(response):
    data = response.get("data")
    if not isinstance(data, list) or len(data) != 1:
        raise ValueError("Expected one embedding for one input")
    row = data[0]
    if not isinstance(row, dict) or row.get("index") != 0:
        raise ValueError("Expected embedding index 0")
    vector = row.get("embedding")
    if not isinstance(vector, list) or len(vector) != 1024:
        raise ValueError("Expected 1024-dimensional Qwen3 embedding")
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in vector):
        raise ValueError("Embedding contains non-finite or non-numeric values")
    norm = math.sqrt(math.fsum(x * x for x in vector))
    if not math.isclose(norm, 1.0, abs_tol=0.01):
        raise ValueError(f"Expected L2-normalized server vector, norm={norm}")
    return vector


def embed(base_url, model, text):
    payload = {"model": model, "input": text, "encoding_format": "float"}
    request = Request(
        base_url.rstrip("/") + "/v1/embeddings",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    with urlopen(request, timeout=180) as result:
        response = json.load(result)
    return validate_response(response), round(time.perf_counter() - start, 3)


def check(base_url, model):
    vectors, timings = [], []
    inputs = DOCUMENTS + [
        f"Instruct: {INSTRUCTION}\nQuery:{query}" for _, query, _ in QUERIES
    ]
    # Sequential requests keep this smoke check practical on a small CPU server.
    for text in inputs:
        vector, elapsed = embed(base_url, model, text)
        vectors.append(vector)
        timings.append(elapsed)
    results = {}
    passed = True
    for dimensions in (1024, 256):
        normalized = [normalize(vector, dimensions) for vector in vectors]
        rows = []
        for offset, (language, _, expected) in enumerate(QUERIES):
            query = normalized[len(DOCUMENTS) + offset]
            scores = [math.fsum(a * b for a, b in zip(query, document))
                      for document in normalized[:len(DOCUMENTS)]]
            actual = max(range(len(scores)), key=scores.__getitem__)
            ok = actual == expected
            passed = passed and ok
            rows.append({"query_language": language, "expected_document": expected,
                         "top_document": actual, "passed": ok,
                         "scores": [round(score, 5) for score in scores]})
        results[str(dimensions)] = rows
    return {"passed": passed, "url": base_url, "model": model,
            "native_dimensions": 1024, "request_seconds": timings,
            "results": results,
            "note": "Three cross-language examples, not a corpus quality benchmark."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8081")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = check(args.url, args.model)
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError, TypeError,
            AttributeError, OSError) as error:
        print(f"Embedding check failed: {error}", file=sys.stderr)
        return 1
    formatted = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(formatted + "\n", encoding="utf-8")
    print(formatted)
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
