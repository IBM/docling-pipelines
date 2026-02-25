"""
Pytest configuration and fixtures for datasift-opensource tests.
"""
import pytest
import sys
import os
from pathlib import Path

# Add backend directory to path for imports
backend_dir = Path(__file__).parent.parent / "src" / "datasift_opensource" / "backend"
if backend_dir.exists():
    sys.path.insert(0, str(backend_dir))

@pytest.fixture(scope="session")
def test_data_dir():
    """Return the path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"

@pytest.fixture(scope="session")
def temp_dir(tmp_path_factory):
    """Create a temporary directory for test outputs."""
    return tmp_path_factory.mktemp("test_outputs")