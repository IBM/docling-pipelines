"""Pytest configuration and fixtures for integration tests."""

import pytest


def pytest_configure(config):
    """Configure pytest with custom markers for integration tests."""
    config.addinivalue_line("markers", "requires_ollama: mark test as requiring ollama package")
    config.addinivalue_line("markers", "requires_watsonx: mark test as requiring ibm-watsonx-ai package")
    config.addinivalue_line("markers", "requires_prefect: mark test as requiring prefect package")


@pytest.fixture(scope="session")
def ollama_available():
    """Check if ollama package is available."""
    try:
        import ollama  # noqa: F401

        return True
    except ImportError:
        return False


@pytest.fixture(scope="session")
def watsonx_available():
    """Check if ibm-watsonx-ai package is available."""
    try:
        import ibm_watsonx_ai  # noqa: F401

        return True
    except ImportError:
        return False


@pytest.fixture(scope="session")
def prefect_available():
    """Check if prefect package is available."""
    try:
        import prefect  # noqa: F401

        return True
    except ImportError:
        return False


@pytest.fixture
def skip_if_ollama_unavailable(ollama_available):
    """Skip test if ollama package is not available."""
    if not ollama_available:
        pytest.skip("ollama package not installed")


@pytest.fixture
def skip_if_watsonx_unavailable(watsonx_available):
    """Skip test if ibm-watsonx-ai package is not available."""
    if not watsonx_available:
        pytest.skip("ibm-watsonx-ai package not installed")


@pytest.fixture
def skip_if_prefect_unavailable(prefect_available):
    """Skip test if prefect package is not available."""
    if not prefect_available:
        pytest.skip("prefect package not installed")
