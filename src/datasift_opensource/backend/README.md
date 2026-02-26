# Backend

This directory contains all backend components of the datasift-open project, including the core framework, operators, and orchestration logic.

## Structure

### config/
Configuration management utilities for the backend services.

### common/
Shared utilities, models, and exceptions used across backend components.

### core/
Core orchestration framework including:
- **orchestrator/** - Flow orchestration (cmdline, python)
- **data_access/** - Data access layer
- **plugins/** - Plugin system
- **runtime_jobs/** - Runtime job execution

### operators/
Python-based operator implementations:
- **language/** - Language processing operators
- **transform/** - Data transformation operators
- **validation/** - Data validation operators
- **universal/** - Universal operators
- **custom/** - Custom operator support

### app/
Backend API application (if needed for web services).

### orchestrator/
Legacy orchestrator components (to be migrated to core/).

## Purpose

The backend layer provides:
- Data processing orchestration
- Operator execution framework
- Configuration management
- Plugin system for extensibility
- API services (optional)

All backend components are Python-based with no Spark dependencies.

## Import Structure

**Important**: The `backend` directory is the source root for all imports. When setting up your development environment, ensure `PYTHONPATH` points to `src/datasift_opensource/backend`.

### Import Examples

All imports should be relative to the backend directory:

```python
# Correct imports
from common.util.constants import DatasiftConstants
from common.exceptions.datasift_exceptions import DatasiftException
from core.operators.abstract_operator import AbstractOperator
from core.orchestrator.operator_factory import OperatorFactory
from app.models.session_info import SessionInfo

# Incorrect imports (DO NOT USE)
from datasift_opensource.backend.common.util.constants import DatasiftConstants
```

### Setting PYTHONPATH

For development and testing:

```bash
# From project root
export PYTHONPATH="$(pwd)/src/datasift_opensource/backend:${PYTHONPATH}"

# Or from backend directory
export PYTHONPATH="$(cd ../../.. && pwd)/src/datasift_opensource/backend:${PYTHONPATH}"
```

This ensures all imports resolve correctly without needing the full `datasift_opensource.backend` prefix.

## Command-Line Orchestrator

The command-line orchestrator allows you to execute data processing flows and manage operators from the command line.

### Running Flows

Execute a flow definition from a JSON file:

```bash
python -m core.orchestrator.cmdline.cmd_line_orchestrator --flow-file path/to/flow.json
```

Options:
- `--flow-file, -f`: Path to the JSON file containing the flow definition (required for execution)
- `--log-level, -l`: Set logging level (choices: debug, info, warning, error, critical; default: info)

Example:
```bash
python -m core.orchestrator.cmdline.cmd_line_orchestrator \
  --flow-file tests/flow_local.json \
  --log-level debug
```

### Listing Available Operators

To see all available operators and their details:

```bash
# Show summary of all operators
python -m core.orchestrator.cmdline.cmd_line_orchestrator --list-operators

# Show detailed information about each operator
python -m core.orchestrator.cmdline.cmd_line_orchestrator --list-operators --verbose
```

The `--list-operators` command displays:
- **Summary mode** (default): A table showing operator name, category, availability status, and feature count
- **Verbose mode** (`--verbose` or `-v`): Detailed information including:
  - Output features (columns produced by the operator)
  - Configuration parameters (input parameters for the operator)
  - Required input features (columns needed by the operator)
  - Data types, descriptions, and default values

Example output (summary):
```
================================================================================
AVAILABLE OPERATORS SUMMARY
================================================================================

Operator                  Category        Status       Features
--------------------------------------------------------------------------------
ingest_local              Ingest          Available    3
extract_docling           Extract         Available    5
docling_chunker           Functional      Available    2
...
```

Example output (verbose):
```
================================================================================
Operator: ingest_local
Category: Ingest
Status: ✓ Available
================================================================================

Output Features (3):
  • path: File Path
  • binary_content: Binary Content
  • doc_id_hash: Hash ID

Configuration Parameters (3):
  • max_file_size [OPTIONAL]: Max File Size (default: 100)
  • include_filter [OPTIONAL]: Include File Type (default: pdf,docx,pptx,txt,md)
  • store_binary_content [OPTIONAL]: Store Binary Content (default: True)
```

This feature is particularly useful for:
- Understanding what operators are available in your installation
- Discovering operator capabilities and output features
- Learning what configuration parameters each operator accepts
- Planning your data processing flows