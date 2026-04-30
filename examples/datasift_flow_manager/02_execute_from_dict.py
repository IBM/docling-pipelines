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
import uuid

from datasift.lib.datasift_flow_manager import DatasiftFlowManager


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
                "id": "f1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c",
                "name": "ingest",
                "operator": "ingest_local",
                "config": {
                    "input_folder": "./tests/fixtures/invoices",
                    "include_filter": "pdf",
                    "store_binary_content": False,
                },
                "input_edges": [],
                "output_edges": [{"node_id_ref": "e2b3c4d5-f6a7-4b8c-9d0e-1f2a3b4c5d6e"}],
            },
            {
                "id": "e2b3c4d5-f6a7-4b8c-9d0e-1f2a3b4c5d6e",
                "name": "extract",
                "operator": "extract_operator",
                "config": {"doc_column": "content"},
                "input_edges": [{"node_id_ref": "f1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c"}],
                "output_edges": [],
            },
        ],
    }

    # Create flow manager with flow definition
    manager = DatasiftFlowManager(
        flow_def=flow_def, log_level="info", job_id=str(uuid.uuid4())
    )

    # Execute
    print("\nExecuting programmatically defined flow...")
    try:
        manager.execute()
        print("\nExecution completed successfully!")
        print("Execution logs:")
        for line in manager.get_execution_logs():
            print(line)
    except Exception as e:
        print(f"\nExecution failed: {e}")


if __name__ == "__main__":
    main()
