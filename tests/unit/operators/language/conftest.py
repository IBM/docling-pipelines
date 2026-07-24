"""
Pytest configuration for language detection tests.

Provides fixtures to ensure clean state between tests, particularly
for the FastTextModelManager singleton.
"""

import pytest

from docpipe.utils.infrastructure.fasttext_model_manager import FastTextModelManager


@pytest.fixture(autouse=True)
def reset_fasttext_singleton():
    """
    Reset FastTextModelManager singleton state between tests.

    This fixture runs automatically before each test to ensure:
    1. Reference count is reset to 0
    2. Model is unloaded
    3. Error state is cleared

    This prevents test pollution where one test's unreleased model
    references affect subsequent tests.
    """
    # Get the singleton instance
    manager = FastTextModelManager()

    # Force reset the state before test
    if manager._model_lock.acquire(timeout=5.0):
        try:
            manager._ref_count = 0
            manager._model = None
            manager._load_failed = False
            manager._load_error = None
        finally:
            manager._model_lock.release()

    # Run the test
    yield

    # Clean up after test (force release any remaining references)
    if manager._model_lock.acquire(timeout=5.0):
        try:
            if manager._ref_count > 0:
                # Log warning about unreleased references
                print(f"\nWarning: Test left {manager._ref_count} unreleased model references")
            manager._ref_count = 0
            manager._model = None
            manager._load_failed = False
            manager._load_error = None
        finally:
            manager._model_lock.release()
