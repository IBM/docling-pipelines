"""
DocpipeFlowManager Example 1: Execute Flow from File

This example demonstrates the simplest way to use DocpipeFlowManager - just provide
a path to your flow definition JSON file.

Prerequisites:
- Virtual environment activated: source .venv/bin/activate
- PYTHONPATH set: export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
- Ollama running (for LLM operations): http://localhost:11434
- OpenSearch running (for vector storage): http://localhost:9200

Setup (from repository root):
    python3.12 -m venv .venv
    source .venv/bin/activate
    uv sync --extra dev
    export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"

Run:
    source .venv/bin/activate
    export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
    python examples/docpipe_flow_manager/01_execute_from_file.py
"""

import shutil
from pathlib import Path

from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager


def create_test_data():
    """Create test directory and sample documents"""
    test_dir = Path("./test_data")
    test_dir.mkdir(exist_ok=True)

    # Create sample text file
    sample_file = test_dir / "sample_document.txt"
    sample_content = """Sample document for testing."""
    sample_file.write_text(sample_content)
    return test_dir


def cleanup_test_data(test_dir):
    """Remove test directory and files"""
    if test_dir.exists():
        shutil.rmtree(test_dir)


def main():
    """
    Execute a flow from a JSON file

    This is the simplest way to use DocpipeFlowManager - just provide a path
    to your flow definition JSON file.
    """
    test_dir = None

    try:
        print("\n" + "=" * 70)
        print("Example 1: Execute Flow from File")
        print("=" * 70)

        # Create test data
        print("\nCreating test data...")
        test_dir = create_test_data()

        # Path to the flow definition file
        flow_file = "examples/docpipe_flow_manager/sample_flow.json"

        # Create flow manager
        manager = DocpipeFlowManager(flow_file=flow_file)

        # Get metadata before execution
        metadata = manager.get_execution_metadata()
        print(f"\nFlow: {metadata['flow_name']}")
        print(f"Description: {metadata['flow_description']}")
        print(f"Operators: {metadata['num_operators']}")
        print(f"Job ID: {metadata['job_id']}")
        print(f"Job Run ID: {metadata['job_run_id']}")

        # Execute the flow
        print("\nExecuting flow...")
        manager.execute()

        # Check execution status
        status = None
        if manager.orchestrator:
            job_stats_service = getattr(manager.orchestrator, "job_stats_service", None)
            if job_stats_service:
                try:
                    job_stats = job_stats_service.get_job_run_stats(job_run_id=manager.job_run_id)
                    if job_stats and hasattr(job_stats, "status"):
                        status = job_stats.status
                except Exception as e:
                    print(f"Warning: Could not retrieve job status: {e}")

        if status == "Completed":
            print("\nExecution completed successfully!")
            print(f"Status: {status}")
        else:
            print(f"\nExecution ended with status: {status}")

    except Exception as e:
        print(f"\nExecution failed: {e}")
    finally:
        # Cleanup
        if test_dir:
            print("\nCleaning up test data...")
            cleanup_test_data(test_dir)


if __name__ == "__main__":
    main()
