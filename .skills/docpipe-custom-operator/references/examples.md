# Custom Operator Examples

Use this map to select one implementation and one loading example. The current skill contract and repository rules take precedence over legacy signatures or logging found in older examples.

## Minimal local operator

Use for an operator that adds one deterministic column and has no external dependency.

- Implementation: `examples/custom_operators/hello_operator.py`
- Flow: `sample_flows/custom_operators/hello_operator.json`
- Loader fixture: `tests/fixtures/custom_operators/valid_operator.py`
- Invalid discovery fixtures: `tests/fixtures/custom_operators/invalid_operator_no_short_name.py` and `invalid_operator_no_transform.py`

The hello example demonstrates `AbstractOperator`, `OWNER_CUSTOM`, Arrow column creation, metadata, and required features. Its optional legacy `file_name` argument is not required for new operators; follow the keyword-only and transform-signature rules in `SKILL.md`.

## Configurable local operator

Use for multiple input parameters, selected columns, or a configurable output column.

- Implementation: `examples/custom_operators/example_custom_operator.py`
- Flow: `sample_flows/custom_operators/custom_operators_demo.json`
- Usage guide: `examples/custom_operators/README.md`

Compare `__init__` defaults with `get_metadata()` defaults. Prefer `OperatorConstants` and `AttributeDataTypes` where current built-in operators use them.

## Installed package and entry points

Use when operators will be installed and shared between applications.

- Package root: `examples/custom_operators/package_example/`
- Package metadata: `examples/custom_operators/package_example/pyproject.toml`
- Entry-point declaration: `[project.entry-points."docpipe.operators"]` in that file
- Operators: `my_custom_operators/operators/uppercase_operator.py` and `reverse_operator.py`
- Package instructions: `examples/custom_operators/package_example/README.md`
- Loader implementation: `src/docpipe/core/orchestration/operator_loader/adapters/package_adapter.py`
- Loader tests: `tests/unit/core/orchestrator/operator_loader/test_package_adapter.py`

Verify the installed distribution rather than relying on a repository-relative import. Test entry-point discovery and module inspection because the package adapter supports both.

## Filesystem discovery

Use for a Python file or directory referenced by `DOCPIPE_CUSTOM_OPERATORS`.

- Adapter: `src/docpipe/core/orchestration/operator_loader/adapters/filesystem_adapter.py`
- Tests: `tests/unit/core/orchestration/operator_loader/adapters/test_filesystem_adapter.py`
- Loader orchestration: `src/docpipe/core/orchestration/operator_loader/loader_service.py`
- Loader tests: `tests/unit/core/orchestration/operator_loader/test_loader_service.py`

Use one custom operator class per module when possible. The validator warns and selects the first class when a module contains multiple operator subclasses.

## S3-loaded operator

Use only for an established remote-code workflow.

- Adapter: `src/docpipe/core/orchestration/operator_loader/adapters/s3_adapter.py`
- Tests: `tests/unit/core/orchestration/operator_loader/adapters/test_s3_adapter.py`
- Alternate test location: `tests/unit/core/orchestrator/operator_loader/test_s3_adapter.py`
- Configuration guidance: the S3 section of `docs/guides/CUSTOM_OPERATORS_GUIDE.md`

Remote Python is executable code. Validate the trusted bucket/key boundary and avoid using this example for ordinary document ingestion; ingest sources use `DocumentSourcePort` instead.

## Validation and priority behavior

- Structural validator: `src/docpipe/core/orchestration/operator_loader/validator.py`
- Validator tests: `tests/unit/core/orchestrator/operator_loader/test_validator.py`
- Priority resolution: `src/docpipe/core/orchestration/operator_factory.py`
- Factory tests: `tests/unit/core/orchestrator/test_operator_factory.py`
- Host provider hooks: `docs/guides/EXTERNAL_OPERATOR_INTEGRATION.md`

Use these references for duplicate `short_name`, incorrect owner, missing transform, custom-over-built-in behavior, and application-specific priority tiers.
