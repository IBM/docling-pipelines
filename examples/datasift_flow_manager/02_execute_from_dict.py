"""
DatasiftFlowManager Example 2: Execute Flow from Dictionary

This example demonstrates how to programmatically construct or modify flow
definitions before execution using a Python dictionary.

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
    python examples/datasift_flow_manager/02_execute_from_dict.py
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
    from lib.datasift_flow_manager import DatasiftFlowManager
else:
    # When installed as a package
    from datasift_opensource.backend.datasift_flow_manager import DatasiftFlowManager


def main():
    """
    Execute a flow from a dictionary

    This approach is useful when you want to programmatically construct
    or modify flow definitions before execution.
    """
    print("\n" + "=" * 70)
    print("Example 2: Execute Flow from Dictionary")
    print("=" * 70)

    # Define flow as a dictionary with proper DAG structure
    flow_def = {
        "name": "Programmatic Flow Example",
        "flow_id": "programmatic-001",
        "description": "A flow created programmatically from Python",
        "storage": "in-memory",
        "execute_type": "local",
        "global_config": {
            "doc_column": "content",
            "disable_validation": "true",
            "force_ingest": True,
        },
        "dag": [
            {
                "id": "ingest-node",
                "name": "ingest",
                "operator": "ingest_local",
                "config": {
                    "input_folder": "./tests/fixtures/invoices",
                    "include_filter": "pdf",
                    "store_binary_content": "false",
                },
                "input_edges": [],
                "output_edges": [{"node_id_ref": "extract-node"}],
            },
            {
                "id": "extract-node",
                "name": "extract",
                "operator": "extract_operator",
                "config": {"doc_column": "content"},
                "input_edges": [{"node_id_ref": "ingest-node"}],
                "output_edges": [],
            },
        ],
    }

    # Create flow manager with flow definition
    manager = DatasiftFlowManager(
        flow_def=flow_def, log_level="info", job_id="custom-job-001"
    )

    # Execute
    print("\nExecuting programmatically defined flow...")
    try:
        manager.execute()
        print("\nExecution completed successfully!")
    except Exception as e:
        print(f"\nExecution failed: {e}")


if __name__ == "__main__":
    main()
