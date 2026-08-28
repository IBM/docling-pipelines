# My Custom Operators Package

Example package demonstrating how to distribute custom Docling Pipelines operators as a pip-installable package.

## Installation

```bash
# Install from local directory (development mode)
uv pip install -e .

# Or build and install
uv pip install .
```

## Verify Installation

After installation, verify the operators are registered:

```bash
docling-pipelines --list-operators --verbose
```

You should see `uppercase_text` and `reverse_text` in the operator list.

## Usage

### Method 1: Environment Variable (Recommended)

Set the `DOCPIPE_CUSTOM_OPERATORS` environment variable to enable auto-discovery:

```bash
export DOCPIPE_CUSTOM_OPERATORS="my_custom_operators"
docling-pipelines --flow-file sample_flows/custom_operators/custom_operators_demo.json
```

### Method 2: Flow Configuration

Alternatively, specify the package in your flow configuration:

```json
{
  "custom_operators": {
    "adapters": [
      {
        "type": "package",
        "package_name": "my_custom_operators"
      }
    ]
  }
}
```

### Method 3: Python API

Using the Python API:

```python
from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager

# Operators will be auto-discovered from the installed package
manager = DocpipeFlowManager(flow_file="flow.json")
result = manager.execute()
```

## Demo Flow

A complete demo flow is available at `sample_flows/custom_operators/custom_operators_demo.json` that demonstrates both operators in action:

```bash
# Run the demo (requires DOCPIPE_CUSTOM_OPERATORS environment variable)
export DOCPIPE_CUSTOM_OPERATORS="my_custom_operators"
docling-pipelines --flow-file sample_flows/custom_operators/custom_operators_demo.json
```

The demo flow:
1. Ingests a text file
2. Extracts text content
3. Converts text to uppercase using `UppercaseOperator`
4. Reverses the text using `ReverseOperator`

## Included Operators

- **UppercaseOperator** (`uppercase_text`): Converts text to uppercase
- **ReverseOperator** (`reverse_text`): Reverses text content

## Package Structure

```
my_custom_operators/
├── __init__.py
└── operators/
    ├── __init__.py
    ├── uppercase_operator.py
    └── reverse_operator.py
```

## Entry Points

This package registers operators via entry points in `pyproject.toml`:

```toml
[project.entry-points."docpipe.operators"]
uppercase_text = "my_custom_operators.operators.uppercase_operator:UppercaseOperator"
reverse_text = "my_custom_operators.operators.reverse_operator:ReverseOperator"
