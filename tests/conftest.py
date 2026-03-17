"""
Pytest configuration and fixtures for datasift-opensource tests.
"""

import pytest
import shutil
import sys
import tempfile
from pathlib import Path


# Centralized path setup - automatically adds backend to Python path
@pytest.fixture(scope="session", autouse=True)
def setup_python_path():
    """
    Automatically setup Python path for all tests.
    This runs once per test session and ensures imports work correctly.
    """
    backend_dir = (
        Path(__file__).parent.parent / "src" / "datasift_opensource" / "backend"
    )
    if backend_dir.exists() and str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    yield
    # Cleanup: Remove from path after tests complete
    if str(backend_dir) in sys.path:
        sys.path.remove(str(backend_dir))


# ============================================================================
# Directory Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def src_dir(project_root):
    """Return the src directory."""
    return project_root / "src"


@pytest.fixture(scope="session")
def backend_dir(src_dir):
    """Return the backend directory."""
    return src_dir / "datasift_opensource" / "backend"


@pytest.fixture(scope="session")
def tests_dir():
    """Return the tests directory."""
    return Path(__file__).parent


@pytest.fixture(scope="session")
def test_data_dir(tests_dir):
    """Return the path to test fixtures directory."""
    return tests_dir / "fixtures"


@pytest.fixture(scope="session")
def temp_test_dir():
    """Create a temporary directory with test files from fixtures"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        test_dir = Path(tmpdir)

        # Create a text file
        txt_file = test_dir / "test.txt"
        txt_file.write_text("This is a test text file.")

        # Copy a sample PDF from fixtures instead of creating hardcoded content
        fixtures_dir = Path(__file__).parent.parent.parent / "fixtures" / "invoices"
        if fixtures_dir.exists():
            sample_pdfs = list(fixtures_dir.glob("*.pdf"))
            if sample_pdfs:
                # Copy the first PDF to temp directory
                shutil.copy(sample_pdfs[0], test_dir / "test.pdf")

        yield str(test_dir)


@pytest.fixture(scope="session")
def fixtures_invoices_dir(test_data_dir):
    """Return path to invoice fixtures."""
    return test_data_dir / "invoices"


@pytest.fixture(scope="session")
def fixtures_customer_support_dir(test_data_dir):
    """Return path to customer support fixtures."""
    return test_data_dir / "customer_support_docs"


@pytest.fixture(scope="session")
def sample_pdf_files(fixtures_invoices_dir):
    """
    Return a list of sample PDF files from the invoices fixtures directory.
    Skips the test if no PDF files are found.
    """
    pdf_files = list(fixtures_invoices_dir.glob("*.pdf"))
    if not pdf_files:
        pytest.skip(f"No PDF files found in {fixtures_invoices_dir}")
    return pdf_files


@pytest.fixture(scope="session")
def temp_dir(tmp_path_factory):
    """Create a temporary directory for test outputs."""
    return tmp_path_factory.mktemp("test_outputs")


# ============================================================================
# PyArrow Table Fixtures
# ============================================================================


@pytest.fixture
def sample_pyarrow_table():
    """
    Create a sample PyArrow table for testing.
    Useful for testing operators that expect PyArrow tables as input.
    """
    import pyarrow as pa

    data = {
        "id": ["doc1", "doc2", "doc3"],
        "name": ["file1.txt", "file2.txt", "file3.txt"],
        "content": ["Sample content 1", "Sample content 2", "Sample content 3"],
        "path": ["/path/to/file1.txt", "/path/to/file2.txt", "/path/to/file3.txt"],
    }

    return pa.table(data)


@pytest.fixture
def empty_pyarrow_table():
    """Create an empty PyArrow table for testing edge cases."""
    import pyarrow as pa

    schema = pa.schema(
        [
            ("id", pa.string()),
            ("name", pa.string()),
            ("content", pa.string()),
            ("path", pa.string()),
        ]
    )

    return pa.table({}, schema=schema)


# ============================================================================
# Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_ollama_client(mocker):
    """
    Mock Ollama client with standard responses.
    Useful for testing embeddings and LLM operations without actual API calls.
    """
    mock_client = mocker.Mock()
    mock_client.embeddings.return_value = {
        "embedding": [0.1] * 384  # Standard embedding dimension
    }
    return mock_client


# ============================================================================
# Configuration Fixtures
# ============================================================================


@pytest.fixture
def basic_operator_config():
    """
    Return a basic operator configuration for testing.
    Can be extended by individual tests.
    """
    return {"max_files": 10, "force_ingest": True, "store_binary_content": True}


# ============================================================================
# Pytest Hooks for Enhanced Output
# ============================================================================


def pytest_configure(config):
    """
    Configure pytest with custom markers and settings.
    This runs before test collection.
    """
    # Register custom markers
    config.addinivalue_line("markers", "fast: marks tests as fast (< 1 second)")
    config.addinivalue_line("markers", "performance: marks tests as performance tests")


def pytest_collection_modifyitems(config, items):
    """
    Modify test items after collection.
    Automatically adds markers based on test location.
    """
    for item in items:
        # Auto-mark unit tests
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)

        # Auto-mark integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Auto-mark slow tests based on name
        if "slow" in item.nodeid.lower() or "performance" in item.nodeid.lower():
            item.add_marker(pytest.mark.slow)
