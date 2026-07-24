"""Unit tests for Error DTO validation."""

import pytest
from pydantic import ValidationError

from docpipe.api.dto.error_dto import (
    ErrorDetail,
    ErrorResponse,
    ErrorTarget,
)


class TestErrorDetailValidation:
    """Tests for ErrorDetail DTO validation."""

    def test_error_detail_with_valid_data(self):
        """Test creating error detail with valid data."""
        # Act
        dto = ErrorDetail(
            code="invalid_parameter",
            message="The 'flow_id' parameter is invalid",
            more_info="https://docs.example.com/errors/invalid_parameter",
            target=ErrorTarget(type="parameter", name="flow_id"),
        )

        # Assert
        assert dto.code == "invalid_parameter"
        assert dto.message == "The 'flow_id' parameter is invalid"
        assert dto.more_info == "https://docs.example.com/errors/invalid_parameter"
        assert dto.target is not None

    def test_error_detail_message_max_length_10000_valid(self):
        """Test that message with exactly 10000 characters is valid."""
        # Arrange
        message_10000 = "x" * 10000

        # Act
        dto = ErrorDetail(code="validation_error", message=message_10000)

        # Assert
        assert len(dto.message) == 10000

    def test_error_detail_message_exceeding_10000_chars_raises_error(self):
        """Test that message exceeding 10000 characters raises validation error."""
        # Arrange
        long_message = "x" * 10001

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ErrorDetail(code="validation_error", message=long_message)

        assert "message" in str(exc_info.value)

    def test_error_detail_message_with_newlines(self):
        """Test that message allows \\r\\n characters."""
        # Arrange
        message_with_newlines = "Line 1\r\nLine 2\r\nLine 3"

        # Act
        dto = ErrorDetail(code="validation_error", message=message_with_newlines)

        # Assert
        assert "\r\n" in dto.message
        assert dto.message == message_with_newlines

    def test_error_detail_more_info_empty_string_valid(self):
        """Test that more_info accepts empty string."""
        # Act
        dto = ErrorDetail(
            code="validation_error",
            message="Test message",
            more_info="",
        )

        # Assert
        assert dto.more_info == ""

    def test_error_detail_more_info_max_length_10000_valid(self):
        """Test that more_info with exactly 10000 characters is valid."""
        # Arrange
        more_info_10000 = "x" * 10000

        # Act
        dto = ErrorDetail(
            code="validation_error",
            message="Test message",
            more_info=more_info_10000,
        )

        # Assert
        assert len(dto.more_info) == 10000

    def test_error_detail_more_info_exceeding_10000_chars_raises_error(self):
        """Test that more_info exceeding 10000 characters raises validation error."""
        # Arrange
        long_more_info = "x" * 10001

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ErrorDetail(
                code="validation_error",
                message="Test message",
                more_info=long_more_info,
            )

        assert "more_info" in str(exc_info.value)

    def test_error_detail_more_info_ascii_pattern(self):
        """Test that more_info follows ASCII pattern (space to tilde)."""
        # Arrange - ASCII printable characters (space to tilde)
        ascii_more_info = "https://docs.example.com/errors?code=123&type=validation"

        # Act
        dto = ErrorDetail(
            code="validation_error",
            message="Test message",
            more_info=ascii_more_info,
        )

        # Assert
        assert dto.more_info == ascii_more_info

    def test_error_detail_without_optional_fields(self):
        """Test creating error detail without optional fields."""
        # Act
        dto = ErrorDetail(code="internal_error", message="An unexpected error occurred")

        # Assert
        assert dto.code == "internal_error"
        assert dto.message == "An unexpected error occurred"
        assert dto.more_info is None
        assert dto.target is None


class TestErrorTargetValidation:
    """Tests for ErrorTarget DTO validation."""

    def test_error_target_with_valid_data(self):
        """Test creating error target with valid data."""
        # Act
        dto = ErrorTarget(type="parameter", name="flow_id")

        # Assert
        assert dto.type == "parameter"
        assert dto.name == "flow_id"

    def test_error_target_name_permissive_pattern(self):
        """Test that name pattern is permissive and allows various formats."""
        # Arrange - Test various name formats
        test_names = [
            "flow_id",
            "definition -> nodes -> 0 -> operator_type",
            "Authorization",
            "name",
            "tags[0]",
            "nested.field.path",
        ]

        # Act & Assert
        for name in test_names:
            dto = ErrorTarget(type="field", name=name)
            assert dto.name == name

    def test_error_target_name_max_length_256_valid(self):
        """Test that name with exactly 256 characters is valid."""
        # Arrange
        name_256 = "x" * 256

        # Act
        dto = ErrorTarget(type="field", name=name_256)

        # Assert
        assert len(dto.name) == 256

    def test_error_target_name_exceeding_256_chars_raises_error(self):
        """Test that name exceeding 256 characters raises validation error."""
        # Arrange
        long_name = "x" * 257

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ErrorTarget(type="field", name=long_name)

        assert "name" in str(exc_info.value)


class TestErrorResponseValidation:
    """Tests for ErrorResponse DTO validation."""

    def test_error_response_with_valid_data(self):
        """Test creating error response with valid data."""
        # Act
        dto = ErrorResponse(
            errors=[
                ErrorDetail(
                    code="not_found",
                    message="Flow not found",
                )
            ],
            trace="550e8400-e29b-41d4-a716-446655440000",
            status_code=404,
        )

        # Assert
        assert len(dto.errors) == 1
        assert dto.trace == "550e8400-e29b-41d4-a716-446655440000"
        assert dto.status_code == 404

    def test_error_response_trace_uuid_v4_format_valid(self):
        """Test that trace accepts valid UUID v4 format."""
        # Arrange - Valid UUID v4 (36 chars with specific pattern)
        valid_uuids = [
            "550e8400-e29b-41d4-a716-446655440000",
            "9a5137a7-15d5-431c-b945-b147a3043694",
            "123e4567-e89b-12d3-a456-426614174000",
        ]

        # Act & Assert
        for uuid in valid_uuids:
            dto = ErrorResponse(
                errors=[ErrorDetail(code="not_found", message="Test")],
                trace=uuid,
                status_code=404,
            )
            assert dto.trace == uuid
            assert len(dto.trace) == 36

    def test_error_response_trace_invalid_uuid_raises_error(self):
        """Test that trace with invalid UUID format raises validation error."""
        # Arrange - Invalid UUID formats
        invalid_uuids = [
            "not-a-uuid",
            "550e8400-e29b-41d4-a716",  # Too short
            "550e8400-e29b-41d4-a716-446655440000-extra",  # Too long
            "550e8400e29b41d4a716446655440000",  # pragma: allowlist secret - Missing hyphens
            "GGGGGGGG-e29b-41d4-a716-446655440000",  # Invalid hex
        ]

        # Act & Assert
        for invalid_uuid in invalid_uuids:
            with pytest.raises(ValidationError) as exc_info:
                ErrorResponse(
                    errors=[ErrorDetail(code="not_found", message="Test")],
                    trace=invalid_uuid,
                    status_code=404,
                )
            assert "trace" in str(exc_info.value)

    def test_error_response_trace_exactly_36_chars(self):
        """Test that trace must be exactly 36 characters."""
        # Arrange
        trace_35 = "550e8400-e29b-41d4-a716-44665544000"  # 35 chars
        trace_37 = "550e8400-e29b-41d4-a716-4466554400000"  # 37 chars

        # Act & Assert - 35 chars should fail
        with pytest.raises(ValidationError) as exc_info:
            ErrorResponse(
                errors=[ErrorDetail(code="not_found", message="Test")],
                trace=trace_35,
                status_code=404,
            )
        assert "trace" in str(exc_info.value)

        # 37 chars should fail
        with pytest.raises(ValidationError) as exc_info:
            ErrorResponse(
                errors=[ErrorDetail(code="not_found", message="Test")],
                trace=trace_37,
                status_code=404,
            )
        assert "trace" in str(exc_info.value)

    def test_error_response_with_multiple_errors(self):
        """Test error response with multiple error details."""
        # Act
        dto = ErrorResponse(
            errors=[
                ErrorDetail(code="validation_error", message="Field 'name' is required"),
                ErrorDetail(
                    code="validation_error",
                    message="Field 'definition' must be valid JSON",
                ),
            ],
            trace="550e8400-e29b-41d4-a716-446655440000",
            status_code=400,
        )

        # Assert
        assert len(dto.errors) == 2
        assert dto.status_code == 400

    def test_error_response_status_code_range(self):
        """Test that status_code must be between 400 and 599."""
        # Valid status codes
        valid_codes = [400, 404, 500, 503, 599]
        for code in valid_codes:
            dto = ErrorResponse(
                errors=[ErrorDetail(code="not_found", message="Test")],
                trace="550e8400-e29b-41d4-a716-446655440000",
                status_code=code,
            )
            assert dto.status_code == code

        # Invalid status codes
        invalid_codes = [200, 399, 600]
        for code in invalid_codes:
            with pytest.raises(ValidationError) as exc_info:
                ErrorResponse(
                    errors=[ErrorDetail(code="not_found", message="Test")],
                    trace="550e8400-e29b-41d4-a716-446655440000",
                    status_code=code,
                )
            assert "status_code" in str(exc_info.value)


class TestErrorDTOEdgeCases:
    """Tests for edge cases in Error DTOs."""

    def test_error_detail_with_all_error_codes(self):
        """Test that all defined error codes are valid."""
        # Arrange
        error_codes = [
            "invalid_request",
            "invalid_parameter",
            "unauthorized",
            "forbidden",
            "not_found",
            "method_not_allowed",
            "conflict",
            "validation_error",
            "too_many_requests",
            "internal_error",
            "service_unavailable",
            "unknown_error",
        ]

        # Act & Assert
        for code in error_codes:
            dto = ErrorDetail(code=code, message="Test message")
            assert dto.code == code

    def test_error_response_with_max_errors(self):
        """Test error response with maximum number of errors (100)."""
        # Arrange
        errors = [ErrorDetail(code="validation_error", message=f"Error {i}") for i in range(100)]

        # Act
        dto = ErrorResponse(
            errors=errors,
            trace="550e8400-e29b-41d4-a716-446655440000",
            status_code=400,
        )

        # Assert
        assert len(dto.errors) == 100

    def test_error_response_with_more_than_100_errors_raises_error(self):
        """Test that more than 100 errors raises validation error."""
        # Arrange
        errors = [ErrorDetail(code="validation_error", message=f"Error {i}") for i in range(101)]

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ErrorResponse(
                errors=errors,
                trace="550e8400-e29b-41d4-a716-446655440000",
                status_code=400,
            )

        assert "errors" in str(exc_info.value)
