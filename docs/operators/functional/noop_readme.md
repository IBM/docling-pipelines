# NoopOperator

Pass-through operator that forwards input data unchanged. Short name: `noop` · Category: Functional

## Overview

The NoopOperator copies its input table to output without modification, optionally sleeping for a configurable duration. Use it to test flow structure before implementing real operators, to introduce timing delays for performance testing, or to isolate a problem between two operators by inserting a no-op between them.

## Key Features

- Passes all rows and columns through unchanged
- Adds no new columns to the PyArrow table
- Configurable sleep delay for simulating slow operators
- Zero performance overhead when `sleep_sec` is `0`
- Safe for use in any position in a flow

## Operator Configuration

```json
{
  "name": "noop_step",
  "type": "noop",
  "depends_on": ["previous_op"],
  "config": {
    "sleep_sec": 0
  }
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `sleep_sec` | `int` | No | `0` | Seconds to sleep before passing data through. Use `> 0` to simulate slow operators. |

## Output Columns

This operator adds no columns. The output table is identical to the input table.

## Examples

### Example 1: No-op between two operators (debugging)

```json
{
  "name": "debug_checkpoint",
  "type": "noop",
  "depends_on": ["extract"],
  "config": { "sleep_sec": 0 }
}
```

### Example 2: Simulate a slow operator (performance testing)

```json
{
  "name": "slow_step",
  "type": "noop",
  "depends_on": ["ingest"],
  "config": { "sleep_sec": 5 }
}
```

## Troubleshooting

**Flow completes instantly but you expected a delay** — ensure `sleep_sec` is set to a positive integer, not a float.

**Using noop in production** — remove noop operators before production deployment. They add no value and inflate flow execution time when `sleep_sec > 0`.

## Sample Flow

See [`sample_flows/advanced/quality_branching_merge_pipeline.json`](../../../sample_flows/advanced/quality_branching_merge_pipeline.json) for a complete pipeline example.
