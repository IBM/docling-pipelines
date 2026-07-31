"""Pytest fixtures for document library tests."""

from typing import Any
from unittest.mock import Mock

import pytest

from docpipe.core.assets.common.domain.ports.asset_repository import AssetRepository
from docpipe.core.assets.document_libraries.application.services.document_library_service import (
    DocumentLibraryService,
)
from docpipe.core.assets.document_libraries.domain.models.document_library import DocumentLibrary


@pytest.fixture
def sample_library_data() -> dict[str, Any]:
    """Sample document library data dictionary for testing."""
    return {
        "name": "Test Library",
        "description": "A test library for unit testing",
        "total_document_sets": 5,
        "total_documents": 150,
        "total_size_bytes": 1024000,
    }


@pytest.fixture
def sample_library_domain(sample_library_data) -> DocumentLibrary:
    """Sample DocumentLibrary domain object for testing."""
    return DocumentLibrary.create(
        name=sample_library_data["name"],
        description=sample_library_data["description"],
    )


@pytest.fixture
def sample_library_with_id(sample_library_data) -> DocumentLibrary:
    """Sample DocumentLibrary domain object with a specific library_id for testing."""
    return DocumentLibrary(
        library_id="test-library-id-123",
        name=sample_library_data["name"],
        description=sample_library_data["description"],
        document_set_ids=["set-1", "set-2"],
    )


@pytest.fixture
def sample_library_with_sets() -> DocumentLibrary:
    """Sample DocumentLibrary with document sets for testing."""
    library = DocumentLibrary.create(
        name="Library with Sets",
        description="Test library with document sets",
    )
    library.add_document_set(document_set_id="set-1")
    library.add_document_set(document_set_id="set-2")
    library.add_document_set(document_set_id="set-3")
    return library


@pytest.fixture
def mock_document_library_repository() -> Mock:
    """Mock AssetRepository[DocumentLibrary] for testing."""
    mock_repo = Mock(spec=AssetRepository)

    # Configure default return values
    mock_repo.save.return_value = None  # Will be set by individual tests
    mock_repo.find_by_id.return_value = None
    mock_repo.find_by_name.return_value = None
    mock_repo.list_all.return_value = []
    mock_repo.update.return_value = None
    mock_repo.delete.return_value = True
    mock_repo.exists.return_value = False
    mock_repo.exists_by_name.return_value = False
    mock_repo.count.return_value = 0
    mock_repo.add_document_set_to_library.return_value = None
    mock_repo.remove_document_set_from_library.return_value = None
    mock_repo.get_document_sets_for_library.return_value = []

    return mock_repo


@pytest.fixture
def mock_document_library_service(mock_document_library_repository) -> DocumentLibraryService:
    """Mock DocumentLibraryService with mocked repository for testing."""
    return DocumentLibraryService(repository=mock_document_library_repository)


@pytest.fixture
def multiple_sample_libraries() -> list[DocumentLibrary]:
    """Multiple sample libraries for testing list operations."""
    libraries = []
    for i in range(5):
        library = DocumentLibrary(
            library_id=f"library-id-{i}",
            name=f"Test Library {i}",
            description=f"Description for library {i}",
            document_set_ids=[f"set-{i}-1", f"set-{i}-2"],
        )
        libraries.append(library)
    return libraries


@pytest.fixture
def invalid_library_data() -> dict[str, Any]:
    """Invalid library data for testing validation errors."""
    return {
        "name": "",  # Empty name - invalid
        "description": "x" * 1001,  # Too long - invalid
        "total_document_sets": -1,  # Negative - invalid
        "total_documents": -1,  # Negative - invalid
        "total_size_bytes": -1,  # Negative - invalid
    }
