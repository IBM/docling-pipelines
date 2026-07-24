"""
Example: Running a flow with DuckDB job stats storage

This example demonstrates:
1. Running a simple data processing flow with DuckDB storage
2. Querying the stored job statistics from DuckDB

Prerequisites:
- Uncomment the DuckDB configuration in docling-pipelines-config.yaml:

  job_management:
    store:
      type: duckdb
      config:
        database_path: ./data/duckdb/job_stats.duckdb

- Sample data files in examples/duckdb_job_stats/sample_data/
- DuckDB installed (included in project dependencies)

Setup (from repository root):
    cd src/docpipe_app/backend
    python3.12 -m venv .venv
    source .venv/bin/activate
    uv sync --extra dev
    cd ../../..
    export PYTHONPATH="$(pwd)/src/docpipe_app/backend:${PYTHONPATH}"

Run:
    source src/docpipe_app/backend/.venv/bin/activate
    export PYTHONPATH="$(pwd)/src/docpipe_app/backend:${PYTHONPATH}"
    python examples/duckdb_job_stats/run_example.py
"""

import shutil
import sys
from pathlib import Path

# Add src to path for imports
# ruff: noqa: E402
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root / "src"))

import duckdb

from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager


def create_test_data():
    """Create test directory and sample document."""
    test_dir = Path("./test_data")
    test_dir.mkdir(exist_ok=True)

    # Create sample text file
    sample_file = test_dir / "sample_document.txt"
    sample_content = """# Sample Document for DuckDB Job Stats Example

This is a test document to demonstrate DuckDB job stats storage in docpipe.

## Introduction
The docling-pipelines project is a modular, operator-based data processing framework
designed for building flexible data pipelines.

## Key Features
- Operator-based architecture with 20+ specialized operators
- PyArrow data format for efficient memory usage
- DAG-based workflow execution

## DuckDB Job Stats Storage
This example demonstrates how to use DuckDB as a storage backend for job statistics.
DuckDB is an embedded analytical database that requires no server setup.
"""

    sample_file.write_text(sample_content)
    print(f"  Created test data directory: {test_dir}")
    print(f"  Created sample file: {sample_file}")

    return test_dir


def cleanup_test_data(test_dir):
    """Remove test directory and files."""
    if test_dir.exists():
        shutil.rmtree(test_dir)
        print("Cleaned up test directory: " + str(test_dir))


def print_configuration_info():
    """Print configuration information."""
    print("\n[Step 1] Configuration")
    print("  DuckDB storage is configured via docling-pipelines-config.yaml")
    print("  Make sure you have uncommented the DuckDB configuration:")
    print()
    print("  job_management:")
    print("    store:")
    print("      type: duckdb")
    print("      config:")
    print("        database_path: ./data/duckdb/job_stats.duckdb")
    print()


def execute_flow():
    """Execute the flow and return job_run_id."""
    print("\n[Step 3] Creating DocpipeFlowManager...")
    print("  Configuration is automatically loaded from docling-pipelines-config.yaml")
    flow_manager = DocpipeFlowManager(flow_file="examples/docpipe_flow_manager/sample_flow.json")
    print("  ✓ Flow manager created")

    print("\n[Step 4] Executing flow...")
    flow_file = Path(__file__).resolve().parents[1] / "docpipe_flow_manager" / "sample_flow.json"

    if not flow_file.exists():
        print("  ✗ Flow file not found: " + str(flow_file))
        print("  Please ensure example_flow.json exists in the same directory")
        return None

    print("  Flow file: " + str(flow_file))

    try:
        flow_manager.execute()
        print("  ✓ Flow executed successfully")

        metadata = flow_manager.get_execution_metadata()
        job_run_id = metadata.get("job_run_id")

        if job_run_id:
            print("  Job Run ID: " + job_run_id)

        return job_run_id

    except Exception as e:
        print("  ✗ Flow execution failed: " + str(e))
        print("\nNote: This example requires sample data files.")
        print("You can still query existing job stats if the database exists.")
        return None


def query_recent_jobs(conn):
    """Query and display recent jobs."""
    print("\n  Recent Jobs:")
    print("  " + "-" * 76)
    jobs = conn.execute("""
        SELECT
            job_run_id,
            status,
            total_docs,
            processed_docs,
            failed_docs,
            duration
        FROM job_stats
        ORDER BY start_time DESC
        LIMIT 5
    """).fetchall()

    if jobs:
        print("  {:<38} {:<12} {:<15} {:<10}".format("Job Run ID", "Status", "Docs", "Duration"))
        print("  " + "-" * 76)
        for job in jobs:
            job_id_short = job[0][:36] if len(job[0]) > 36 else job[0]
            docs_str = f"{job[3]}/{job[2]}"
            duration_str = f"{job[5]}s" if job[5] else "N/A"
            print(f"  {job_id_short:<38} {job[1]:<12} {docs_str:<15} {duration_str:<10}")
    else:
        print("  No jobs found in database")


def query_job_details(conn, job_run_id):
    """Query and display job details."""
    print("\n  Detailed Stats for Current Job (" + job_run_id[:8] + "...):")
    print("  " + "-" * 76)

    job_detail = conn.execute(
        """
        SELECT
            status,
            total_docs,
            processed_docs,
            completed_docs,
            failed_docs,
            skipped_docs,
            duration,
            orchestrator
        FROM job_stats
        WHERE job_run_id = ?
    """,
        [job_run_id],
    ).fetchone()

    if job_detail:
        print("  Status: " + str(job_detail[0]))
        print("  Total Documents: " + str(job_detail[1]))
        print("  Processed: " + str(job_detail[2]))
        print("  Completed: " + str(job_detail[3]))
        print("  Failed: " + str(job_detail[4]))
        print("  Skipped: " + str(job_detail[5]))
        print("  Duration: " + str(job_detail[6]) + "s")
        print("  Orchestrator: " + str(job_detail[7]))


def query_node_stats(conn, job_run_id):
    """Query and display node statistics."""
    print("\n  Node Statistics:")
    print("  " + "-" * 76)

    nodes = conn.execute(
        """
        SELECT
            node_id,
            name,
            node_status,
            time_taken,
            docs_completed_count
        FROM node_stats
        WHERE job_run_id = ?
        ORDER BY start_time
    """,
        [job_run_id],
    ).fetchall()

    if nodes:
        print("  {:<38} {:<20} {:<12} {:<8}".format("Node ID", "Name", "Status", "Time"))
        print("  " + "-" * 76)
        for node in nodes:
            node_id_short = node[0][:36] if len(node[0]) > 36 else node[0]
            name = node[1][:18] if node[1] and len(node[1]) > 18 else (node[1] or "N/A")
            time_str = f"{node[3]}s" if node[3] else "N/A"
            print(f"  {node_id_short:<38} {name:<20} {node[2]:<12} {time_str:<8}")
    else:
        print("  No node stats found")


def print_query_examples(db_path):
    """Print example SQL queries."""
    print("\n[Step 6] Additional Query Examples:")
    print("  " + "-" * 76)
    print("\n  To query the database directly:")
    print("    duckdb " + db_path)
    print()
    print("  Example queries:")
    print("    -- List all jobs")
    print("    SELECT job_run_id, status, total_docs FROM job_stats;")
    print()
    print("    -- Get job statistics summary")
    print("    SELECT status, COUNT(*) as count, AVG(duration) as avg_duration")
    print("    FROM job_stats GROUP BY status;")
    print()
    print("    -- View node performance")
    print("    SELECT node_id, name, AVG(time_taken) as avg_time")
    print("    FROM node_stats GROUP BY node_id, name;")


def main():
    """Run flow with DuckDB storage and query results."""

    print("=" * 80)
    print("DuckDB Job Stats Storage Example")
    print("=" * 80)

    print_configuration_info()

    print("[Step 2] Creating test data...")
    create_test_data()

    job_run_id = execute_flow()

    print("\n[Step 5] Querying job statistics from DuckDB...")

    # Default database path from docling-pipelines-config.yaml
    db_path = "./data/duckdb/job_stats.duckdb"

    try:
        conn = duckdb.connect(db_path, read_only=True)

        query_recent_jobs(conn)

        if job_run_id:
            query_job_details(conn, job_run_id)
            query_node_stats(conn, job_run_id)

        conn.close()
        print("\n  ✓ Successfully queried DuckDB database")

    except Exception as e:
        print("  ✗ Failed to query database: " + str(e))
        print("  Make sure the database file exists at: " + db_path)
        print("  Run a flow first to create the database.")

    print_query_examples(db_path)

    print("\n" + "=" * 80)
    print("Example completed!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    finally:
        # Cleanup test data
        test_dir = Path("./test_data")
        if test_dir.exists():
            print("\nCleaning up test data...")
            cleanup_test_data(test_dir)
