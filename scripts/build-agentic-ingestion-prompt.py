#!/usr/bin/env python3
"""Build a direct, JSON-encoded Agent ingestion prompt from the live ConfigMap."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request


EXPECTED_KEYS = [
    "DOC-01-qdrant-storage.yaml",
    "DOC-02-sidecar-network.yaml",
    "DOC-03-flux-oci.yaml",
    "DOC-04-llmd-route.yaml",
    "DOC-05-official-qdrant-mcp.yaml",
    "DOC-06-agent-model.yaml",
    "DOC-07-abox-qdrant-mcp.yaml",
    "DOC-08-inference-pool.yaml",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", default="kagent")
    parser.add_argument("--configmap", default="agentic-retrieval-corpus")
    parser.add_argument("--tool", choices=("vector_store", "qdrant-store"), required=True)
    parser.add_argument("--qdrant-url", default="http://127.0.0.1:6333")
    parser.add_argument("--source-collection")
    parser.add_argument("--source-layout", choices=("official", "abox"), default="official")
    return parser.parse_args()


def load_configmap(namespace: str, name: str) -> dict[str, str]:
    result = subprocess.run(
        ["kubectl", "-n", namespace, "get", "configmap", name, "-o", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout).get("data", {})


def scroll_points(qdrant_url: str, collection: str) -> list[dict]:
    endpoint = f"{qdrant_url.rstrip('/')}/collections/{collection}/points/scroll"
    body = {"limit": 256, "with_payload": True, "with_vector": False}
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)["result"]["points"]


def load_qdrant_records(qdrant_url: str, collection: str, layout: str) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for point in scroll_points(qdrant_url, collection):
        payload = point.get("payload", {})
        if layout == "official":
            metadata = payload.get("metadata", {})
        else:
            metadata = {
                key: payload[key]
                for key in ("doc_id", "source", "language")
                if key in payload
            }
        doc_id = metadata.get("doc_id") if isinstance(metadata, dict) else None
        document = payload.get("document")
        if not isinstance(doc_id, str) or not isinstance(document, str):
            continue
        if doc_id in records:
            raise ValueError(f"Duplicate source document: {doc_id}")
        records[doc_id] = {"information": document, "metadata": metadata}
    return records


def main() -> int:
    args = parse_args()
    expected_ids = [key.removesuffix(".yaml") for key in EXPECTED_KEYS]
    if args.source_collection:
        source_records = load_qdrant_records(
            args.qdrant_url, args.source_collection, args.source_layout
        )
        source_description = f"Qdrant collection {args.source_collection}"
    else:
        data = load_configmap(args.namespace, args.configmap)
        source_records = {
            key.removesuffix(".yaml"): {
                "information": value,
                "metadata": {
                    "doc_id": key.removesuffix(".yaml"),
                    "source": f"{args.namespace}/{args.configmap}",
                    "language": "en",
                },
            }
            for key, value in data.items()
            if key.endswith(".yaml")
        }
        source_description = f"ConfigMap {args.namespace}/{args.configmap}"

    if set(source_records) != set(expected_ids):
        print(f"{source_description} IDs do not match the fixed corpus.", file=sys.stderr)
        print("Expected:", *expected_ids, sep="\n  ", file=sys.stderr)
        print("Observed:", *sorted(source_records), sep="\n  ", file=sys.stderr)
        return 1

    records = [source_records[doc_id] for doc_id in expected_ids]

    print("This is a direct, controlled corpus ingestion request.")
    print(f"The exact source is {source_description}.")
    print("Do not call k8s-agent and do not reconstruct or summarize any document.")
    print(f"Call {args.tool} exactly once for each JSON record below.")
    print("Use each information string and metadata object exactly as encoded.")
    print("Make the eight calls strictly sequentially in array order.")
    print("Wait for each result before the next call and stop on the first error.")
    print("Report every stored doc_id and the successful call count.")
    print("DOCUMENTS_JSON:")
    print(json.dumps(records, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
