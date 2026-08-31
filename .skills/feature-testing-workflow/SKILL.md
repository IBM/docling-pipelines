---
name: feature-testing-workflow
description: >-
  Exercise observable docpipe feature behavior without depending on pytest or existing test
  cases. Use for operator, pipeline, ingest-provider, orchestration, REST API, or Python API
  validation by building a small runnable scenario, executing a public entrypoint, checking
  runtime artifacts or service state, and reporting reproducible evidence. Do not use when the
  user specifically asks to write automated tests.
---

# Feature Testing Workflow

Validate a feature through the same public surface a user would exercise. Build a self-contained scenario with its own inputs and acceptance checks; existing unit or integration tests are optional supporting evidence, never a prerequisite.

## Required outcome

Produce a feature-validation bundle containing:

- the behavior being tested and its observable acceptance criteria;
- minimal test input owned by this run;
- a flow, API request sequence, or Python runner that exercises the feature;
- executable verification that does not import pytest;
- a concise result with commands, evidence, failures, and environmental limitations.

A zero exit code alone is not proof that the feature works.

## Core rules

1. Exercise the narrowest public entrypoint that proves the behavior: CLI flow by default, REST API for route-only features, or `DocpipeFlowManager` for library-only behavior.
2. Do not require existing tests to pass before running this workflow. Do not create pytest cases unless the user separately requests automated coverage.
3. Derive current configuration from the implementation, `docs/reference/OPERATORS.md`, `docs/reference/GLOBAL_CONFIG.md`, and the closest current file in `sample_flows/`. Do not reuse stale operator names or parameters from memory.
4. State the acceptance contract before execution. Every criterion must be observable in output tables, job statistics, API responses, logs, or external service state.
5. Create run artifacts in a temporary directory. Do not add ad hoc flows to `sample_flows/` or commit generated inputs, credentials, logs, or outputs.
6. Validate a flow before executing it. Keep `disable_validation` false.
7. Use real external services only when they are part of the behavior under test. Preflight them, use isolated resource names, and never silently replace the requested provider with a mock or different provider.
8. Do not expose credentials in generated files, commands, reports, or logs. Reference environment variables from flow configuration.
9. Do not modify production code while performing a validation-only request. Diagnose failures and report them unless the user also asked for a fix.

## Choose the scenario

### Operator or pipeline behavior

Create the smallest valid DAG that reaches the feature. A flow has exactly one root and that root is an ingest operator.

- Start with `ingest_source` using the filesystem provider and one to three small documents when local input is sufficient.
- Add only the upstream operators needed to produce required columns.
- Put the operator under test immediately after those prerequisites.
- Add a downstream operator only when downstream compatibility is part of the acceptance contract.
- Do not automatically add Chunker, Embeddings, or VectorDB.

### Ingest source provider

Use `ingest_source` with the provider under test. Verify discovery, filtering, document metadata, row counts, and lazy binary retrieval through a downstream extraction step when binary retrieval is part of the feature.

### REST API behavior

Run the local API and send real HTTP requests to the route. Verify status, response schema, persisted state, authentication behavior, and transaction identifiers as applicable. Do not substitute an in-process test client unless the user asks for automated API tests.

### Python library behavior

Create a small runner that calls `DocpipeFlowManager` with the scenario flow and verifies its returned result plus persisted artifacts. Keep runner logic outside `src/`.

When choosing a scenario, read [references/scenarios.md](references/scenarios.md) and start from the closest maintained sample. Reduce it to the behavior under test instead of copying a full pipeline unchanged.

## Workflow

### 1. Define the acceptance contract

Write a short Given/When/Then scenario and turn it into explicit checks. Include:

- expected job and node status;
- expected input and output row counts;
- required output columns and important values;
- expected failed and skipped document counts;
- expected external record, index, file, or API state;
- any behavior that must not occur.

Separate feature assertions from integrity assertions. For example, verifying that a new enrichment column contains the expected value is a feature assertion; verifying that no input document disappeared is an integrity assertion.

### 2. Prepare isolated artifacts

Create a temporary directory with `mktemp -d` and place the scenario flow, generated input, runner, and feature-specific verifier there. Use paths that resolve correctly when commands run from the repository root.

Prefer an existing small fixture from `tests/fixtures/` when it expresses the scenario. Generate a new temporary input when precise content is needed. Never alter shared fixtures for an ad hoc run.

### 3. Build the runner

For a CLI flow, start from the closest current sample and reduce it. A typical local root is:

```json
{
  "flow_name": "temporary-feature-validation",
  "global_config": {
    "doc_column": "content",
    "disable_validation": false,
    "force_ingest": true,
    "enable_micro_batching": false,
    "data_storage_type": "local"
  },
  "flow": [
    {
      "type": "ingest_source",
      "name": "ingest",
      "config": {
        "provider": "filesystem",
        "connection_params": {
          "paths": ["tests/fixtures/customer_support_docs"]
        },
        "include_filter": "txt",
        "max_files": 3
      }
    }
  ]
}
```

Change the flow name for each independent scenario when incremental metadata could affect results. Set `enable_micro_batching` explicitly: false for a deterministic baseline, true only when micro-batching is itself being tested or a second parity run is required.

When testing a custom operator, set `DOCPIPE_CUSTOM_OPERATORS` for validation and execution and verify that `docling-pipelines --list-operators --verbose` shows its `short_name`.

### 4. Preflight and validate

Activate the project environment first:

```bash
source .venv/bin/activate
docling-pipelines --flow-file /path/to/temporary-flow.json --validate
```

Resolve validation failures before execution. Preflight only the external dependencies used by the scenario. If a required service is unavailable:

- run a smaller local slice only if it still proves a distinct acceptance criterion;
- mark the external criterion `BLOCKED`, not `PASS`;
- report the exact prerequisite and rerun command.

The user's request to run feature validation authorizes ordinary local execution and temporary files. Ask before testing against a shared or production-like external system, creating costly resources, or performing destructive cleanup.

### 5. Execute through the public surface

Run from the repository root and capture combined output in the temporary bundle:

```bash
source .venv/bin/activate
docling-pipelines --flow-file /path/to/temporary-flow.json
```

Record the flow path, start time, command, exit code, `job_id`, and `job_run_id`. Stop retrying after one repeat with the same failure unless a concrete environmental correction was made.

### 6. Verify independently of test cases

Run the bundled baseline verifier against the generated run artifacts:

```bash
source .venv/bin/activate
python .skills/feature-testing-workflow/scripts/verify_flow_run.py \
  --started-after 2026-08-31T10:00:00+00:00 \
  --expect-node ingest \
  --min-rows ingest:1
```

Add feature-specific checks in a temporary `verify.py` or direct service query. Use explicit failures and a nonzero exit code; do not import pytest. Verify the actual values described in the acceptance contract, not only the presence of files or columns.

Useful evidence sources include:

- `data/{job_id}/{job_run_id}/docpipe_logs/job_stats.json`;
- `data/{job_id}/{job_run_id}/data/{node_name}_*/output.parquet`;
- `job_report_{job_run_id}.csv` when report generation is relevant;
- API response bodies and persisted DTO-visible state;
- isolated OpenSearch/Milvus records for vector database behavior;
- destination files or objects for storage-output behavior.

For micro-batching, verify both the combined output and parity with the non-batched baseline: row count, schema, document identifiers, failure/skip accounting, and feature values must agree unless the feature intentionally changes them.

### 7. Report the result

Report each acceptance criterion as `PASS`, `FAIL`, or `BLOCKED`, followed by the evidence that supports it. Include:

- exact commands needed to reproduce the run;
- temporary flow and input paths;
- job identifiers and inspected artifact paths;
- relevant row counts, columns, values, and service queries;
- failures with the earliest meaningful error and likely layer;
- environmental limitations and unverified criteria;
- whether temporary artifacts or isolated external resources remain.

Do not claim the feature is validated when only configuration validation passed, when required external checks were skipped, or when the verifier did not exercise the requested behavior.

## Optional relationship to automated tests

Existing tests may help discover realistic inputs or expected behavior, but this workflow must remain runnable when no tests exist. After a successful feature run, recommend durable regression tests only as a separate follow-up. Do not make their creation or execution part of the feature-validation result unless the user asks.
