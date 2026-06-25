"""Unit tests for DocumentLibrary domain model validation."""

import pytest

from docpipe.core.assets.document_libraries.domain.models.document_library import DocumentLibrary
from docpipe.exceptions.docpipe_exceptions import DocpipeException


class TestDocumentLibraryCreation:
    """Tests for DocumentLibrary creation and initialization."""

    def test_create_library_with_valid_data(self, sample_library_data):
        """Test creating a library with valid data."""
        # Arrange & Act
        library = DocumentLibrary.create(
            name=sample_library_data["name"],
            description=sample_library_data["description"],
        )

        # Assert
        assert library.name == sample_library_data["name"]
        assert library.description == sample_library_data["description"]
        assert library.library_id is not None
        assert len(library.library_id) > 0
        assert library.document_set_ids == []

    def test_create_library_generates_unique_ids(self, sample_library_data):
        """Test that create generates unique library IDs."""
        # Arrange & Act
        library1 = DocumentLibrary.create(
            name=sample_library_data["name"],
            description=sample_library_data["description"],
        )
        library2 = DocumentLibrary.create(
            name=sample_library_data["name"],
            description=sample_library_data["description"],
        )

        # Assert
        assert library1.library_id != library2.library_id

    def test_create_library_with_minimal_data(self):
        """Test creating a library with only required fields."""
        # Arrange & Act
        library = DocumentLibrary.create(name="Minimal Library")

        # Assert
        assert library.name == "Minimal Library"
        assert library.description is None
        assert library.library_id is not None


class TestDocumentLibraryNameValidation:
    """Tests for library name validation."""

    def test_create_library_with_empty_name_raises_error(self):
        """Test that creating a library with empty name raises validation error."""
        # Arrange & Act & Assert
        with pytest.raises(DocpipeException) as exc_info:
            DocumentLibrary.create(name="")

        assert "Field 'name'" in str(exc_info.value)

    def test_create_library_with_name_too_long_raises_error(self):
        """Test that creating a library with name exceeding max length raises validation error."""
        # Arrange
        long_name = "A" + "x" * 128  # Exceeds max length (128)

        # Act & Assert
        with pytest.raises(DocpipeException) as exc_info:
            DocumentLibrary.create(name=long_name)

        assert "128 characters" in str(exc_info.value)

    def test_create_library_with_max_length_name_succeeds(self):
        """Test that creating a library with name at max length succeeds."""
        # Arrange
        max_length_name = "A" + "x" * 127  # Exactly 128 characters, starts with letter

        # Act
        library = DocumentLibrary.create(name=max_length_name)

        # Assert
        assert library.name == max_length_name


class TestDocumentLibraryDescriptionValidation:
    """Tests for library description validation."""

    def test_create_library_with_none_description_succeeds(self):
        """Test that creating a library with None description succeeds."""
        # Arrange & Act
        library = DocumentLibrary.create(name="Test Library", description=None)

        # Assert
        assert library.description is None

    def test_create_library_with_empty_description_succeeds(self):
        """Test that creating a library with empty description succeeds."""
        # Arrange & Act
        library = DocumentLibrary.create(name="Test Library", description="")

        # Assert
        assert library.description == ""

    def test_create_library_with_description_too_long_raises_error(self):
        """Test that creating a library with description exceeding max length raises validation error."""
        # Arrange
        long_description = "x" * 2001  # Exceeds max length (2000)

        # Act & Assert
        with pytest.raises(DocpipeException) as exc_info:
            DocumentLibrary.create(name="Test Library", description=long_description)

        assert "2000 characters" in str(exc_info.value)

    def test_create_library_with_max_length_description_succeeds(self):
        """Test that creating a library with description at max length succeeds."""
        # Arrange
        max_length_description = "x" * 2000

        # Act
        library = DocumentLibrary.create(name="Test Library", description=max_length_description)

        # Assert
        assert library.description == max_length_description


class TestDocumentLibraryDocumentSetManagement:
    """Tests for managing document sets in a library."""

    def test_add_document_set_to_library(self, sample_library_domain):
        """Test adding a document set to a library."""
        # Arrange
        library = sample_library_domain
        document_set_id = "test-set-id-1"

        # Act
        library.add_document_set(document_set_id=document_set_id)

        # Assert
        assert document_set_id in library.document_set_ids
        assert len(library.document_set_ids) == 1

    def test_add_multiple_document_sets_to_library(self, sample_library_domain):
        """Test adding multiple document sets to a library."""
        # Arrange
        library = sample_library_domain
        set_ids = ["set-1", "set-2", "set-3"]

        # Act
        for set_id in set_ids:
            library.add_document_set(document_set_id=set_id)

        # Assert
        assert len(library.document_set_ids) == 3
        for set_id in set_ids:
            assert set_id in library.document_set_ids

    def test_add_duplicate_document_set_raises_error(self, sample_library_domain):
        """Test that adding a duplicate document set raises validation error."""
        # Arrange
        library = sample_library_domain
        document_set_id = "test-set-id-1"
        library.add_document_set(document_set_id=document_set_id)

        # Act & Assert
        with pytest.raises(DocpipeException) as exc_info:
            library.add_document_set(document_set_id=document_set_id)

        assert "already exists" in str(exc_info.value)

    def test_remove_document_set_from_library(self, sample_library_with_sets):
        """Test removing a document set from a library."""
        # Arrange
        library = sample_library_with_sets
        document_set_id = "set-1"
        initial_count = len(library.document_set_ids)

        # Act
        library.remove_document_set(document_set_id=document_set_id)

        # Assert
        assert document_set_id not in library.document_set_ids
        assert len(library.document_set_ids) == initial_count - 1

    def test_remove_nonexistent_document_set_raises_error(self, sample_library_domain):
        """Test that removing a nonexistent document set raises error."""
        # Arrange
        library = sample_library_domain
        document_set_id = "nonexistent-set-id"

        # Act & Assert
        with pytest.raises(DocpipeException) as exc_info:
            library.remove_document_set(document_set_id=document_set_id)

        assert document_set_id in str(exc_info.value)

    def test_has_document_set_returns_true_when_exists(self, sample_library_with_sets):
        """Test has_document_set returns True when set exists."""
        # Arrange
        library = sample_library_with_sets

        # Act & Assert
        assert library.has_document_set(document_set_id="set-1") is True

    def test_has_document_set_returns_false_when_not_exists(self, sample_library_domain):
        """Test has_document_set returns False when set doesn't exist."""
        # Arrange
        library = sample_library_domain

        # Act & Assert
        assert library.has_document_set(document_set_id="nonexistent") is False

    def test_get_document_set_count(self, sample_library_with_sets):
        """Test get_document_set_count returns correct count."""
        # Arrange
        library = sample_library_with_sets

        # Act
        count = library.get_document_set_count()

        # Assert
        assert count == 3
