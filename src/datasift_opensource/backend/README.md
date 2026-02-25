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