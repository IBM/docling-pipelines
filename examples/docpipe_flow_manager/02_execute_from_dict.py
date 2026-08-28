"""
DocpipeFlowManager Example 2: Execute Flow from Dictionary

This example demonstrates how to programmatically construct or modify flow
definitions before execution using a Python dictionary.

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
    python examples/docpipe_flow_manager/02_execute_from_dict.py
"""

import uuid

from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager


def main():
    """
    Execute a flow from a dictionary

    This approach is useful when you want to programmatically construct
    or modify flow definitions before execution.
    """
    print("\n" + "=" * 70)
    print("Example 2: Execute Flow from Dictionary")
    print("=" * 70)

    # Define flow as a dictionary using the authoring format
    flow_def = {
        "flow_name": "Programmatic Flow Example",
        "flow_id": "programmatic-001",
        "description": "A flow created programmatically from Python",
        "global_config": {
            "storage": "in-memory",
            "execute_type": "local",
            "doc_column": "content",
            "disable_validation": True,
            "force_ingest": True,
        },
        "flow": [
            {
                "name": "ingest",
                "type": "ingest_source",
                "config": {
                    "provider": "filesystem",
                    "paths": ["./tests/fixtures/invoices"],
                    "include_filter": "pdf",
                },
            },
            {
                "name": "extract",
                "type": "extract_operator",
                "config": {
                    "text_extraction": {
                        "provider": "docling_library",
                        "doc_column": "content",
                        "provider_config": {"additional_formats": ["html", "json"]},
                    },
                    "entity_extraction": {"provider": "none"},
                },
                "depends_on": ["ingest"],
            },
        ],
    }

    # Create flow manager with flow definition
    manager = DocpipeFlowManager(flow_def=flow_def, job_id=str(uuid.uuid4()))

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
