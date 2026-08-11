# Testing Standards

This document defines coverage requirements, test organisation, naming conventions, and fixture patterns for all contributors to docling-pipelines.

---

## Coverage Requirements

| Scope | Threshold |
|---|---|
| Overall (unit tests) | 80% |
| Core operators (`transform()`) | 90%+ |
| Critical paths (flow executor, validator) | 90%+ |

Coverage is enforced in CI via `--cov-fail-under=80`. Run locally with:

```bash
pytest tests/unit/ --cov=src/docpipe --cov-report=term-missing
```

---

## Test Directory Structure

```
tests/
├── conftest.py                        # Shared fixtures — use these before creating new ones
├── fixtures/                          # Static test data: PDFs, parquet, text files
├── unit/                              # Auto-marked @pytest.mark.unit — no external services
│   ├── api/                           # FastAPI route + middleware tests
│   ├── auth/                          # JWT, token, auth logic
│   ├── cli/                           # CLI argument parsing
│   ├── core/                          # Orchestration, assets, job management
│   ├── operators/                     # One subdirectory per operator
│   │   └── <category>/<operator_name>/
│   └── storage/                       # Storage layer
└── integration/                       # Auto-marked @pytest.mark.integration
    ├── api/                           # API integration (dependency-overridden)
    ├── operators/                     # Operator pipeline integration
    └── opensearch/                    # Live OpenSearch
```

**Rules:**
- `tests/unit/` — no real DB, HTTP, network, Ollama, or OpenSearch calls. Mock everything.
- `tests/integration/` — external services allowed; skip gracefully if absent.
- `e2e/` does not exist. Do not create it.

---

## Test Naming Convention

Format: `test_<subject>_<condition>_<expected_result>`

```python
# Good
def test_chunker_skips_empty_documents() -> None: ...
def test_flow_validator_raises_when_dag_missing() -> None: ...
def test_embeddings_operator_returns_vectors_for_valid_table() -> None: ...

# Bad — too vague
def test_chunker() -> None: ...
def test_flow() -> None: ...
```

---

## Required Test Types Per Operator

Every operator must have unit tests covering:

| Test type | Description |
|---|---|
| Happy path | Valid input table, expected output shape and columns |
| Empty table | `pa.Table` with 0 rows — must not raise, must return empty table |
| Invalid config | Missing required config keys — must raise with a clear error |
| Missing column | `doc_column` absent from table — must record skip or raise |
| Error handling | Simulated downstream failure — metadata must record failure |

---

## Shared Fixtures (`tests/conftest.py`)

Always use these before creating new fixtures:

| Fixture | Scope | Provides |
|---|---|---|
| `sample_pyarrow_table` | function | `pa.Table` with `id`, `name`, `content`, `path` columns |
| `empty_pyarrow_table` | function | Empty `pa.Table` with same schema |
| `mock_ollama_client` | function | `Mock` returning `{"embedding": [0.1, ...]}` |
| `basic_operator_config` | function | `{"max_files": 10, "force_ingest": True}` |
| `temp_duckdb_path` | function | `str` path to a temp DuckDB file |
| `temp_dir` | function | `Path` temp directory |
| `clear_singleton_caches` | function, autouse | Clears `LRUCache` after every test |

---

## Mocking Rules

| Allowed | Forbidden |
|---|---|
| `Mock()` / `MagicMock()` for sync services | `patch("docpipe.some.module.Class")` string-path |
| `AsyncMock()` for async adapter methods | `for` loops over inputs in one test |
| `app.dependency_overrides` at FastAPI boundaries | `unittest.TestCase` subclassing |
| `mocker.patch.object(obj, "method")` | Mutating `DOCPIPE_OPERATORS` or `LRUCache` in teardown |

Always clean up `dependency_overrides` via `yield` + `.clear()`:

```python
@pytest.fixture
def authenticated_client(mock_user: User) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield TestClient(app)
    app.dependency_overrides.clear()  # REQUIRED
```

---

## Async Tests

| Use case | Marker |
|---|---|
| Adapter / provider / service tests | `@pytest.mark.asyncio` |
| Middleware dispatch tests | `@pytest.mark.anyio` |

---

## Parametrize

Use `@pytest.mark.parametrize` — never `for` loops over inputs in a single test:

```python
@pytest.mark.parametrize(("input_text", "expected_chunks"), [
    ("short text", 1),
    ("word " * 1000, 5),
    ("", 0),
])
def test_chunker_chunk_count(input_text: str, expected_chunks: int) -> None: ...
```

---

## Running Tests

```bash
source .venv/bin/activate

# Unit tests only (CI-equivalent)
pytest tests/unit/ -v

# Specific operator
pytest tests/unit/operators/chunker/ -v

# With coverage report
pytest tests/unit/ --cov=src/docpipe --cov-report=html

# Parallel execution locally
pytest tests/unit/ -n auto

# Integration tests (requires Ollama + OpenSearch)
pytest tests/integration/ -v -m "not slow"
```

---

## Contributor Checklist

- [ ] New public behaviour has at least one unit test
- [ ] Failure and edge cases covered (empty table, missing column, invalid config)
- [ ] `@pytest.mark.parametrize` used where multiple inputs drive the same logic
- [ ] Fixtures from `tests/conftest.py` reused — no duplicate `sample_pyarrow_table`
- [ ] `app.dependency_overrides` cleaned up via `yield` + `.clear()`
- [ ] No `unittest.TestCase` subclassing
- [ ] No string-path `patch("docpipe.some.module")` — use `patch.object` or inject
- [ ] Async tests use `@pytest.mark.asyncio` (adapters) or `@pytest.mark.anyio` (middleware)
- [ ] Test names describe observable behaviour
- [ ] `pytest tests/unit/ -v` passes locally before pushing
