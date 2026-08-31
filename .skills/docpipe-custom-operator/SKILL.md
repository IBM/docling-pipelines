---
name: docpipe-custom-operator
description: >-
  Create, load, package, or modify an external custom operator for docpipe. Use when a consumer
  needs an AbstractOperator supplied through DOCPIPE_CUSTOM_OPERATORS, DocpipeFlowManager,
  package entry points, S3, or register_operator_provider without modifying the built-in
  DOCPIPE_OPERATORS registry. Do not use for built-in operators or ingest source connectors.
---

# Docpipe Custom Operator

Deliver a consumer-owned operator that satisfies docpipe’s PyArrow and metadata contracts, is discoverable through the selected custom loading mechanism, and runs in a valid flow without modifying the built-in registry.

## Scope and placement

A custom operator is external to `src/docpipe` and must set:

```python
owner: str | None = DocpipeConstants.OWNER_CUSTOM
```

Custom discovery rejects an operator that claims `OWNER_DOCPIPE`. Do not import the class into `src/docpipe/core/operators/operator_registry.py` and do not add it to `DOCPIPE_OPERATORS`.

Choose a consumer-owned location. When adding a maintained example to this repository, use `examples/custom_operators/`; otherwise use the user’s external project or requested path.

Read these sources before implementing:

- `src/docpipe/core/operators/abstract_operator.py` for the runtime contract;
- `src/docpipe/core/orchestration/operator_loader/validator.py` for discovery validation;
- `examples/custom_operators/hello_operator.py` for a small current example;
- `docs/guides/CUSTOM_OPERATORS_GUIDE.md` for filesystem, package, and S3 loading;
- `docs/guides/EXTERNAL_OPERATOR_INTEGRATION.md` only for host provider hooks and owner-priority behavior.

Read [references/examples.md](references/examples.md) and select the example matching the requested loading mode and operator shape. Do not load package or S3 examples for a simple local-file operator.

## Choose the loading mode

Use the smallest mechanism that fits distribution needs.

### Local file or directory

Use during development. `DOCPIPE_CUSTOM_OPERATORS` accepts comma-separated source paths:

```bash
export DOCPIPE_CUSTOM_OPERATORS="/absolute/path/operator.py,/absolute/path/operators"
```

The filesystem loader scans Python modules and validates discovered classes. Prefer one operator class per module so discovery is deterministic.

### Installed package

Use for reuse across applications. Put operators in an importable package, expose a stable module, and optionally publish `docpipe.operators` entry points. Verify both package installation metadata and module import; the package adapter uses both entry points and module inspection.

### Python library registration

Call before execution:

```python
manager.register_custom_operators(package_names=["my_company.operators"])
```

### Host application provider

Use `register_operator_provider()` when a host application owns a set of operator classes and wires them at startup. Return a `frozenset` and optionally filter it by orchestrator. Register owner priority only when the host intentionally needs conflict resolution beyond the reserved custom and docpipe tiers.

### S3 source

Use only for an existing remote-operator deployment workflow. Keep credentials outside source paths, use the supported S3 loader configuration, and do not download or execute untrusted operator code.

## Required class contract

Implement a class that:

- inherits `AbstractOperator`;
- defines non-empty `short_name` and a valid `OperatorCategory`;
- sets `owner = DocpipeConstants.OWNER_CUSTOM`;
- calls `super().__init__(config)` when overriding `__init__`;
- defines `transform()` directly on the class;
- accepts a `pa.Table` and returns `tuple[list[pa.Table], dict]`;
- implements `get_metadata()` as `@staticmethod` for its public parameters and output features;
- declares upstream columns with `get_required_features()`;
- uses `create_base_metadata()` and inherited failure/skip recording;
- keeps persistence, orchestration, and concrete infrastructure adapters outside transform logic.

Use keyword-only parameters whenever a function has two or more parameters excluding `self` or `cls`. Do not copy the legacy optional `file_name` argument from old examples unless a real caller requires it; make it keyword-only when required.

## Transform semantics

Define before coding:

- required columns and accepted Arrow types;
- output columns, types, and whether existing columns are replaced;
- row ordering, document identifier, and branch behavior;
- empty-table, missing-column, null-value, and row-failure behavior;
- processed, skipped, and failed metadata accounting.

For valid zero-row input, return an empty output with a stable schema unless the operator’s documented contract requires failure. Never use `if table:` on `pa.Table`.

Use docpipe ports such as `LLMInferencePort` or `LLMEmbeddingPort` for external behavior. Inject or construct dependencies at an appropriate boundary; do not make transform logic import a concrete built-in adapter.

## Metadata and validation

Keep the runtime configuration and `get_metadata()` synchronized.

- Put user inputs under `OperatorConstants.Config.ATTRIBUTES` with label, description, type, required flag, default, and bounds or valid values.
- Put produced columns under `OperatorConstants.Config.FEATURES` with stable names and types.
- Use `AttributeDataTypes` and existing constants instead of free-form strings when available.
- Implement `get_static_required_features()` when discovery needs requirements without instance configuration.
- Override `validate(errors, warnings, available_features)` for cross-field and upstream-feature validation.
- Ensure the class `short_name`, flow `type`, metadata, tests, and docs agree.

## Logging and safety

- Use `get_logger()` from docpipe infrastructure.
- Use lazy `%s` parameters in `logger.*()` calls; no f-strings.
- Do not log secrets, full document content, or non-ASCII/emoji text.
- Preserve actionable document identifiers and job context in errors.
- Treat imported custom code as executable code; do not load an untrusted path or package merely to inspect it.

## Verify discovery before flow execution

For a local source:

```bash
source .venv/bin/activate
DOCPIPE_CUSTOM_OPERATORS=/absolute/path/to/operator.py \
  docling-pipelines --list-operators --verbose
```

Confirm:

- the expected `short_name` is present;
- owner is `custom`;
- category, availability, attributes, and features are correct;
- no duplicate short name exists in the same custom load batch;
- an intended override wins according to owner priority.

An importable module that is absent from `--list-operators` is not complete.

## Automated verification

Keep tests with the consumer project. For an example maintained here, place focused tests under an appropriate `tests/unit/` custom-loader or example area without changing global registries during teardown.

Cover at least:

- happy-path output schema and exact values;
- typed zero-row input;
- invalid and conflicting config;
- missing and null required columns;
- row-level or dependency failures and metadata accounting;
- discovery validation, owner, and duplicate `short_name` behavior;
- package/provider registration when that loading mode is used.

Mock external services and use `patch.object` or injected dependencies. Reuse `tests/fixtures/custom_operators/` for loader behavior when appropriate.

## Runnable flow validation

Create a temporary flow with exactly one `ingest_source` root, the minimum upstream operators required by the custom operator, and the custom `short_name` as its `type`. Use `force_ingest: true`, keep validation enabled, and set micro-batching explicitly for deterministic behavior.

Validate and run with the same custom source configuration:

```bash
source .venv/bin/activate
DOCPIPE_CUSTOM_OPERATORS=/absolute/path/to/operator.py \
  docling-pipelines --flow-file /path/to/flow.json --validate

DOCPIPE_CUSTOM_OPERATORS=/absolute/path/to/operator.py \
  docling-pipelines --flow-file /path/to/flow.json
```

Use `.skills/feature-testing-workflow/SKILL.md` to inspect job statistics and actual Parquet values without depending on pytest. Verify feature values, input/output document parity, and failure/skip counts rather than relying only on process exit status.

## Packaging and documentation

For a distributable package:

- provide normal package metadata and a stable import path;
- declare compatible docpipe/Python versions;
- declare only required dependencies;
- add `docpipe.operators` entry points when package discovery needs them;
- document the selected loading mechanism and required environment variables;
- verify behavior in a clean environment where the package is installed rather than imported from the working tree.

For a repository example, update `examples/custom_operators/README.md`, add or update one focused example flow, and add the change under `## [Unreleased]` in `CHANGELOG.md`. Do not add an external operator to built-in operator reference pages as though it ships with docpipe.

Finish by reporting the source location, loading mode, discovery evidence, flow-validation result, runtime feature evidence, and any unverified external dependency.
