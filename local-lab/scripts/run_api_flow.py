#!/usr/bin/env python3
"""Submit api/flow.json to the Docling Pipelines API and wait for a summary.

Run from local-lab/:

    python3 scripts/run_api_flow.py

The API is a long-running service. A flow file on disk is not executed
directly. This script: saves the flow as an asset, starts a job run, then
polls until the job finishes. The last print is the CLI-style summary.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
FLOW_FILE = LAB_ROOT / "api" / "flow.json"
API_BASE = "http://localhost:8080"
TERMINAL_STATUSES = {"Completed", "CompletedWithErrors", "Failed"}
POLL_SECONDS = 2


def _read_json(request: urllib.request.Request) -> dict:
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError:
        raise
    except urllib.error.URLError as exc:
        raise SystemExit(f"Could not reach {request.full_url}: {exc.reason}") from exc


def _exit_http(*, exc: urllib.error.HTTPError) -> None:
    detail = exc.read().decode("utf-8", errors="replace")
    raise SystemExit(f"HTTP {exc.code} {exc.url}: {detail}") from exc


def post_json(*, path: str, body: dict) -> dict:
    request = urllib.request.Request(
        url=f"{API_BASE}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        return _read_json(request)
    except urllib.error.HTTPError as exc:
        _exit_http(exc=exc)


def get_json(*, path: str) -> dict:
    request = urllib.request.Request(url=f"{API_BASE}{path}", method="GET")
    try:
        return _read_json(request)
    except urllib.error.HTTPError as exc:
        _exit_http(exc=exc)


def find_flow_by_name(*, name: str) -> str | None:
    query = urllib.parse.urlencode({"name": name})
    payload = get_json(path=f"/api/v1/flows?{query}")
    for flow in payload.get("flows") or []:
        if flow.get("flow_name") == name or flow.get("name") == name:
            return flow["flow_id"]
    return None


def create_flow(*, flow_file: Path) -> str:
    """Return a flow_id: reuse it if that name exists, otherwise POST the JSON."""
    payload = json.loads(flow_file.read_text(encoding="utf-8"))
    flow_name = payload["flow_name"]
    existing_id = find_flow_by_name(name=flow_name)
    if existing_id is not None:
        print(f"Flow '{flow_name}' already exists, reusing {existing_id}")
        return existing_id

    print(f"Creating flow from {flow_file.relative_to(LAB_ROOT)}...")
    flow_id = post_json(path="/api/v1/flows", body=payload)["flow_id"]
    print(f"Created flow id: {flow_id}")
    return flow_id


def start_job_run(*, flow_id: str) -> str:
    """POST /api/v1/job_runs — start one execution. Returns immediately."""
    print("Starting job run...")
    body = {
        "entity": {
            "job": {
                "asset_ref": flow_id,
                "asset_ref_type": "ibm_udp_flow",
                "name": "local-lab-minio-docling-serve",
            }
        }
    }
    job_run_id = post_json(path="/api/v1/job_runs", body=body)["job_run_id"]
    print(f"Job run id: {job_run_id}")
    return job_run_id


def wait_for_job(*, job_run_id: str) -> dict:
    """GET /api/v1/job_runs/{id} until the job finishes. Same counts as the CLI summary."""
    print("Waiting for job to finish...")
    while True:
        payload = get_json(path=f"/api/v1/job_runs/{job_run_id}")
        stats = payload.get("job_stats") or {}
        status = stats.get("status") or "unknown"
        print(
            f"  {status}  completed={stats.get('completed_docs')} "
            f"failed={stats.get('failed_docs')} skipped={stats.get('skipped_docs')} "
            f"of {stats.get('total_docs')}"
        )
        if status in TERMINAL_STATUSES:
            return stats
        time.sleep(POLL_SECONDS)


def print_summary(*, stats: dict) -> None:
    print()
    print("FLOW EXECUTION SUMMARY")
    print(f"  Status:     {stats.get('status')}")
    print(f"  Duration:   {stats.get('duration')}s")
    print(
        f"  Documents:  {stats.get('completed_docs')} completed, "
        f"{stats.get('failed_docs')} failed, "
        f"{stats.get('skipped_docs')} skipped "
        f"(of {stats.get('total_docs')} total)"
    )


def main() -> int:
    if not FLOW_FILE.is_file():
        print(f"Flow file not found: {FLOW_FILE}", file=sys.stderr)
        return 1

    flow_id = create_flow(flow_file=FLOW_FILE)
    job_run_id = start_job_run(flow_id=flow_id)
    stats = wait_for_job(job_run_id=job_run_id)
    print_summary(stats=stats)
    return 0 if stats.get("status") == "Completed" else 1


if __name__ == "__main__":
    sys.exit(main())
