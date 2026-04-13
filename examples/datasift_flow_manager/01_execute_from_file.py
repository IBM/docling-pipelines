"""
DatasiftFlowManager Example 1: Execute Flow from File

This example demonstrates the simplest way to use DatasiftFlowManager - just provide
a path to your flow definition JSON file.

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
    python examples/datasift_flow_manager/01_execute_from_file.py
"""

import sys
from pathlib import Path

# Add backend to path for local development
# In production, use: from datasift_opensource.backend.datasift_flow_manager import DatasiftFlowManager
backend_path = (
    Path(__file__).parent.parent.parent / "src" / "datasift_opensource" / "backend"
)
if backend_path.exists():
    sys.path.insert(0, str(backend_path))
    from datasift_flow_manager import DatasiftFlowManager
else:
    # When installed as a package
    from datasift_opensource.backend.datasift_flow_manager import DatasiftFlowManager


def main():
    """
    Execute a flow from a JSON file

    This is the simplest way to use DatasiftFlowManager - just provide a path
    to your flow definition JSON file.
    """
    print("\n" + "=" * 70)
    print("Example 1: Execute Flow from File")
    print("=" * 70)

    # Path to the flow definition file
    flow_file = "examples/datasift_flow_manager/sample_flow.json"

    # Create flow manager
    manager = DatasiftFlowManager(flow_file=flow_file, log_level="info")

    # Get metadata before execution
    metadata = manager.get_execution_metadata()
    print(f"\nFlow: {metadata['flow_name']}")
    print(f"Description: {metadata['flow_description']}")
    print(f"Operators: {metadata['num_operators']}")
    print(f"Job ID: {metadata['job_id']}")
    print(f"Job Run ID: {metadata['job_run_id']}")

    # Execute the flow
    print("\nExecuting flow...")
    try:
        result = manager.execute()
        print("\nExecution completed successfully!")
        print(f"Result type: {type(result)}")
    except Exception as e:
        print(f"\nExecution failed: {e}")


if __name__ == "__main__":
    main()
