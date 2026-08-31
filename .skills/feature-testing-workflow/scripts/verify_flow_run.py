#!/usr/bin/env python3
"""Verify persisted docpipe flow artifacts without using a test framework."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--run-dir", type=Path, help="Explicit data/{job_id}/{job_run_id} directory")
    parser.add_argument(
        "--started-after",
        type=datetime.fromisoformat,
        help="Only consider job_stats.json files modified after this ISO-8601 timestamp",
    )
    parser.add_argument(
        "--expect-status",
        action="append",
        dest="expected_statuses",
        help="Allowed job status; repeat for multiple values",
    )
    parser.add_argument("--expected-total", type=int, help="Expected job-level total_docs count")
    parser.add_argument("--expect-node", action="append", default=[], help="Expected node name")
    parser.add_argument(
        "--expect-column",
        action="append",
        default=[],
        metavar="NODE:COLUMN",
        help="Require a column in every persisted output for a node",
    )
    parser.add_argument(
        "--min-rows",
        action="append",
        default=[],
        metavar="NODE:COUNT",
        help="Require at least COUNT persisted rows for a node",
    )
    parser.add_argument("--allow-failures", action="store_true", help="Do not fail on job-level failed_docs")
    return parser.parse_args()


def count_value(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, (list, tuple, set, dict)):
        return len(value)
    raise ValueError(f"Cannot interpret count from {value!r}")


def find_run_dir(*, data_root: Path, started_after: datetime | None) -> Path:
    candidates = list(data_root.glob("*/*/docpipe_logs/job_stats.json"))
    if started_after is not None:
        threshold = started_after.timestamp()
        candidates = [path for path in candidates if path.stat().st_mtime >= threshold]
    if not candidates:
        raise FileNotFoundError(f"No matching job_stats.json found under {data_root}")
    return max(candidates, key=lambda path: path.stat().st_mtime).parent.parent


def load_stats(*, run_dir: Path) -> dict[str, Any]:
    stats_path = run_dir / "docpipe_logs" / "job_stats.json"
    if not stats_path.is_file():
        raise FileNotFoundError(f"Job statistics not found: {stats_path}")
    with stats_path.open(encoding="utf-8") as stream:
        return json.load(stream)


def parse_pair(*, raw: str, value_name: str) -> tuple[str, str]:
    if ":" not in raw:
        raise ValueError(f"Expected NODE:{value_name}, received {raw!r}")
    node, value = raw.split(":", 1)
    if not node or not value:
        raise ValueError(f"Expected NODE:{value_name}, received {raw!r}")
    return node, value


def find_node_stats(*, stats: dict[str, Any], node_name: str) -> dict[str, Any] | None:
    node_stats = stats.get("node_stats", {})
    if not isinstance(node_stats, dict):
        return None
    return next(
        (node for node in node_stats.values() if isinstance(node, dict) and node.get("name") == node_name), None
    )


def node_outputs(*, run_dir: Path, node_name: str) -> list[Path]:
    return sorted((run_dir / "data").glob(f"{node_name}_*/output.parquet"))


def main() -> int:
    args = parse_args()
    errors: list[str] = []

    try:
        run_dir = args.run_dir or find_run_dir(data_root=args.data_root, started_after=args.started_after)
        stats = load_stats(run_dir=run_dir)
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    expected_statuses = set(args.expected_statuses or ["Completed", "CompletedWithWarnings"])
    actual_status = stats.get("status") or stats.get("job_status")
    if actual_status not in expected_statuses:
        errors.append(f"job status {actual_status!r} is not one of {sorted(expected_statuses)!r}")

    try:
        failed_count = count_value(stats.get("failed_docs"))
        total_count = count_value(stats.get("total_docs"))
    except ValueError as exc:
        errors.append(str(exc))
        failed_count = -1
        total_count = -1

    if not args.allow_failures and failed_count > 0:
        errors.append(f"job contains {failed_count} failed document(s)")
    if args.expected_total is not None and total_count != args.expected_total:
        errors.append(f"total_docs is {total_count}, expected {args.expected_total}")

    for node_name in args.expect_node:
        if find_node_stats(stats=stats, node_name=node_name) is None:
            errors.append(f"node {node_name!r} is absent from job statistics")

    output_cache: dict[str, list[tuple[Path, Any]]] = {}

    def read_outputs(node_name: str) -> list[tuple[Path, Any]]:
        if node_name not in output_cache:
            paths = node_outputs(run_dir=run_dir, node_name=node_name)
            output_cache[node_name] = [(path, pq.read_table(path)) for path in paths]
        return output_cache[node_name]

    try:
        for raw in args.expect_column:
            node_name, column = parse_pair(raw=raw, value_name="COLUMN")
            outputs = read_outputs(node_name)
            if not outputs:
                errors.append(f"node {node_name!r} has no persisted output.parquet")
                continue
            missing = [str(path) for path, table in outputs if column not in table.column_names]
            if missing:
                errors.append(f"column {column!r} is missing from: {', '.join(missing)}")

        for raw in args.min_rows:
            node_name, minimum_text = parse_pair(raw=raw, value_name="COUNT")
            minimum = int(minimum_text)
            outputs = read_outputs(node_name)
            if not outputs:
                errors.append(f"node {node_name!r} has no persisted output.parquet")
                continue
            rows = sum(table.num_rows for _, table in outputs)
            if rows < minimum:
                errors.append(f"node {node_name!r} has {rows} persisted row(s), expected at least {minimum}")
    except (OSError, ValueError) as exc:
        errors.append(str(exc))

    print(f"Run directory: {run_dir}")
    print(f"Job status: {actual_status}")
    print(f"Total documents: {total_count}")
    print(f"Failed documents: {failed_count}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print("PASS: baseline flow-run checks succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
