"""Test Document Library API validation behavior.

This test suite verifies the Document Library API validation rules
which now match the Document Set validation pattern for consistency.

Current Implementation (as of 2026-06-03):
- name: 3-128 characters, must start with letter, alphanumeric + spaces/underscores only
- description: max 2000 characters (optional)
- purpose: max 1024 characters (optional)
- original_size: non-negative integer (optional)
- final_size: non-negative integer (optional)
- tags: no limit on count or individual tag length (optional)

Pattern: ^[a-zA-Z][a-zA-Z0-9_ ]*$
"""

import pytest
from pydantic import ValidationError

from docpipe.api.dto.document_library_dto import DocumentLibraryPatch, DocumentLibraryPrototype
from docpipe.core.assets.document_libraries.domain.models.document_library import DocumentLibrary
from docpipe.exceptions.docpipe_exceptions import DocpipeException


class TestDocumentLibraryDTOValidation:
    """Test Pydantic DTO validation (FastAPI request validation layer)."""

    def test_name_accepts_valid_alphanumeric(self):
        """Name with letters, digits, spaces, underscores should pass."""
        dto = DocumentLibraryPrototype(name="Test Library 123")
        assert dto.name == "Test Library 123"

    def test_name_accepts_128_characters(self):
        """Name accepts up to 128 characters."""
        long_name = "A" + "a" * 127
        dto = DocumentLibraryPrototype(name=long_name)
        assert len(dto.name) == 128

    def test_name_rejects_129_characters(self):
        """Name rejects 129+ characters."""
        too_long = "A" + "a" * 128
        with pytest.raises(ValidationError) as exc_info:
            DocumentLibraryPrototype(name=too_long)
        assert "String should have at most 128 characters" in str(exc_info.value)

    def test_name_rejects_special_characters(self):
        """Name rejects special characters like @#$%."""
        with pytest.raises(ValidationError) as exc_info:
            DocumentLibraryPrototype(name="Test@#$%123")
        error_msg = str(exc_info.value)
        assert "must start with a letter" in error_msg
        assert "can only contain letters, digits, spaces, and underscores" in error_msg
        assert "Special characters like @#$%-!& are not allowed" in error_msg

    def test_name_rejects_starting_with_digit(self):
        """Name must start with a letter, not a digit."""
        with pytest.raises(ValidationError) as exc_info:
            DocumentLibraryPrototype(name="123Test")
        error_msg = str(exc_info.value)
        assert "Name must start with a letter" in error_msg

    def test_name_rejects_starting_with_underscore(self):
        """Name must start with a letter, not underscore."""
        with pytest.raises(ValidationError) as exc_info:
            DocumentLibraryPrototype(name="_Test")
        error_msg = str(exc_info.value)
        assert "Name must start with a letter" in error_msg

    def test_name_accepts_underscores_after_first_char(self):
        """Name accepts underscores after the first character."""
        dto = DocumentLibraryPrototype(name="Test_Library_Name")
        assert dto.name == "Test_Library_Name"

    def test_description_accepts_2000_characters(self):
        """Description accepts up to 2000 characters."""
        long_desc = "A" * 2000
        dto = DocumentLibraryPrototype(name="Test", description=long_desc)
        assert len(dto.description) == 2000

    def test_description_rejects_2001_characters(self):
        """Description rejects 2001+ characters."""
        too_long = "A" * 2001
        with pytest.raises(ValidationError) as exc_info:
            DocumentLibraryPrototype(name="Test", description=too_long)
        assert "String should have at most 2000 characters" in str(exc_info.value)

    def test_tags_accepts_unlimited_count(self):
        """Tags have no count limit."""
        many_tags = [f"tag{i}" for i in range(100)]
        dto = DocumentLibraryPrototype(name="Test", tags=many_tags)
        assert len(dto.tags) == 100

    def test_tags_accepts_long_individual_tags(self):
        """Individual tags have no length limit."""
        long_tag = "a" * 200
        dto = DocumentLibraryPrototype(name="Test", tags=[long_tag])
        assert dto.tags[0] == long_tag

    def test_patch_name_is_optional(self):
        """PATCH DTO should allow omitted name."""
        dto = DocumentLibraryPatch()
        assert dto.name is None

    def test_patch_name_accepts_valid_value(self):
        """PATCH DTO should validate provided name."""
        dto = DocumentLibraryPatch(name="Updated Library")
        assert dto.name == "Updated Library"


class TestDocumentLibraryDomainValidation:
    """Test domain model validation (business logic layer)."""

    def test_domain_accepts_valid_name(self):
        """Domain model accepts valid alphanumeric name."""
        library = DocumentLibrary.create(name="Test Library")
        assert library.name == "Test Library"

    def test_domain_accepts_128_character_name(self):
        """Domain model accepts up to 128 characters."""
        long_name = "A" + "a" * 127
        library = DocumentLibrary.create(name=long_name)
        assert len(library.name) == 128

    def test_domain_rejects_129_character_name(self):
        """Domain model rejects 129+ characters."""
        too_long = "A" + "a" * 128
        with pytest.raises(DocpipeException) as exc_info:
            DocumentLibrary.create(name=too_long)
        assert "must not exceed 128 characters" in str(exc_info.value)

    def test_domain_rejects_name_starting_with_digit(self):
        """Domain model rejects names starting with digits."""
        with pytest.raises(DocpipeException) as exc_info:
            DocumentLibrary.create(name="123Test")
        assert "must start with an alphabetic character" in str(exc_info.value)

    def test_domain_rejects_name_with_special_chars(self):
        """Domain model rejects names with special characters."""
        with pytest.raises(DocpipeException) as exc_info:
            DocumentLibrary.create(name="Test@Library")
        assert "can only contain letters, digits, spaces, and underscores" in str(exc_info.value)

    def test_domain_accepts_2000_character_description(self):
        """Domain model accepts up to 2000 characters."""
        long_desc = "A" * 2000
        library = DocumentLibrary.create(name="Test", description=long_desc)
        assert len(library.description) == 2000

    def test_domain_rejects_2001_character_description(self):
        """Domain model rejects 2001+ characters."""
        too_long = "A" * 2001
        with pytest.raises(DocpipeException) as exc_info:
            DocumentLibrary.create(name="Test", description=too_long)
        assert "must not exceed 2000 characters" in str(exc_info.value)

    def test_domain_accepts_unlimited_tags(self):
        """Domain model has no tag count limit."""
        many_tags = [f"tag{i}" for i in range(100)]
        library = DocumentLibrary.create(name="Test", tags=many_tags)
        assert len(library.tags) == 100

    def test_domain_accepts_long_tags(self):
        """Domain model has no individual tag length limit."""
        long_tag = "a" * 200
        library = DocumentLibrary.create(name="Test", tags=[long_tag])
        assert library.tags[0] == long_tag


class TestNegativeValidationScenarios:
    """Test negative scenarios - what SHOULD fail validation."""

    def test_name_empty_string_fails(self):
        """Empty name should fail validation (min 3 characters)."""
        with pytest.raises(ValidationError) as exc_info:
            DocumentLibraryPrototype(name="")
        assert "String should have at least 3 characters" in str(exc_info.value)

    def test_name_only_whitespace_fails_dto(self):
        """Whitespace-only name should fail DTO validation (min 3 characters)."""
        with pytest.raises(ValidationError) as exc_info:
            DocumentLibraryPrototype(name=" ")
        assert "String should have at least 3 characters" in str(exc_info.value)

    def test_name_with_leading_whitespace_fails(self):
        """Name with leading whitespace fails (doesn't start with letter)."""
        with pytest.raises(ValidationError) as exc_info:
            DocumentLibraryPrototype(name="  Test")
        error_msg = str(exc_info.value)
        assert "Name must start with a letter" in error_msg

    def test_name_missing_fails(self):
        """Missing required name field should fail."""
        with pytest.raises(ValidationError) as exc_info:
            DocumentLibraryPrototype()
        assert "Field required" in str(exc_info.value)

    def test_original_size_negative_fails_dto(self):
        """Negative original_size should fail DTO validation."""
        with pytest.raises(ValidationError) as exc_info:
            DocumentLibraryPrototype(name="Test", original_size=-1)
        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_final_size_negative_fails_dto(self):
        """Negative final_size should fail DTO validation."""
        with pytest.raises(ValidationError) as exc_info:
            DocumentLibraryPrototype(name="Test", final_size=-1)
        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_original_size_exceeds_max_safe_integer_fails_domain(self):
        """Size exceeding MAX_SAFE_INTEGER should fail domain validation."""
        too_large = 9007199254740992  # MAX_SAFE_INTEGER + 1
        with pytest.raises(DocpipeException) as exc_info:
            DocumentLibrary.create(name="Test", original_size=too_large)
        assert "MAX_SAFE_INTEGER" in str(exc_info.value)

    def test_final_size_exceeds_max_safe_integer_fails_domain(self):
        """Size exceeding MAX_SAFE_INTEGER should fail domain validation."""
        too_large = 9007199254740992  # MAX_SAFE_INTEGER + 1
        with pytest.raises(DocpipeException) as exc_info:
            DocumentLibrary.create(name="Test", final_size=too_large)
        assert "MAX_SAFE_INTEGER" in str(exc_info.value)

    def test_tags_non_string_items_fail(self):
        """Tags containing non-string items should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            DocumentLibraryPrototype(name="Test", tags=["valid", 123, "another"])
        assert "Input should be a valid string" in str(exc_info.value)

    def test_tags_not_a_list_fails(self):
        """Tags that are not a list should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            DocumentLibraryPrototype(name="Test", tags="not-a-list")
        assert "Input should be a valid list" in str(exc_info.value)


class TestEdgeCaseValidation:
    """Test edge cases and boundary conditions."""

    def test_name_three_characters_passes(self):
        """Three character name should pass (minimum 3 characters)."""
        dto = DocumentLibraryPrototype(name="ABC")
        assert dto.name == "ABC"

    def test_name_exactly_128_characters_passes(self):
        """Name with exactly 128 characters should pass."""
        name_128 = "A" + "a" * 127
        dto = DocumentLibraryPrototype(name=name_128)
        assert len(dto.name) == 128

    def test_description_exactly_2000_characters_passes(self):
        """Description with exactly 2000 characters should pass."""
        desc_2000 = "A" * 2000
        dto = DocumentLibraryPrototype(name="Test", description=desc_2000)
        assert len(dto.description) == 2000

    def test_original_size_zero_passes(self):
        """Zero original_size should pass."""
        dto = DocumentLibraryPrototype(name="Test", original_size=0)
        assert dto.original_size == 0

    def test_final_size_zero_passes(self):
        """Zero final_size should pass."""
        dto = DocumentLibraryPrototype(name="Test", final_size=0)
        assert dto.final_size == 0

    def test_original_size_max_safe_integer_passes(self):
        """MAX_SAFE_INTEGER for original_size should pass."""
        max_safe = 9007199254740991
        library = DocumentLibrary.create(name="Test", original_size=max_safe)
        assert library.original_size == max_safe

    def test_final_size_max_safe_integer_passes(self):
        """MAX_SAFE_INTEGER for final_size should pass."""
        max_safe = 9007199254740991
        library = DocumentLibrary.create(name="Test", final_size=max_safe)
        assert library.final_size == max_safe

    def test_empty_tags_list_passes(self):
        """Empty tags list should pass."""
        dto = DocumentLibraryPrototype(name="Test", tags=[])
        assert dto.tags == []

    def test_tags_with_empty_strings_passes(self):
        """Tags containing empty strings should pass (no validation on tag content)."""
        dto = DocumentLibraryPrototype(name="Test", tags=["", "valid", ""])
        assert len(dto.tags) == 3

    def test_name_with_spaces_passes(self):
        """Name with spaces should pass."""
        dto = DocumentLibraryPrototype(name="Test Library Name")
        assert dto.name == "Test Library Name"

    def test_name_with_underscores_passes(self):
        """Name with underscores should pass."""
        dto = DocumentLibraryPrototype(name="Test_Library_Name")
        assert dto.name == "Test_Library_Name"

    def test_name_with_digits_passes(self):
        """Name with digits (after first char) should pass."""
        dto = DocumentLibraryPrototype(name="Test123Library")
        assert dto.name == "Test123Library"


class TestValidationConsistencyWithDocumentSet:
    """Verify Document Library validation matches Document Set pattern.

    These tests ensure consistency between Document Library and Document Set
    validation rules as requested in GitHub issue #6073.
    """

    def test_name_must_start_with_letter(self):
        """Name must start with letter (matching Document Set)."""
        with pytest.raises(ValidationError):
            DocumentLibraryPrototype(name="123Test")
        with pytest.raises(ValidationError):
            DocumentLibraryPrototype(name="_Test")

    def test_name_max_128_characters(self):
        """Name limited to 128 characters (matching Document Set)."""
        valid_name = "A" + "a" * 127
        dto = DocumentLibraryPrototype(name=valid_name)
        assert len(dto.name) == 128

        invalid_name = "A" + "a" * 128
        with pytest.raises(ValidationError):
            DocumentLibraryPrototype(name=invalid_name)

    def test_name_alphanumeric_spaces_underscores_only(self):
        """Name allows only alphanumeric, spaces, underscores (matching Document Set)."""
        # Valid characters
        dto = DocumentLibraryPrototype(name="Test Library 123_Name")
        assert dto.name == "Test Library 123_Name"

        # Invalid characters
        with pytest.raises(ValidationError):
            DocumentLibraryPrototype(name="Test-Library")  # hyphen not allowed
        with pytest.raises(ValidationError):
            DocumentLibraryPrototype(name="Test@Library")  # @ not allowed

    def test_description_max_2000_characters(self):
        """Description limited to 2000 characters (matching Document Set)."""
        valid_desc = "A" * 2000
        dto = DocumentLibraryPrototype(name="Test", description=valid_desc)
        assert len(dto.description) == 2000

        invalid_desc = "A" * 2001
        with pytest.raises(ValidationError):
            DocumentLibraryPrototype(name="Test", description=invalid_desc)

    def test_pattern_enforcement_at_dto_layer(self):
        """Pattern validation enforced at DTO layer."""
        with pytest.raises(ValidationError) as exc_info:
            DocumentLibraryPrototype(name="Test@Library")
        error_msg = str(exc_info.value)
        assert "can only contain letters, digits, spaces, and underscores" in error_msg

    def test_pattern_enforcement_at_domain_layer(self):
        """Pattern validation enforced at domain layer."""
        with pytest.raises(DocpipeException) as exc_info:
            DocumentLibrary.create(name="Test@Library")
        assert "can only contain letters, digits, spaces, and underscores" in str(exc_info.value)
