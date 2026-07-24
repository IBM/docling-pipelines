"""
DocpipeFlowManager Example 4: Custom Configuration and Error Handling

This example demonstrates advanced usage with custom job IDs, error handling,
and metadata extraction.

Prerequisites:
- Backend virtual environment activated: source src/docpipe_app/backend/.venv/bin/activate
- PYTHONPATH set to backend directory: export PYTHONPATH="$(pwd)/src/docpipe_app/backend:${PYTHONPATH}"
- Ollama running (for LLM operations): http://localhost:11434
- OpenSearch running (for vector storage): http://localhost:9200

Setup (from repository root):
    cd src/docpipe_app/backend
    python3.12 -m venv .venv
    source .venv/bin/activate
    uv sync --extra dev
    cd ../../..
    export PYTHONPATH="$(pwd)/src/docpipe_app/backend:${PYTHONPATH}"

Run:
    source src/docpipe_app/backend/.venv/bin/activate
    python examples/docpipe_flow_manager/04_custom_configuration.py
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
    sample_content = """Sample document for custom configuration example."""
    sample_file.write_text(sample_content)
    return test_dir


def cleanup_test_data(test_dir):
    """Remove test directory and files"""
    if test_dir.exists():
        shutil.rmtree(test_dir)


def main():
    """
    Custom configuration and error handling

    Demonstrates advanced usage with custom job IDs, error handling,
    and metadata extraction.
    """
    test_dir = None

    try:
        print("\n" + "=" * 70)
        print("Example 4: Custom Configuration")
        print("=" * 70)

        # Create test data
        print("\nCreating test data...")
        test_dir = create_test_data()

        flow_file = "examples/docpipe_flow_manager/sample_flow.json"

        # Create flow manager with custom configuration
        manager = DocpipeFlowManager(
            flow_file=flow_file,
            job_id="notebook-job-001",
            job_run_id="custom-run-12345",
            flow_id="custom-flow-id",
        )

        # Get and display metadata
        metadata = manager.get_execution_metadata()
        print("\nExecution Metadata:")
        for key, value in metadata.items():
            print(f"  {key}: {value}")

        # Execute with error handling
        print("\nExecuting flow with custom configuration...")
        manager.execute()
        print("\nExecution successful!")

        # Access execution metadata after completion
        final_metadata = manager.get_execution_metadata()
        print(f"\nFinal Job Run ID: {final_metadata['job_run_id']}")

    except FileNotFoundError as e:
        print(f"\nFlow file not found: {e}")
    except Exception as e:
        print(f"\nExecution error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Cleanup
        if test_dir:
            print("\nCleaning up test data...")
            cleanup_test_data(test_dir)


if __name__ == "__main__":
    main()
