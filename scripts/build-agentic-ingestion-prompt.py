#!/usr/bin/env python3
"""Build a direct, JSON-encoded Agent ingestion prompt from the live ConfigMap."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


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
    return parser.parse_args()


def load_configmap(namespace: str, name: str) -> dict[str, str]:
    result = subprocess.run(
        ["kubectl", "-n", namespace, "get", "configmap", name, "-o", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout).get("data", {})


def main() -> int:
    args = parse_args()
    data = load_configmap(args.namespace, args.configmap)
    if set(data) != set(EXPECTED_KEYS):
        print("ConfigMap keys do not match the fixed evaluation corpus.", file=sys.stderr)
        print("Expected:", *EXPECTED_KEYS, sep="\n  ", file=sys.stderr)
        print("Observed:", *sorted(data), sep="\n  ", file=sys.stderr)
        return 1

    records = []
    for key in EXPECTED_KEYS:
        records.append(
            {
                "information": data[key],
                "metadata": {
                    "doc_id": key.removesuffix(".yaml"),
                    "source": f"{args.namespace}/{args.configmap}",
                    "language": "en",
                },
            }
        )

    print("This is a direct, controlled corpus ingestion request.")
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
