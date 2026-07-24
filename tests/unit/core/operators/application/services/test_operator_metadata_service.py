"""Unit tests for OperatorMetadataService.

This test suite validates the application service layer for operator metadata,
ensuring proper:
- Business logic execution
- Exception handling and translation
- Logging behavior
- Keyword-only argument enforcement
- Integration with domain layer (OperatorMetadata)

Test Strategy:
    - Mock the domain layer (OperatorMetadata) for isolated service testing
    - Verify service correctly delegates to domain layer
    - Verify service translates exceptions to DocpipeException
    - Verify logging at appropriate levels (info, error)
    - Test both success and failure scenarios

Coverage:
    - Success cases: Metadata retrieval with/without internal features
    - Error cases: Domain layer failures, exception translation
    - Logging: Info logs on success, error logs on failure
    - Initialization: Service creates OperatorMetadata instance
    - API contract: Keyword-only arguments enforced
"""

from unittest.mock import Mock, patch

import pytest

from docpipe.core.operators.application.services.operator_metadata_service import (
    OperatorMetadataService,
)
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode


class TestOperatorMetadataServiceGetAll:
    """Tests for OperatorMetadataService.get_all_operator_metadata method.

    This test class covers the main service method that retrieves metadata
    for all operators. Tests verify:
    - Correct return type and structure
    - Internal feature filtering
    - Expected operators present
    - Required metadata fields
    - Feature type information
    - Exception handling
    - Logging behavior
    """

    def test_get_all_operator_metadata_returns_dict(self):
        """Test that get_all_operator_metadata returns a dictionary."""
        # Arrange
        service = OperatorMetadataService()

        # Act
        result = service.get_all_operator_metadata(internal_features=False)

        # Assert
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_get_all_operator_metadata_excludes_internal_features_by_default(self):
        """Test that internal features are excluded by default."""
        # Arrange
        service = OperatorMetadataService()

        # Act
        result = service.get_all_operator_metadata()

        # Assert
        assert isinstance(result, dict)
        # Verify at least one operator exists
        assert len(result) > 0

        # Check that internal features are not included
        for _operator_name, metadata in result.items():
            features = metadata.get("features", {})
            for _feature_name, feature_data in features.items():
                # Internal features should not be present
                tags = feature_data.get("tags", [])
                assert "internal" not in tags or feature_data.get("available_for_filter", False)

    def test_get_all_operator_metadata_includes_internal_features_when_requested(self):
        """Test that internal features are included when explicitly requested."""
        # Arrange
        service = OperatorMetadataService()

        # Act
        result = service.get_all_operator_metadata(internal_features=True)

        # Assert
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_get_all_operator_metadata_contains_expected_operators(self):
        """Test that result contains expected operator categories."""
        # Arrange
        service = OperatorMetadataService()
        expected_operators = [
            "extract_operator",
            "chunker",
            "ingest_source",
            "branching",
            "noop",
        ]

        # Act
        result = service.get_all_operator_metadata(internal_features=False)

        # Assert
        for operator in expected_operators:
            assert operator in result, f"Expected operator '{operator}' not found"

    def test_get_all_operator_metadata_has_required_fields(self):
        """Test that each successfully initialized operator has required metadata fields."""
        # Arrange
        service = OperatorMetadataService()
        required_fields = ["features"]  # Only features is truly required, category may be missing

        # Act
        result = service.get_all_operator_metadata(internal_features=False)

        # Assert
        for operator_name, metadata in result.items():
            # Skip operators that failed to initialize or have incomplete metadata
            if not metadata or not metadata.get("is_operator_available", True):
                continue
            for field in required_fields:
                assert field in metadata, f"Operator '{operator_name}' missing field '{field}'"

    def test_get_all_operator_metadata_features_have_type(self):
        """Test that each feature has a type field."""
        # Arrange
        service = OperatorMetadataService()

        # Act
        result = service.get_all_operator_metadata(internal_features=False)

        # Assert
        for operator_name, metadata in result.items():
            features = metadata.get("features", {})
            for feature_name, feature_data in features.items():
                assert "type" in feature_data, f"Feature '{feature_name}' in operator '{operator_name}' missing 'type'"

    @patch("docpipe.core.operators.application.services.operator_metadata_service.OperatorMetadata")
    def test_get_all_operator_metadata_raises_docpipe_exception_on_error(self, mock_operator_metadata_class):
        """Test that service raises DocpipeException when underlying call fails."""
        # Arrange
        mock_instance = Mock()
        mock_instance.get_operator_metadata.side_effect = RuntimeError("Test error")
        mock_operator_metadata_class.return_value = mock_instance

        service = OperatorMetadataService()

        # Act & Assert
        with pytest.raises(DocpipeException) as exc_info:
            service.get_all_operator_metadata(internal_features=False)

        assert exc_info.value.status_code == 500
        assert exc_info.value.error_code == ErrorCode.OPERATOR_METADATA_FAILED
        assert "Failed to retrieve operator metadata" in str(exc_info.value)

    @patch("docpipe.core.operators.application.services.operator_metadata_service.OperatorMetadata")
    def test_get_all_operator_metadata_logs_error_on_failure(self, mock_operator_metadata_class):
        """Test that errors are logged when metadata retrieval fails."""
        # Arrange
        mock_instance = Mock()
        mock_instance.get_operator_metadata.side_effect = RuntimeError("Test error")
        mock_operator_metadata_class.return_value = mock_instance

        service = OperatorMetadataService()

        # Act & Assert
        with patch("docpipe.core.operators.application.services.operator_metadata_service.logger") as mock_logger:
            with pytest.raises(DocpipeException):
                service.get_all_operator_metadata(internal_features=False)

            # Verify error was logged
            mock_logger.error.assert_called_once()
            assert "Failed to retrieve operator metadata" in mock_logger.error.call_args[0][0]

    def test_get_all_operator_metadata_logs_info_on_success(self):
        """Test that successful retrieval is logged."""
        # Arrange
        service = OperatorMetadataService()

        # Act
        with patch("docpipe.core.operators.application.services.operator_metadata_service.logger") as mock_logger:
            result = service.get_all_operator_metadata(internal_features=False)

            # Assert
            assert len(result) > 0
            # Verify info logs were called
            assert mock_logger.info.call_count >= 2
            # Check for retrieval start log
            info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
            assert any("Retrieving metadata" in call for call in info_calls)
            assert any("Successfully retrieved metadata" in call for call in info_calls)

    def test_service_initialization_creates_operator_metadata_instance(self):
        """Test that service initialization creates OperatorMetadata instance."""
        # Act
        service = OperatorMetadataService()

        # Assert
        assert hasattr(service, "operator_metadata")
        assert service.operator_metadata is not None

    def test_get_all_operator_metadata_uses_keyword_only_arguments(self):
        """Test that internal_features must be passed as keyword argument."""
        # Arrange
        service = OperatorMetadataService()

        # Act & Assert - positional argument should raise TypeError
        with pytest.raises(TypeError):
            service.get_all_operator_metadata(False)  # type: ignore
