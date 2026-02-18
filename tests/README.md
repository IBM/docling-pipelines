# Tests

This directory contains all test suites for the datasift-open project.

## Structure

### unit/
Unit tests for individual components:
- Operator tests
- Orchestrator tests
- Utility function tests
- Configuration tests

### integration/
Integration tests for component interactions:
- End-to-end flow execution
- Operator chaining
- Data access integration
- Plugin system integration

### fixtures/
Test fixtures and sample data:
- Sample flow configurations
- Test data files
- Mock objects
- Test utilities

## Running Tests

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit

# Run integration tests only
pytest tests/integration

# Run with coverage
pytest --cov=src/datasift_opensource
```

## Test Guidelines
- Write unit tests for all new operators
- Include integration tests for flow execution
- Use fixtures for reusable test data
- Mock external dependencies
- Maintain high code coverage (>80%)