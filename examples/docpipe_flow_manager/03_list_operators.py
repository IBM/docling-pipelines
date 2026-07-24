"""
DocpipeFlowManager Example 3: List Available Operators

This example demonstrates how to discover available operators and their
configuration options using the DocpipeFlowManager class method.

Prerequisites:
- Backend virtual environment activated: source src/docpipe_app/backend/.venv/bin/activate
- PYTHONPATH set to backend directory: export PYTHONPATH="$(pwd)/src/docpipe_app/backend:${PYTHONPATH}"

Setup (from repository root):
    cd src/docpipe_app/backend
    python3.12 -m venv .venv
    source .venv/bin/activate
    uv sync --extra dev
    cd ../../..
    export PYTHONPATH="$(pwd)/src/docpipe_app/backend:${PYTHONPATH}"

Run:
    source src/docpipe_app/backend/.venv/bin/activate
    python examples/docpipe_flow_manager/03_list_operators.py
"""

# When installed as a package
from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager


def main():
    """
    List all available operators

    Use this to discover what operators are available and their
    configuration options.
    """
    print("\n" + "=" * 70)
    print("Example 3: List Available Operators")
    print("=" * 70)

    # List operators with summary
    print("\n--- Operator Summary ---")
    summary = DocpipeFlowManager.list_operators(verbose=False)
    print(summary)

    # List operators with details
    print("\n--- Detailed Operator Information ---")
    details = DocpipeFlowManager.list_operators(verbose=True)
    print(details)


if __name__ == "__main__":
    main()
