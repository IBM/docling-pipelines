# Examples

This directory contains example flows and usage patterns for the datasift-open project.

## Contents

### Basic Examples
- `simple_transform.json` - Basic data transformation flow
- `validation_flow.json` - Data validation example
- `language_detection.json` - Language processing example

### Advanced Examples
- `multi_step_pipeline.json` - Complex multi-step data pipeline
- `custom_operator_flow.json` - Using custom operators
- `plugin_integration.json` - Plugin system usage

### Use Cases
- Data cleaning and preparation
- Text processing and analysis
- Data validation and quality checks
- Format conversion

## Running Examples

```bash
# Run a simple example
python -m datasift_opensource.backend.core.orchestrator.cmdline.cmd_line_orchestrator --flow-file examples/simple_transform.json

# Run with custom configuration
python -m datasift_opensource.backend.core.orchestrator.cmdline.cmd_line_orchestrator --flow-file examples/validation_flow.json --config config.yaml
```

## Creating Your Own Flows

1. Copy an example flow as a template
2. Modify operators and parameters
3. Add your data sources and destinations
4. Test locally before deployment

## Flow Configuration Format

```json
{
  "flow_id": "example_flow",
  "operators": [
    {
      "id": "op1",
      "type": "TransformOperator",
      "config": {
        "param1": "value1"
      }
    }
  ]
}
```

See individual example files for detailed configurations.