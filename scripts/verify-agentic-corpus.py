#!/usr/bin/env python3
"""Compare indexed Qdrant payloads with the live evaluation ConfigMap."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.error
import urllib.request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qdrant-url", default="http://127.0.0.1:6333")
    parser.add_argument("--collection", required=True)
    parser.add_argument("--layout", choices=("official", "abox"), required=True)
    parser.add_argument("--namespace", default="kagent")
    parser.add_argument("--configmap", default="agentic-retrieval-corpus")
    return parser.parse_args()


def load_configmap(namespace: str, name: str) -> dict[str, str]:
    command = [
        "kubectl",
        "-n",
        namespace,
        "get",
        "configmap",
        name,
        "-o",
        "json",
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    resource = json.loads(result.stdout)
    return resource.get("data", {})


def scroll_points(qdrant_url: str, collection: str) -> list[dict]:
    endpoint = f"{qdrant_url.rstrip('/')}/collections/{collection}/points/scroll"
    points: list[dict] = []
    offset = None

    while True:
        body: dict[str, object] = {
            "limit": 256,
            "with_payload": True,
            "with_vector": False,
        }
        if offset is not None:
            body["offset"] = offset
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            result = json.load(response)["result"]
        points.extend(result["points"])
        offset = result.get("next_page_offset")
        if offset is None:
            return points


def point_doc_id(payload: dict, layout: str) -> str | None:
    if layout == "official":
        metadata = payload.get("metadata")
        return metadata.get("doc_id") if isinstance(metadata, dict) else None
    return payload.get("doc_id")


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def main() -> int:
    args = parse_args()
    configmap = load_configmap(args.namespace, args.configmap)
    expected = {
        key.removesuffix(".yaml"): value
        for key, value in configmap.items()
        if key.endswith(".yaml")
    }
    indexed: dict[str, list[str]] = {}
    unknown_points = 0

    try:
        points = scroll_points(args.qdrant_url, args.collection)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            print(
                f"Qdrant collection {args.collection!r} was not found. "
                "Run the ingestion before verification.",
                file=sys.stderr,
            )
        else:
            print(f"Qdrant returned HTTP {error.code}: {error.reason}", file=sys.stderr)
        return 2
    except urllib.error.URLError as error:
        print(f"Cannot reach Qdrant: {error.reason}", file=sys.stderr)
        return 2

    for point in points:
        payload = point.get("payload", {})
        doc_id = point_doc_id(payload, args.layout)
        document = payload.get("document")
        if not isinstance(doc_id, str) or not isinstance(document, str):
            unknown_points += 1
            continue
        indexed.setdefault(doc_id, []).append(document)

    ok = unknown_points == 0 and set(indexed) == set(expected)
    print("doc_id\tstatus\tconfigmap_sha256\tqdrant_sha256")
    for doc_id in sorted(set(expected) | set(indexed)):
        wanted = expected.get(doc_id)
        stored = indexed.get(doc_id, [])
        if wanted is None:
            status = "UNEXPECTED_ID"
            wanted_hash = "-"
            stored_hash = ",".join(digest(value) for value in stored)
        elif len(stored) != 1:
            status = "MISSING" if not stored else f"DUPLICATE_{len(stored)}"
            wanted_hash = digest(wanted)
            stored_hash = ",".join(digest(value) for value in stored) or "-"
        else:
            status = "MATCH" if stored[0] == wanted else "CONTENT_MISMATCH"
            wanted_hash = digest(wanted)
            stored_hash = digest(stored[0])
        ok = ok and status == "MATCH"
        print(f"{doc_id}\t{status}\t{wanted_hash}\t{stored_hash}")

    if unknown_points:
        print(f"Points missing a usable doc_id or document payload: {unknown_points}")
    print(f"Exact corpus match: {'yes' if ok else 'no'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
