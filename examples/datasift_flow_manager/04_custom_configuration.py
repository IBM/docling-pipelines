"""
DatasiftFlowManager Example 4: Custom Configuration and Error Handling

This example demonstrates advanced usage with custom job IDs, error handling,
and metadata extraction.

Prerequisites:
- Backend virtual environment activated: source src/datasift_opensource/backend/.venv/bin/activate
- PYTHONPATH set to backend directory: export PYTHONPATH="$(pwd)/src/datasift_opensource/backend:${PYTHONPATH}"
- Ollama running (for LLM operations): http://localhost:11434
- OpenSearch running (for vector storage): http://localhost:9200

Setup (from repository root):
    cd src/datasift_opensource/backend
    python3.12 -m venv .venv
    source .venv/bin/activate
    uv sync --extra dev
    cd ../../..
    export PYTHONPATH="$(pwd)/src/datasift_opensource/backend:${PYTHONPATH}"

Run:
    source src/datasift_opensource/backend/.venv/bin/activate
    python examples/datasift_flow_manager/04_custom_configuration.py
"""

from datasift_opensource.backend.datasift_flow_manager import DatasiftFlowManager


def main():
    """
    Custom configuration and error handling

    Demonstrates advanced usage with custom job IDs, error handling,
    and metadata extraction.
    """
    print("\n" + "=" * 70)
    print("Example 4: Custom Configuration")
    print("=" * 70)

    flow_file = "examples/datasift_flow_manager/sample_flow.json"

    # Create flow manager with custom configuration
    manager = DatasiftFlowManager(
        flow_file=flow_file,
        log_level="debug",  # More verbose logging
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
    try:
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


if __name__ == "__main__":
    main()
