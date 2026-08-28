# External Operator Integration Example

This example demonstrates how an external application can integrate custom operators with docling-pipelines when it's installed as a wheel package.

## Scenario

You have an external application that:
1. Installs `docling-pipelines` as a dependency (wheel package)
2. Has its own custom operators
3. Wants to use both docpipe and custom operators in pipelines

## Directory Structure

```
external_app/
├── pyproject.toml                    # Application dependencies
├── external_app/
│   ├── __init__.py                   # Register operators at startup
│   ├── main.py                       # Application entry point
│   ├── operators/
│   │   ├── __init__.py               # Define APP_OPERATORS frozenset
│   │   ├── uppercase_operator.py     # Example custom operator
│   │   └── reverse_operator.py       # Example custom operator
│   └── flows/
│       └── example_flow.json         # Flow using custom operators
└── tests/
    └── test_integration.py           # Integration tests
```

## Files

### 1. pyproject.toml

```toml
[project]
name = "external-app"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "docling-pipelines>=0.1.0",  # Install docpipe as wheel
]

[project.scripts]
external-app = "external_app.main:main"
```

### 2. external_app/operators/uppercase_operator.py

```python
"""Custom operator that converts text to uppercase."""
from docpipe.core.operators.abstract_operator import AbstractOperator
from docpipe.core.constants.constants import DocpipeConstants
import pyarrow as pa
import pyarrow.compute as pc


class UppercaseOperator(AbstractOperator):
    """Converts all text columns to uppercase."""

    short_name = "uppercase"
    owner = DocpipeConstants.OWNER_CUSTOM  # Priority 100 (can override OSS operators)

    def __init__(self, *, config: dict):
        super().__init__(config=config)
        self.target_column = config.get("target_column", "contents")

    def transform(self, table: pa.Table) -> pa.Table:
        """Convert target column to uppercase."""
        if self.target_column not in table.column_names:
            self.logger.warning(f"Column '{self.target_column}' not found")
            return table

        # Get the column
        column = table.column(self.target_column)

        # Convert to uppercase using PyArrow compute
        uppercase_column = pc.utf8_upper(column)

        # Replace the column
        column_index = table.column_names.index(self.target_column)
        new_table = table.set_column(column_index, self.target_column, uppercase_column)

        self.logger.info(f"Converted {len(new_table)} rows to uppercase")
        return new_table

    @staticmethod
    def is_available() -> bool:
        """Check if operator is available."""
        return True
```

### 3. external_app/operators/reverse_operator.py

```python
"""Custom operator that reverses text."""
from docpipe.core.operators.abstract_operator import AbstractOperator
from docpipe.core.constants.constants import DocpipeConstants
import pyarrow as pa


class ReverseOperator(AbstractOperator):
    """Reverses text in specified column."""

    short_name = "reverse"
    owner = DocpipeConstants.OWNER_CUSTOM  # Priority 100 (can override OSS operators)

    def __init__(self, *, config: dict):
        super().__init__(config=config)
        self.target_column = config.get("target_column", "contents")

    def transform(self, table: pa.Table) -> pa.Table:
        """Reverse text in target column."""
        if self.target_column not in table.column_names:
            self.logger.warning(f"Column '{self.target_column}' not found")
            return table

        # Get the column as Python list
        column_data = table.column(self.target_column).to_pylist()

        # Reverse each string
        reversed_data = [text[::-1] if isinstance(text, str) else text for text in column_data]

        # Create new column
        reversed_column = pa.array(reversed_data)

        # Replace the column
        column_index = table.column_names.index(self.target_column)
        new_table = table.set_column(column_index, self.target_column, reversed_column)

        self.logger.info(f"Reversed {len(new_table)} rows")
        return new_table

    @staticmethod
    def is_available() -> bool:
        """Check if operator is available."""
        return True
```

### 4. external_app/operators/__init__.py

```python
"""Operator registry for external application."""
from external_app.operators.uppercase_operator import UppercaseOperator
from external_app.operators.reverse_operator import ReverseOperator

# Define application's operator frozenset
APP_OPERATORS = frozenset({
    UppercaseOperator,
    ReverseOperator,
})

__all__ = ["APP_OPERATORS", "UppercaseOperator", "ReverseOperator"]
```

### 5. external_app/__init__.py

```python
"""External application initialization - register operators."""
from docpipe.core.operators.operator_registry import register_operator_provider
from external_app.operators import APP_OPERATORS


def get_app_operators(orchestrator=None):
    """
    Provider function for application operators.

    Args:
        orchestrator: Optional orchestrator type for filtering

    Returns:
        frozenset: Application operator classes
    """
    # Could filter by orchestrator if needed
    # For this example, return all operators
    return APP_OPERATORS


# Register operators when module is imported
register_operator_provider(get_app_operators)

__all__ = ["get_app_operators"]
```

### 6. external_app/main.py

```python
"""Main application entry point."""
import sys
from pathlib import Path
from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


def main():
    """Run the external application pipeline."""

    # Flow definition using both docpipe and custom operators
    flow_def = {
        "flow_name": "External App Pipeline",
        "flow": [
            {
                "type": "ingest_source",
                "name": "ingest",
                "config": {
                    "provider": "filesystem",
                    "connection_params": {"paths": ["./sample_data"]}
                }
            },
            {
                "type": "uppercase",  # Custom operator!
                "name": "uppercase_text",
                "config": {
                    "target_column": "contents"
                },
                "depends_on": ["ingest"]
            },
            {
                "type": "reverse",  # Custom operator!
                "name": "reverse_text",
                "config": {
                    "target_column": "contents"
                },
                "depends_on": ["uppercase_text"]
            },
            {
                "type": "noop",  # Docling Pipelines operator
                "name": "output",
                "config": {},
                "depends_on": ["reverse_text"]
            }
        ]
    }

    logger.info("Starting external app pipeline")
    logger.info("Using docpipe operators + custom operators")

    try:
        # Create and execute flow
        manager = DocpipeFlowManager(flow_def=flow_def)
        result = manager.execute()

        logger.info("Pipeline completed successfully")
        return 0

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

### 7. external_app/flows/example_flow.json

```json
{
  "flow_name": "External App Example Flow",
  "flow": [
    {
      "type": "ingest_source",
      "name": "ingest",
      "config": {
        "provider": "filesystem",
        "connection_params": {"paths": ["./sample_data"]}
      }
    },
    {
      "type": "uppercase",
      "name": "uppercase_text",
      "config": {
        "target_column": "contents"
      },
      "depends_on": ["ingest"]
    },
    {
      "type": "reverse",
      "name": "reverse_text",
      "config": {
        "target_column": "contents"
      },
      "depends_on": ["uppercase_text"]
    }
  ]
}
```

### 8. tests/test_integration.py

```python
"""Integration tests for external operator registration."""
import pytest
from docpipe.core.operators.operator_registry import (
    register_operator_provider,
    clear_operator_providers,
    get_docpipe_operators,
    get_registered_provider_count
)
from external_app.operators import APP_OPERATORS, UppercaseOperator, ReverseOperator


@pytest.fixture(autouse=True)
def reset_providers():
    """Reset operator providers before each test."""
    clear_operator_providers()
    yield
    clear_operator_providers()


def test_operator_registration():
    """Test that custom operators are registered correctly."""

    def test_provider(orchestrator=None):
        return APP_OPERATORS

    register_operator_provider(test_provider)

    assert get_registered_provider_count() == 1

    operators = get_docpipe_operators()
    short_names = {op.short_name for op in operators}

    # Check custom operators are present
    assert "uppercase" in short_names
    assert "reverse" in short_names

    # Check docpipe operators are still present
    assert "ingest_source" in short_names
    assert "noop" in short_names


def test_operator_availability():
    """Test that custom operators are available."""
    assert UppercaseOperator.is_available()
    assert ReverseOperator.is_available()


def test_operator_short_names():
    """Test that operators have correct short names."""
    assert UppercaseOperator.short_name == "uppercase"
    assert ReverseOperator.short_name == "reverse"


def test_multiple_providers():
    """Test registering multiple providers."""

    def provider1(orchestrator=None):
        return frozenset({UppercaseOperator})

    def provider2(orchestrator=None):
        return frozenset({ReverseOperator})

    register_operator_provider(provider1)
    register_operator_provider(provider2)

    assert get_registered_provider_count() == 2

    operators = get_docpipe_operators()
    short_names = {op.short_name for op in operators}

    assert "uppercase" in short_names
    assert "reverse" in short_names
```

## Usage

### Installation

```bash
# Install docling-pipelines wheel
pip install docling-pipelines-0.1.0-py3-none-any.whl

# Install external application
cd external_app
pip install -e .
```

### Running

```bash
# Run the application
external-app

# Or run directly
python -m external_app.main

# Or use flow file
docling-pipelines --flow-file external_app/flows/example_flow.json
```

### Testing

```bash
# Run tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test
pytest tests/test_integration.py::test_operator_registration
```

## Key Points

1. **Automatic Registration**: Operators are registered when `external_app` module is imported
2. **Seamless Integration**: Custom operators work alongside docpipe operators
3. **No Docling Pipelines Modification**: Docling Pipelines codebase remains unchanged
4. **Type Safety**: Custom operators inherit from `AbstractOperator`
5. **Priority-Based Resolution**: Custom operators (priority 100) can override OSS operators (priority 200)
6. **Testable**: Easy to test operator registration and functionality

## Operator Priority System

Docling Pipelines uses priority-based resolution for operators with the same `short_name`. Set `owner = DocpipeConstants.OWNER_CUSTOM` on your operators.

For the full priority levels, override rules, and registering custom tiers, see [External Operator Integration — Operator Priority](../docs/guides/EXTERNAL_OPERATOR_INTEGRATION.md#operator-priority-and-override).

## Troubleshooting

### Operators Not Found

If custom operators are not found in flows:

1. Ensure `external_app` is imported before using docpipe
2. Check that `register_operator_provider()` is called
3. Verify operators are in `APP_OPERATORS` frozenset
4. Check logs for registration errors

### Import Errors

If you get import errors:

1. Verify docling-pipelines wheel is installed
2. Check Python version (>=3.12 required)
3. Ensure PYTHONPATH includes docpipe package

## Next Steps

- Add more custom operators
- Implement orchestrator-specific filtering
- Add operator validation logic
- Create more complex pipelines
- Add monitoring and metrics
