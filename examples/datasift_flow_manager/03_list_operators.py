"""
DatasiftFlowManager Example 3: List Available Operators

This example demonstrates how to discover available operators and their
configuration options using the DatasiftFlowManager class method.

Prerequisites:
- Backend virtual environment activated: source src/datasift_opensource/backend/.venv/bin/activate
- PYTHONPATH set to backend directory: export PYTHONPATH="$(pwd)/src/datasift_opensource/backend:${PYTHONPATH}"

Setup (from repository root):
    cd src/datasift_opensource/backend
    python3.12 -m venv .venv
    source .venv/bin/activate
    uv sync --extra dev
    cd ../../..
    export PYTHONPATH="$(pwd)/src/datasift_opensource/backend:${PYTHONPATH}"

Run:
    source src/datasift_opensource/backend/.venv/bin/activate
    python examples/datasift_flow_manager/03_list_operators.py
"""


# When installed as a package
from datasift_opensource.backend.datasift_flow_manager import DatasiftFlowManager


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
    summary = DatasiftFlowManager.list_operators(verbose=False)
    print(summary)

    # List operators with details
    print("\n--- Detailed Operator Information ---")
    details = DatasiftFlowManager.list_operators(verbose=True)
    print(details)


if __name__ == "__main__":
    main()
