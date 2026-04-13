"""
DatasiftFlowManager Example 5: Jupyter Notebook Usage Pattern

This example demonstrates the typical pattern for using DatasiftFlowManager
in a Jupyter notebook environment.

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
    python examples/datasift_flow_manager/05_notebook_usage.py
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
else:
    # When installed as a package
    pass


def main():
    """
    Jupyter Notebook Usage Pattern

    This example shows the typical pattern for using DatasiftFlowManager
    in a Jupyter notebook environment.
    """
    print("\n" + "=" * 70)
    print("Example 5: Jupyter Notebook Usage Pattern")
    print("=" * 70)

    print("""
# Typical Jupyter Notebook Usage:

IMPORTANT: Before starting Jupyter, activate the backend virtual environment:
    source src/datasift_opensource/backend/.venv/bin/activate
    export PYTHONPATH="$(pwd)/src/datasift_opensource/backend:${PYTHONPATH}"
    jupyter notebook

```python
# Cell 1: Import and setup
import sys
from pathlib import Path

# Add backend to path for local development
backend_path = Path.cwd().parent.parent / "src" / "datasift_opensource" / "backend"
sys.path.insert(0, str(backend_path))
from lib.datasift_flow_manager import DatasiftFlowManager

# Cell 2: List available operators
print(DatasiftFlowManager.list_operators())

# Cell 3: Define or load flow
flow_file = "path/to/your/flow.json"

# Or define inline:
flow_def = {
    "name": "My Notebook Flow",
    "dag": [
        # ... operator definitions
    ]
}

# Cell 4: Create flow manager
manager = DatasiftFlowManager(
    flow_file=flow_file,  # or flow_def=flow_def
    log_level="info"
)

# Cell 5: Check metadata
metadata = manager.get_execution_metadata()
print(f"Flow: {metadata['flow_name']}")
print(f"Operators: {metadata['num_operators']}")

# Cell 6: Execute
result = manager.execute()

# Cell 7: Analyze results
# Work with the result DataAccess object
print(f"Execution completed: {result}")
```

Key Benefits for Notebooks:
- Clean, simple API
- Step-by-step execution
- Easy to inspect metadata
- Good error messages
- No need to manage CLI arguments
    """)


if __name__ == "__main__":
    main()
