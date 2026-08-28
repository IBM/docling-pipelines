# External Operator Integration Guide

This guide explains how external applications can integrate their own operators with the docling-pipelines framework when it's installed as a wheel package.

## Overview

The docling-pipelines package provides a **plugin hook pattern** that allows host applications to inject their own operators into the operator registry. This enables seamless integration of custom operators without modifying the docpipe codebase.

## Architecture

```
External Application
├── docling-pipelines (installed wheel)
│   └── operator_registry.py (provides hooks)
└── custom_operators/
    ├── my_operator.py
    └── __init__.py (registers operators)
```

## Quick Start

### 1. Create Your Custom Operators

```python
# external_app/operators/my_custom_operator.py
from docpipe.core.operators.abstract_operator import AbstractOperator
import pyarrow as pa

class MyCustomOperator(AbstractOperator):
    """Custom operator for external application."""

    short_name = "my_custom_op"

    def __init__(self, *, config: dict):
        super().__init__(config=config)
        # Your initialization

    def transform(self, table: pa.Table) -> pa.Table:
        """Transform logic."""
        # Your transformation logic
        return table

    @classmethod
    def is_available(cls) -> bool:
        """Check if operator dependencies are available."""
        return True
```

### 2. Create Operator Registry

```python
# external_app/operators/__init__.py
from external_app.operators.my_custom_operator import MyCustomOperator

# Define your application's operator frozenset
APP_OPERATORS = frozenset({
    MyCustomOperator,
    # Add more operators here
})
```

### 3. Register Operators at Application Startup

```python
# external_app/__init__.py or main.py
from docpipe.core.operators.operator_registry import register_operator_provider
from external_app.operators import APP_OPERATORS

def get_app_operators(orchestrator=None):
    """
    Provider function that returns application operators.

    Args:
        orchestrator: Optional orchestrator type ("python", "spark")

    Returns:
        frozenset: Set of operator classes
    """
    # Optional: Filter by orchestrator
    if orchestrator == "spark":
        return frozenset({
            op for op in APP_OPERATORS
            if hasattr(op, 'supports_spark') and op.supports_spark
        })

    return APP_OPERATORS

# Register at application startup (before using docpipe)
register_operator_provider(get_app_operators)
```

### 4. Use Docling Pipelines with Your Operators

```python
# external_app/pipeline.py
from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

# Your custom operator is now available in flows
flow_def = {
    "flow_name": "My Pipeline",
    "flow": [
        {
            "type": "ingest_source",
            "name": "ingest",
            "config": {"provider": "filesystem", "connection_params": {"paths": ["./data"]}}
        },
        {
            "type": "my_custom_op",  # Your custom operator!
            "name": "custom_processing",
            "config": {"param1": "value1"},
            "depends_on": ["ingest"]
        }
    ]
}

manager = DocpipeFlowManager(flow_def=flow_def)
result = manager.execute()
```

## Advanced Usage

### Orchestrator-Specific Operators

Filter operators based on orchestrator type:

```python
def get_app_operators(orchestrator=None):
    """Return operators filtered by orchestrator."""

    if orchestrator == "python":
        return frozenset({
            PythonOnlyOperator,
            SharedOperator,
        })
    elif orchestrator == "spark":
        return frozenset({
            SparkOnlyOperator,
            SharedOperator,
        })

    # Return all if orchestrator not specified
    return APP_OPERATORS
```

### Multiple Provider Registration

Register multiple operator sources:

```python
from docpipe.core.operators.operator_registry import register_operator_provider

# Register core application operators
register_operator_provider(get_core_operators)

# Register plugin operators
register_operator_provider(get_plugin_operators)

# Register environment-specific operators
register_operator_provider(get_env_specific_operators)
```

### Operator Priority and Override

Docling Pipelines uses a **priority-based resolution system** to handle operators with the same `short_name`. Operators are assigned priorities based on their `owner` attribute:

**Built-in Priority Levels** (lower number = higher priority):
- **Custom operators** (priority 100): Can override inbuilt operators
- **Docling Pipelines operators** (priority 200): Lowest precedence

Additional tiers can be registered at runtime — see [Registering a Custom Priority Tier](#registering-a-custom-priority-tier) below.

#### Setting Operator Owner

```python
from docpipe.core.constants.constants import DocpipeConstants

class CustomExtractOperator(AbstractOperator):
    """Custom extract operator with priority."""

    short_name = "extract"  # Same as docpipe's ExtractOperator
    owner = DocpipeConstants.OWNER_CUSTOM  # Priority 100

    def transform(self, table: pa.Table) -> pa.Table:
        # Custom extraction logic
        return table
```

#### Priority Rules

- **Custom operators CAN override inbuilt operators** (priority 100 < priority 200)
- **Inbuilt operators CANNOT override Custom operators**
- **Same priority**: Last registered wins

#### Example: Custom Operator Overriding OSS

```python
# This custom operator will override docpipe's built-in extract operator
class MyExtractOperator(AbstractOperator):
    short_name = "extract"
    owner = DocpipeConstants.OWNER_CUSTOM  # Priority 100 beats inbuilt priority 200

    def transform(self, table: pa.Table) -> pa.Table:
        # Your custom logic replaces docpipe's extract
        return table
```

#### Registering a Custom Priority Tier

If you need an operator tier with higher precedence than `OWNER_CUSTOM`, register it at startup before operators are loaded. Priorities below 100 outrank all built-in tiers.

```python
from docpipe.core.orchestration.operator_factory import OperatorFactory

# Call once at application startup, before operators are loaded
OperatorFactory.register_owner_priority(owner="my_app", priority=10)

class MyAppOperator(AbstractOperator):
    short_name = "extract"
    owner = "my_app"  # Priority 10 — overrides custom (100) and inbuilt (200)

    def transform(self, table: pa.Table) -> pa.Table:
        return table
```

**Priority ranges:**

| Range | Purpose |
|---|---|
| 0-99 | Consumer tiers above all built-ins |
| 100 | `OWNER_CUSTOM` |
| 101-199 | Consumer tiers between custom and Docling Pipelines built-ins |
| 200 | `OWNER_DOCPIPE` |

**Note:** If you don't set the `owner` attribute, it defaults to `OWNER_CUSTOM` (priority 100).

### Dynamic Operator Loading

Load operators dynamically based on configuration:

```python
def get_app_operators(orchestrator=None):
    """Dynamically load operators based on config."""
    import os
    from importlib import import_module

    operators = set()

    # Load from environment variable
    operator_modules = os.getenv("APP_OPERATOR_MODULES", "").split(",")

    for module_name in operator_modules:
        if module_name.strip():
            try:
                module = import_module(module_name)
                if hasattr(module, "OPERATORS"):
                    operators.update(module.OPERATORS)
            except ImportError as e:
                print(f"Failed to load operators from {module_name}: {e}")

    return frozenset(operators)
```

## API Reference

### `register_operator_provider(provider_func)`

Register an external operator provider function.

**Parameters:**
- `provider_func` (callable): Function that returns frozenset of operator classes
  - Signature: `provider_func(orchestrator: str | None = None) -> frozenset`

**Raises:**
- `TypeError`: If provider_func is not callable

**Example:**
```python
from docpipe.core.operators.operator_registry import register_operator_provider

def my_provider(orchestrator=None):
    return frozenset({MyOperator1, MyOperator2})

register_operator_provider(my_provider)
```

### `clear_operator_providers()`

Clear all registered operator providers. Useful for testing.

**Example:**
```python
from docpipe.core.operators.operator_registry import clear_operator_providers

# Clear all providers
clear_operator_providers()
```

### `get_registered_provider_count()`

Get the number of registered external operator providers.

**Returns:**
- `int`: Number of registered providers

**Example:**
```python
from docpipe.core.operators.operator_registry import get_registered_provider_count

count = get_registered_provider_count()
print(f"Registered providers: {count}")
```

### `get_docpipe_operators(orchestrator=None)`

Get all operators (Docling Pipelines built-ins + external).

**Parameters:**
- `orchestrator` (str, optional): Orchestrator type for filtering

**Returns:**
- `frozenset`: Combined set of operator classes

**Example:**
```python
from docpipe.core.operators.operator_registry import get_docpipe_operators

# Get all operators
all_ops = get_docpipe_operators()

# Get Python-specific operators
python_ops = get_docpipe_operators(orchestrator="python")
```

## Testing

### Unit Testing with Custom Operators

```python
import pytest
from docpipe.core.operators.operator_registry import (
    register_operator_provider,
    clear_operator_providers,
    get_docpipe_operators
)

@pytest.fixture(autouse=True)
def reset_providers():
    """Reset operator providers before each test."""
    clear_operator_providers()
    yield
    clear_operator_providers()

def test_custom_operator_registration():
    """Test that custom operators are registered correctly."""

    def test_provider(orchestrator=None):
        return frozenset({MyTestOperator})

    register_operator_provider(test_provider)

    operators = get_docpipe_operators()
    short_names = {op.short_name for op in operators}

    assert "my_test_op" in short_names
```

## Best Practices

1. **Register Early**: Register operators at application startup, before any Docling Pipelines operations
2. **Use Descriptive Names**: Choose unique `short_name` values to avoid conflicts
3. **Implement `is_available()`**: Check dependencies in the `is_available()` method
4. **Handle Errors Gracefully**: Provider functions should handle errors without crashing
5. **Document Dependencies**: Clearly document any external dependencies your operators require
6. **Test Thoroughly**: Test operator registration and execution in your application context

## Troubleshooting

### Operators Not Found

**Problem**: Custom operators not appearing in flows

**Solution**:
1. Verify registration happens before docpipe usage
2. Check provider function returns frozenset
3. Ensure operators have `short_name` attribute
4. Check logs for registration errors

```python
import logging
logging.basicConfig(level=logging.DEBUG)
# Check logs for operator registration messages
```

### Operator Override Not Working

**Problem**: Custom operator not overriding docpipe operator

**Solution**:
1. Ensure `short_name` matches exactly
2. Set `owner = DocpipeConstants.OWNER_CUSTOM` on your operator
3. Verify priority: Custom (1) can override inbuilt (2)
4. Check logs for priority resolution messages
5. Ensure operator is registered before factory initialization

**Example Debug:**
```python
import logging
logging.basicConfig(level=logging.INFO)

# Look for messages like:
# "Operator 'extract': MyExtractOperator (priority=1) overrides ExtractOperator (priority=2)"
# or
# "Operator 'extract': MyExtractOperator (priority=1) cannot override EnterpriseOp (priority=0)"
```

### Import Errors

**Problem**: Cannot import docpipe modules

**Solution**:
1. Verify docling-pipelines wheel is installed
2. Check Python path includes docpipe package
3. Ensure compatible Python version (>=3.12)

## Example Application Structure

```
external_app/
├── pyproject.toml
├── external_app/
│   ├── __init__.py          # Register operators here
│   ├── main.py              # Application entry point
│   ├── operators/
│   │   ├── __init__.py      # Define APP_OPERATORS
│   │   ├── custom_op1.py
│   │   └── custom_op2.py
│   └── flows/
│       └── pipeline.json    # Flow using custom operators
└── tests/
    └── test_operators.py
```

## See Also

- [Operator Reference](../reference/OPERATORS.md)
- [Custom Operators Guide](CUSTOM_OPERATORS_GUIDE.md)
- [Architecture Documentation](../../ARCHITECTURE.md)
