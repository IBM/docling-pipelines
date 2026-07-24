"""Unit tests for DocumentLibraryService - Simplified working version."""

from unittest.mock import Mock

import pytest

from docpipe.core.assets.document_libraries.application.services.document_library_service import (
    DocumentLibraryService,
)
from docpipe.exceptions.docpipe_exceptions import DocpipeException


@pytest.fixture
def mock_repository():
    """Create a properly configured mock repository."""
    repo = Mock()
    repo.create.return_value = None
    repo.get_by_id.return_value = None
    repo.get_by_name.return_value = None
    repo.list_all.return_value = []
    repo.update.return_value = None
    repo.delete.return_value = True
    repo.exists.return_value = False
    repo.exists_by_name.return_value = False
    repo.count_all.return_value = 0
    repo.add_document_set_to_library.return_value = None
    repo.remove_document_set_from_library.return_value = None
    repo.get_document_sets_for_library.return_value = []
    return repo


@pytest.fixture
def service(mock_repository):
    """Create service with mock repository."""
    return DocumentLibraryService(repository=mock_repository)


@pytest.fixture
def mock_document_set_service():
    """Create a properly configured mock document set service."""
    service = Mock()
    service.get_document_set.return_value = Mock(id="set-1")
    return service


@pytest.fixture
def service_with_document_set_validation(mock_repository, mock_document_set_service):
    """Create service with mock repository and document set validation."""
    return DocumentLibraryService(
        repository=mock_repository,
        document_set_service=mock_document_set_service,
    )


class TestDocumentLibraryServiceCreate:
    """Tests for creating libraries via service."""

    def test_create_library_success(self, service, mock_repository, sample_library_domain):
        """Test successful library creation."""
        # Arrange
        mock_repository.create.return_value = sample_library_domain

        # Act
        result = service.create_library(
            name=sample_library_domain.name,
            description=sample_library_domain.description,
        )

        # Assert
        assert result == sample_library_domain
        mock_repository.create.assert_called_once()

    def test_create_library_with_invalid_name_raises_error(self, service):
        """Test that creating library with invalid name raises error."""
        # Act & Assert
        with pytest.raises(DocpipeException):
            service.create_library(name="")


class TestDocumentLibraryServiceGet:
    """Tests for retrieving libraries via service."""

    def test_get_library_success(self, service, mock_repository, sample_library_with_id):
        """Test successful library retrieval."""
        # Arrange
        mock_repository.get_by_id.return_value = sample_library_with_id

        # Act
        result = service.get_library(library_id=sample_library_with_id.library_id)

        # Assert
        assert result == sample_library_with_id
        mock_repository.get_by_id.assert_called_once_with(library_id=sample_library_with_id.library_id)

    def test_get_library_not_found_raises_error(self, service, mock_repository):
        """Test that getting nonexistent library raises error."""
        # Arrange
        mock_repository.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(DocpipeException):
            service.get_library(library_id="nonexistent-id")


class TestDocumentLibraryServiceList:
    """Tests for listing libraries via service."""

    def test_list_libraries_success(self, service, mock_repository, multiple_sample_libraries):
        """Test successful listing of libraries."""
        # Arrange
        mock_repository.list_all.return_value = multiple_sample_libraries

        # Act
        result = service.list_libraries()

        # Assert
        assert result == multiple_sample_libraries
        assert len(result) == 5
        mock_repository.list_all.assert_called_once()

    def test_count_libraries(self, service, mock_repository):
        """Test counting libraries."""
        # Arrange
        mock_repository.count_all.return_value = 10

        # Act
        result = service.count_libraries()

        # Assert
        assert result == 10
        mock_repository.count_all.assert_called_once()


class TestDocumentLibraryServiceUpdate:
    """Tests for updating libraries via service."""

    def test_update_library_success(self, service, mock_repository, sample_library_with_id):
        """Test successful library update."""
        # Arrange
        mock_repository.get_by_id.return_value = sample_library_with_id
        updated_library = sample_library_with_id
        updated_library.name = "Updated Name"
        mock_repository.update.return_value = updated_library

        # Act
        result = service.update_library(
            library_id=sample_library_with_id.library_id,
            name="Updated Name",
        )

        # Assert
        assert result.name == "Updated Name"
        mock_repository.update.assert_called_once()


class TestDocumentLibraryServiceDelete:
    """Tests for deleting libraries via service."""

    def test_delete_library_success(self, service, mock_repository):
        """Test successful library deletion."""
        # Arrange
        mock_repository.delete.return_value = True

        # Act
        result = service.delete_library(library_id="test-id")

        # Assert
        assert result is True
        mock_repository.delete.assert_called_once_with(library_id="test-id")


class TestDocumentLibraryServiceDocumentSets:
    """Tests for managing document sets in libraries."""

    def test_add_document_set_success(self, service, mock_repository, sample_library_domain):
        """Test successfully adding document set to library."""
        # Arrange - use sample_library_domain which has no existing sets
        mock_repository.get_by_id.return_value = sample_library_domain
        mock_repository.update.return_value = sample_library_domain

        # Act
        service.add_document_set(
            library_id=sample_library_domain.library_id,
            document_set_id="new-set-id",
        )

        # Assert
        mock_repository.add_document_set_to_library.assert_called_once()

    def test_add_document_sets_bulk_success(self, service, mock_repository, sample_library_domain):
        """Test successfully adding multiple document sets to library (bulk operation)."""
        # Arrange - use sample_library_domain which has no existing sets
        mock_repository.get_by_id.return_value = sample_library_domain
        mock_repository.update.return_value = sample_library_domain
        document_set_ids = ["set-1", "set-2", "set-3"]

        # Act
        service.add_document_sets_bulk(
            library_id=sample_library_domain.library_id,
            document_set_ids=document_set_ids,
        )

        # Assert - should use bulk method (1 call) instead of N individual calls
        mock_repository.add_document_sets_bulk.assert_called_once_with(
            library_id=sample_library_domain.library_id,
            document_set_ids=document_set_ids,
        )

    def test_add_document_sets_bulk_validates_document_set_existence(
        self,
        service_with_document_set_validation,
        mock_repository,
        mock_document_set_service,
        sample_library_domain,
    ):
        """Test bulk add validates each document set exists before insert."""
        mock_repository.get_by_id.return_value = sample_library_domain
        mock_document_set_service.document_set_exists.return_value = True
        document_set_ids = ["set-1", "set-2", "set-3"]

        service_with_document_set_validation.add_document_sets_bulk(
            library_id=sample_library_domain.library_id,
            document_set_ids=document_set_ids,
        )

        assert mock_document_set_service.document_set_exists.call_count == 3
        mock_repository.add_document_sets_bulk.assert_called_once_with(
            library_id=sample_library_domain.library_id,
            document_set_ids=document_set_ids,
        )

    def test_add_document_sets_bulk_raises_when_document_set_missing(
        self,
        service_with_document_set_validation,
        mock_repository,
        mock_document_set_service,
        sample_library_domain,
    ):
        """Test bulk add fails before insert when a document set does not exist."""
        mock_repository.get_by_id.return_value = sample_library_domain
        mock_document_set_service.document_set_exists.side_effect = [True, False]

        with pytest.raises(DocpipeException):
            service_with_document_set_validation.add_document_sets_bulk(
                library_id=sample_library_domain.library_id,
                document_set_ids=["set-1", "missing-set"],
            )

        mock_repository.add_document_sets_bulk.assert_not_called()

    def test_remove_document_set_success(self, service, mock_repository, sample_library_with_id):
        """Test successfully removing document set from library."""
        # Arrange - sample_library_with_id has ["set-1", "set-2"]
        mock_repository.get_by_id.return_value = sample_library_with_id
        mock_repository.update.return_value = sample_library_with_id

        # Act - remove an existing set
        service.remove_document_set(
            library_id=sample_library_with_id.library_id,
            document_set_id="set-1",
        )

        # Assert
        mock_repository.remove_document_set_from_library.assert_called_once()

    def test_remove_document_sets_bulk_success(self, service, mock_repository, sample_library_with_id):
        """Test successfully removing multiple document sets from library (bulk operation)."""
        # Arrange - sample_library_with_id has ["set-1", "set-2"]
        mock_repository.get_by_id.return_value = sample_library_with_id
        mock_repository.update.return_value = sample_library_with_id
        document_set_ids = ["set-1", "set-2"]  # Remove only existing sets

        # Act
        service.remove_document_sets_bulk(
            library_id=sample_library_with_id.library_id,
            document_set_ids=document_set_ids,
        )

        # Assert - should use bulk method (1 call) instead of N individual calls
        mock_repository.remove_document_sets_bulk.assert_called_once_with(
            library_id=sample_library_with_id.library_id,
            document_set_ids=document_set_ids,
        )

    def test_get_document_sets_success(self, service, mock_repository):
        """Test getting document sets for library."""
        # Arrange
        expected_sets = ["set-1", "set-2", "set-3"]
        mock_repository.get_document_sets_for_library.return_value = expected_sets

        # Act
        result = service.get_document_sets(library_id="test-id")

        # Assert
        assert result == expected_sets
        mock_repository.get_document_sets_for_library.assert_called_once_with(library_id="test-id")
