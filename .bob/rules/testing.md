# Testing Strategy — docpipe

Tests verify **observable behavior**, not implementation details.

- **Fast** — unit tests run in milliseconds; slow tests quarantined under `integration/`
- **Isolated** — each test owns its state; shared state is explicit via fixtures, never implicit
- **Deterministic** — a test that flips without a code change is a broken test
- **Behavior-first** — test what the system does, not how it does it

---

## Test architecture

```
tests/
├── conftest.py                   # Shared fixtures
├── fixtures/                     # Static test data: PDFs, parquet, text files
├── unit/                         # Auto-marked @pytest.mark.unit
│   ├── api/                      # FastAPI route + middleware tests
│   ├── auth/                     # JWT, token, auth logic
│   ├── cli/                      # CLI argument parsing
│   ├── core/                     # Orchestration, assets, job management
│   ├── operators/                # One subdirectory per operator
│   └── storage/                  # Storage layer
└── integration/                  # Auto-marked @pytest.mark.integration
    ├── api/                      # API integration (dependency-overridden)
    ├── app/routes/               # Flow route integration
    ├── auth/                     # OAuth2 flow
    ├── opensearch/               # Live OpenSearch
    └── operators/                # Operator pipeline integration
```

Markers auto-applied by `pytest_collection_modifyitems` in `tests/conftest.py`:
- `tests/unit/**` → `@pytest.mark.unit`
- `tests/integration/**` → `@pytest.mark.integration`
- node id containing `"slow"` or `"performance"` → `@pytest.mark.slow`

`e2e/` does not exist. Do not create it.

| Layer | Allowed | Forbidden |
|---|---|---|
| `unit/` | `pa.Table`, `Mock/MagicMock/AsyncMock`, fixtures from `conftest.py` | Real DB, HTTP, network, cloud, Ollama, OpenSearch |
| `integration/` | `TestClient(app)`, `app.dependency_overrides`, DuckDB temp | Live Ollama/OpenSearch (skip gracefully if absent) |

---

## Pytest config (`pytest.ini`)

```ini
addopts = -v --tb=short --strict-markers --color=yes --durations=10 -ra
markers = unit, integration, slow, fast, performance
```

`asyncio_mode` not set — apply `@pytest.mark.asyncio` or `@pytest.mark.anyio` explicitly.

---

## Core standards

Pure pytest only. `unittest.TestCase` exists in legacy files — **prohibited in new tests**.

```python
# correct
def test_chunker_skips_empty_documents(sample_pyarrow_table: pa.Table) -> None:
    op = ChunkerOperator(config={"doc_column": "content"})
    tables, metadata = op.transform(sample_pyarrow_table)
    assert len(tables) == 1
    assert metadata["processed_docs"] >= 0

# prohibited
class TestChunker(unittest.TestCase):
    def test_chunker(self):
        self.assertEqual(...)
```

Use `pytest.raises` for exceptions:
```python
with pytest.raises(FlowValidationException, match="depends_on references unknown node"):
    validator.validate(flow_definition)
```

---

## Async testing

| Use case | Marker |
|---|---|
| Adapter/provider/service tests | `@pytest.mark.asyncio` |
| Middleware dispatch tests | `@pytest.mark.anyio` |

Apply per-test or with module-level `pytestmark = pytest.mark.asyncio`.

Helper for async generators (define locally where needed):
```python
async def collect_async(async_gen):
    return [item async for item in async_gen]
```

---

## API tests

Use `fastapi.testclient.TestClient` (sync). Always clean up `dependency_overrides`:

```python
@pytest.fixture
def authenticated_client(mock_user: User, mock_opensearch_service: MagicMock) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_opensearch_service] = lambda: mock_opensearch_service
    yield TestClient(app)
    app.dependency_overrides.clear()   # REQUIRED — never omit
```

Common overrides: `get_current_user`, `get_opensearch_service`, `get_flow_repository`, database session.

Use `module` scope for `TestClient` when app config is constant; `function` scope when overrides differ per test.

---

## Parametrize

Use `@pytest.mark.parametrize` — never `for` loops over inputs in a single test:

```python
@pytest.mark.parametrize(("input_text", "expected_chunks"), [("short", 1), ("word " * 1000, 5), ("", 0)])
def test_chunker_chunk_count(input_text: str, expected_chunks: int) -> None: ...
```

---

## Fixtures

### Shared fixtures (`tests/conftest.py`)

| Fixture | Scope | Provides |
|---|---|---|
| `sample_pyarrow_table` | function | `pa.Table` with columns `id`, `name`, `content`, `path` |
| `empty_pyarrow_table` | function | empty `pa.Table` with same schema |
| `mock_ollama_client` | function | `Mock` returning `{"embedding": [0.1, ...]}` |
| `basic_operator_config` | function | `{"max_files": 10, "force_ingest": True}` |
| `temp_duckdb_path` | function | `str` path to a temp DuckDB file |
| `temp_dir` | function | `Path` temp directory |
| `temp_test_dir` | session | `TemporaryDirectory` with sample content |
| `project_root`, `src_dir`, `tests_dir`, `test_data_dir` | session | `Path` objects to key directories |
| `fixtures_invoices_dir`, `fixtures_customer_support_dir` | session | `Path` to fixture subdirectories |
| `sample_pdf_files`, `sample_text_files` | function | file lists from fixtures |
| `cleanup_test_document_sets` | function | yields; deletes document sets with `"Test"` in name |
| `clear_singleton_caches` | function, **autouse** | clears `LRUCache` after every test — **do not replicate in teardown** |

### Subdirectory conftest files

| File | Provides |
|---|---|
| `tests/unit/api/routes/conftest.py` | Flow DTOs, `Flow` domain objects |
| `tests/unit/core/assets_management/conftest.py` | `FlowService`, `mock_flow_repository` |
| `tests/unit/core/assets/document_libraries/conftest.py` | `DocumentLibraryService`, mock repository |
| `tests/unit/operators/acl/conftest.py` | ACL tables, `mock_acl_adapter` with `AsyncMock` methods |
| `tests/unit/operators/language/conftest.py` | `reset_fasttext_singleton` (autouse) |
| `tests/integration/app/routes/conftest.py` | `TestClient` with overrides, `create_test_flow` factory |

### Conventions

- Default to `function` scope. `module` for stable expensive setup. `session` for immutable resources only.
- Use `yield` fixtures for cleanup — runs after test even on failure.
- Prefer factory fixtures over large static fixtures when shape varies across tests.

---

## Mocking rules

### Allowed

| Technique | When |
|---|---|
| `Mock()` / `MagicMock()` | Sync services, repositories, adapters |
| `AsyncMock()` | Async adapter methods |
| `app.dependency_overrides` | FastAPI boundaries |
| `mocker.patch.object(obj, "method")` | Patching a specific object's attribute |
| `sys.modules` pre-mocking | Unavoidable import-time side effects only (see below) |

### Prohibited

| Technique | Why |
|---|---|
| `patch("app.services.foo.bar")` string-path | Breaks on rename, silently no-ops if path is wrong |
| `for` loops over inputs in one test | Masks which case failed |
| `unittest.TestCase` subclassing | Incompatible with pytest fixture injection |
| Mutating `DOCPIPE_OPERATORS` or `LRUCache` in teardown | Conflicts with `clear_singleton_caches` |

Prefer injecting mocks via fixtures over patching. For heavy optional imports (e.g. `langchain_experimental`, `fasttext`) pre-mock at module level **before** importing from docpipe:

```python
import sys
from unittest.mock import Mock
if "langchain_experimental" not in sys.modules:
    sys.modules["langchain_experimental"] = Mock()
    sys.modules["langchain_experimental.text_splitter"] = Mock()
from docpipe.core.operators.quality.some_operator import SomeOperator  # now safe
```

---

## Test naming

Format: `test_<subject>_<condition>_<expected_result>`

```python
def test_chunker_skips_empty_documents() -> None: ...       # good
def test_create_flow_returns_201_with_valid_payload() -> None: ...  # good
def test_chunker() -> None: ...                             # bad — vague
```

---

## Coverage

No `--cov-fail-under` enforced. Coverage is insight, not a gate. What matters:
- Every operator `transform()` has a happy-path test and a failure/skip-path test
- Every API route has an authenticated test and an unauthenticated test
- Every validator has valid-input and invalid-input tests

---

## Running tests

```bash
source .venv/bin/activate

pytest tests/unit/ -v                                        # unit only (no external services)
pytest tests/unit/operators/chunker/ -v                      # specific operator
pytest tests/unit/api/ -v                                    # API unit tests
pytest tests/integration/ -v -m "not slow"                   # integration (needs Ollama + OpenSearch for some)
pytest --cov=src/docpipe --cov-report=html                   # with coverage
pytest tests/ -m "not integration" -v                        # CI-safe (skip integration)
```

---

## Contributor checklist

- [ ] New public behaviour has at least one unit test
- [ ] Failure/edge cases covered (empty table, missing column, invalid config)
- [ ] `@pytest.mark.parametrize` used where multiple inputs drive the same logic
- [ ] Fixtures from `tests/conftest.py` reused — no duplicate `sample_pyarrow_table`
- [ ] `app.dependency_overrides` cleaned up via `yield` + `.clear()`
- [ ] No `unittest.TestCase` subclassing
- [ ] No string-path `patch("docpipe.some.module.Class")` — use `patch.object` or inject
- [ ] `clear_singleton_caches` respected — no manual `LRUCache` teardown
- [ ] Async tests use `@pytest.mark.asyncio` (adapters) or `@pytest.mark.anyio` (middleware)
- [ ] Test names describe observable behaviour
- [ ] `pytest tests/unit/ -v` passes locally before pushing
