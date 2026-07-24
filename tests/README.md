# Docling Pipelines Tests

This directory contains all tests for the Docling Pipelines operators and pipelines.

## Test Structure

```
tests/
├── fixtures/           # Test data files (PDFs, documents, etc.)
├── unit/              # Unit tests for individual operators
│   ├── operators/
│   │   ├── ingest/    # Ingest operator tests
│   │   ├── extract/   # Extract operator tests
│   │   └── chunker/   # Chunker operator tests
├── integration/       # Integration tests for operator pipelines
└── README.md         # This file
```

## Running Tests

### Prerequisites

1. **Sync dependencies** (first time or after changes):
   ```bash
   # From project root
   uv sync --extra dev
   ```

2. **Set up Python environment**:
   ```bash
   # From project root
   source .venv/bin/activate
   ```

3. **Set PYTHONPATH**:
   ```bash
   # From project root
   export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
   ```

### Running All Tests

```bash
# From project root with activated venv
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=src --cov-report=html
```

### Running Specific Test Suites

#### Unit Tests

```bash
# All unit tests (from project root)
uv run pytest tests/unit/ -v

# Specific operator unit tests
uv run pytest tests/unit/operators/ingest/ -v
uv run pytest tests/unit/operators/extract/ -v
uv run pytest tests/unit/operators/chunker/ -v

# Single test file
uv run pytest tests/unit/operators/ingest/test_ingest_local.py -v

# Single test function
uv run pytest tests/unit/operators/ingest/test_ingest_local.py::TestIngestLocalOperator::test_metadata_only_mode -v
```

#### Integration Tests

```bash
# All integration tests (from project root)
uv run pytest tests/integration/ -v

# Specific integration test files
uv run pytest tests/integration/test_ingest_extract_integration.py -v
uv run pytest tests/integration/test_full_pipeline_integration.py -v

# Single integration test
uv run pytest tests/integration/test_full_pipeline_integration.py::TestFullPipelineIntegration::test_ingest_extract_chunk_pipeline -v
```

### Running Tests with Output

To see print statements and detailed output:

```bash
# From project root
uv run pytest tests/ -v -s
```

### Running Tests in Parallel

For faster execution (requires pytest-xdist):

```bash
# From project root
uv run pytest tests/ -v -n auto
```

## Test Categories

### Unit Tests

Unit tests focus on individual operators in isolation:

- **Ingest Tests** ([`tests/unit/operators/ingest/`](unit/operators/ingest/)): Test file discovery and metadata collection
- **Extract Tests** ([`tests/unit/operators/extract/`](unit/operators/extract/)): Test content extraction from documents
- **Chunker Tests** ([`tests/unit/operators/chunker/`](unit/operators/chunker/)): Test text chunking functionality

### Integration Tests

Integration tests verify operator pipelines work together:

- **Ingest + Extract** ([`test_ingest_extract_integration.py`](integration/test_ingest_extract_integration.py)): Tests the two-operator pipeline
- **Full Pipeline** (`test_full_pipeline_integration.py`): Tests ingest → extract → chunking

## Test Fixtures

Test fixtures are located in [`tests/fixtures/`](fixtures/):

- `invoices/`: Sample PDF invoice documents for testing

To add new fixtures:
1. Place files in the appropriate subdirectory under `fixtures/`
2. Update tests to reference the new fixtures
3. Keep fixture files small (< 1MB) for fast test execution

## Writing New Tests

### Unit Test Template

```python
import pytest
from docpipe.core.operators.your_operator import YourOperator

class TestYourOperator:
    @pytest.fixture
    def operator_config(self):
        return {
            "param1": "value1",
            "param2": "value2"
        }
    
    def test_basic_functionality(self, operator_config):
        operator = YourOperator(operator_config)
        result, metadata = operator.transform(input_data)
        
        assert result is not None
        assert metadata["status"] == "completed"
```

### Integration Test Template

```python
import pytest
from docpipe.core.operators.operator1 import Operator1
from docpipe.core.operators.operator2 import Operator2

class TestOperatorPipeline:
    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent.parent / "fixtures" / "test_data"
    
    def test_pipeline(self, fixtures_dir):
        # Step 1
        op1 = Operator1(config1)
        result1, _ = op1.transform(None)
        
        # Step 2
        op2 = Operator2(config2)
        result2, _ = op2.transform(result1[0])
        
        # Assertions
        assert result2[0].num_rows > 0
```

## Continuous Integration

Tests are automatically run in CI/CD pipelines. See the Makefile for CI test commands:

```bash
# Run tests as in CI
make test
```

## Troubleshooting

### Import Errors

If you see import errors:
1. Verify PYTHONPATH is set correctly
2. Ensure you're in the correct directory
3. Check that the virtual environment is activated

### Fixture Not Found

If tests skip due to missing fixtures:
1. Verify the `tests/fixtures/` directory exists
2. Check that fixture files are present
3. Ensure file paths in tests match actual fixture locations

### Test Failures

For test failures:
1. Run with `-v -s` flags to see detailed output
2. Check the test logs for specific error messages
3. Verify environment variables are set correctly
4. Ensure all dependencies are installed

## Best Practices

1. **Keep tests fast**: Use small fixtures and mock external dependencies
2. **Test one thing**: Each test should verify a single behavior
3. **Use descriptive names**: Test names should clearly indicate what they test
4. **Clean up**: Tests should not leave artifacts or modify global state
5. **Use fixtures**: Leverage pytest fixtures for reusable test data
6. **Document complex tests**: Add comments explaining non-obvious test logic

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [Docling Pipelines Architecture](../ARCHITECTURE.md)
- [Operator Documentation](../src/docpipe/core/operators/)