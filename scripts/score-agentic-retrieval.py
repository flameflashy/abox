#!/usr/bin/env python3
"""Score the controlled Agentic Retrieval experiment from TSV evidence."""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path


EXPECTED_CONFIGS = {
    "official": "qdrant-find",
    "abox": "vector_find",
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source, delimiter="\t"))


def parse_binary(value: str, field: str, row_number: int) -> int:
    if value not in {"0", "1"}:
        raise ValueError(f"row {row_number}: {field} must be 0 or 1")
    return int(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--queries",
        type=Path,
        default=Path("docs/examples/lab4/evaluation-queries.tsv"),
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("docs/examples/lab4/evaluation-results.tsv"),
    )
    args = parser.parse_args()

    query_rows = read_tsv(args.queries)
    expected = {row["query_id"]: row["expected_doc_id"] for row in query_rows}
    if len(expected) != len(query_rows):
        raise ValueError("query_id values must be unique")

    result_rows = read_tsv(args.results)
    if not result_rows:
        print("No result rows recorded yet.")
        return 0

    by_configuration: dict[str, list[dict[str, object]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()

    for number, row in enumerate(result_rows, start=2):
        configuration = row["configuration"]
        query_id = row["query_id"]
        if configuration not in EXPECTED_CONFIGS:
            raise ValueError(
                f"row {number}: configuration must be one of "
                f"{', '.join(EXPECTED_CONFIGS)}"
            )
        if query_id not in expected:
            raise ValueError(f"row {number}: unknown query_id {query_id!r}")
        key = (configuration, query_id)
        if key in seen:
            raise ValueError(f"row {number}: duplicate result for {key}")
        seen.add(key)

        returned = [
            value.strip()
            for value in row["returned_doc_ids"].split(",")
            if value.strip()
        ]
        try:
            unsupported_claims = int(row["unsupported_claims"])
            latency_text = row["latency_seconds"].strip()
            latency = float(latency_text) if latency_text else None
        except ValueError as error:
            raise ValueError(
                f"row {number}: unsupported_claims must be an integer and "
                "latency_seconds must be numeric or empty"
            ) from error
        if unsupported_claims < 0 or (latency is not None and latency < 0):
            raise ValueError(f"row {number}: numeric values cannot be negative")

        expected_id = expected[query_id]
        by_configuration[configuration].append(
            {
                "tool": int(row["retrieval_tool"] == EXPECTED_CONFIGS[configuration]),
                "hit1": int(bool(returned) and returned[0] == expected_id),
                "hit3": int(expected_id in returned[:3]),
                "grounded": parse_binary(row["grounded"], "grounded", number),
                "unsupported": unsupported_claims,
                "latency": latency,
            }
        )

    print(
        "| Configuration | Runs | Tool-use rate | Hit@1 | Hit@3 | "
        "Grounded accuracy | Unsupported claims | Median latency |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for configuration in EXPECTED_CONFIGS:
        rows = by_configuration.get(configuration, [])
        if not rows:
            print(f"| {configuration} | 0 | pending | pending | pending | pending | pending | pending |")
            continue
        count = len(rows)
        percentage = lambda field: f"{sum(int(r[field]) for r in rows) / count:.1%}"
        latencies = [float(r["latency"]) for r in rows if r["latency"] is not None]
        median_latency = (
            f"{statistics.median(latencies):.2f}s" if latencies else "not recorded"
        )
        print(
            f"| {configuration} | {count} | {percentage('tool')} | "
            f"{percentage('hit1')} | {percentage('hit3')} | "
            f"{percentage('grounded')} | "
            f"{sum(int(r['unsupported']) for r in rows)} | "
            f"{median_latency} |"
        )

    missing = [
        f"{configuration}/{query_id}"
        for configuration in EXPECTED_CONFIGS
        for query_id in expected
        if (configuration, query_id) not in seen
    ]
    if missing:
        print("\nMissing runs: " + ", ".join(missing))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
