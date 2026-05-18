# NOOP Operator - Configuration Reference

## Overview

The NOOP (No Operation) Operator is a pass-through operator used for testing and debugging workflows. It copies input data to output without modifications, optionally adding a configurable sleep delay for testing timing and performance scenarios.

- **Operator Name:** `noop`
- **Category**: Functional
- **Short Name**: `noop`

## Output Behavior

The NOOP Operator:
- Passes through all input data unchanged
- Preserves all columns and rows
- Adds no new columns
- Modifies no existing data
- Optionally sleeps for specified duration

**Metadata Structure:**
```json
{
  "nfiles": 0,
  "nrows": 100,
  "processed_docs": 100,
  "total_docs_count": 100,
  "node_status": "COMPLETED"
}
```

## Best Practices

1. **Development**: Use NOOP to test flow structure before implementing real operators
2. **Debugging**: Insert NOOP between operators to isolate issues
3. **Performance**: Use `sleep_sec: 0` for fast pass-through
4. **Testing**: Use `sleep_sec > 0` to simulate slow operations
5. **Production**: Remove NOOP operators before production deployment

## Example Workflow

```json
{
  "flow_name": "NOOP Test Pipeline",
  "description": "Simple pipeline demonstrating NOOP operator usage",
  "flow": [
    {
      "name": "ingest",
      "type": "ingest_local",
      "config": {
        "path": "./data"
      }
    },
    {
      "name": "noop_test",
      "type": "noop",
      "depends_on": ["ingest"],
      "config": {
        "sleep_sec": 5
      }
    }
  ]
}
```

## Validation Rules

- `sleep_sec` must be a non-negative integer
- No other validation required (operator accepts all input data)

## Notes

- This operator is primarily for development and testing
- Should not be used in production workflows
- Has minimal performance impact when `sleep_sec: 0`
- Useful for understanding flow execution patterns
- Can be used to test error handling and retry logic
