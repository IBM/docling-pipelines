"""Unit tests for ACL Operator."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from docpipe.core.constants.constants import ExecutionStatus, Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.acl.acl_operator import ACLOperator
from docpipe.exceptions.docpipe_exceptions import (
    FlowExecutionFailedException,
)


class TestACLOperatorInitialization:
    """Test ACL operator initialization and configuration."""

    def test_init_with_valid_config(self, sample_acl_config):
        """Test operator initialization with valid configuration."""
        operator = ACLOperator(sample_acl_config)

        assert operator.provider_config == sample_acl_config["provider_config"]
        assert operator.fail_on_error is True

    def test_init_with_fail_on_error_false(self, sample_acl_config):
        """Test operator initialization with fail_on_error=false."""
        config = sample_acl_config.copy()
        config["fail_on_error"] = False

        operator = ACLOperator(config)

        assert operator.fail_on_error is False

    def test_init_with_default_fail_on_error(self, sample_acl_config):
        """Test operator initialization with default fail_on_error."""
        config = sample_acl_config.copy()
        del config["fail_on_error"]

        operator = ACLOperator(config)

        assert operator.fail_on_error is True  # Default value

    def test_get_required_features(self, sample_acl_config):
        """Test get_required_features returns correct list."""
        operator = ACLOperator(sample_acl_config)
        required = operator.get_required_features()

        assert OperatorConstants.Columns.PATH in required
        assert OperatorConstants.Columns.SOURCE_ID in required


class TestACLOperatorValidation:
    """Test operator validation logic."""

    def test_validate_valid_config(self, sample_acl_config):
        """Test validation with valid configuration."""
        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_factory.return_value = Mock()

            with patch(
                "docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.is_provider_registered"
            ) as mock_registered:
                mock_registered.return_value = True

                operator = ACLOperator(sample_acl_config)
                errors = []
                warnings = []
                available_features = ["id", "path", "source_id"]

                operator.validate(errors, warnings, available_features)

                assert len(errors) == 0

    def test_validate_missing_provider(self, sample_acl_config):
        """Test validation - provider now extracted from table metadata at runtime."""
        # Provider is no longer validated during config validation
        # It's extracted from table metadata during transform()
        operator = ACLOperator(sample_acl_config)
        errors = []
        warnings = []

        operator.validate(errors, warnings, ["id", "path", "source_id"])

        # Should pass validation since provider is not required in config
        assert len(errors) == 0

    def test_validate_unknown_provider(self, sample_acl_config):
        """Test validation - provider validation happens at runtime, not config time."""
        # Provider validation moved to runtime (during transform)
        operator = ACLOperator(sample_acl_config)
        errors = []
        warnings = []

        operator.validate(errors, warnings, ["id", "path", "source_id"])

        # Should pass - provider validation is at runtime
        assert len(errors) == 0

    def test_validate_invalid_provider_config_type(self, sample_acl_config):
        """Test validation with invalid provider_config type."""
        config = sample_acl_config.copy()
        config["provider_config"] = "not_a_dict"

        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_factory.return_value = Mock()

            operator = ACLOperator(config)
            errors = []
            warnings = []

            operator.validate(errors, warnings, ["id", "path", "source_id"])

            assert len(errors) > 0
            assert any("provider_config must be a dict" in err for err in errors)

    def test_validate_invalid_fail_on_error_type(self, sample_acl_config):
        """Test validation with invalid fail_on_error type."""
        config = sample_acl_config.copy()
        config["fail_on_error"] = "not_a_bool"

        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_factory.return_value = Mock()

            operator = ACLOperator(config)
            errors = []
            warnings = []

            operator.validate(errors, warnings, ["id", "path", "source_id"])

            assert len(errors) > 0
            assert any("fail_on_error must be a boolean" in err for err in errors)


class TestACLOperatorMetadata:
    """Test operator metadata methods."""

    def test_get_metadata_structure(self, sample_acl_config):
        """Test get_metadata returns correct structure."""
        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_factory.return_value = Mock()

            operator = ACLOperator(sample_acl_config)
            metadata = operator.get_metadata()

            assert isinstance(metadata, dict)
            assert OperatorConstants.Misc.CATEGORY in metadata
            assert OperatorConstants.Config.FEATURES in metadata
            assert OperatorConstants.Config.ATTRIBUTES in metadata
            assert OperatorConstants.Misc.IS_OPERATOR_AVAILABLE in metadata

    def test_get_metadata_features(self, sample_acl_config):
        """Test metadata includes correct features."""
        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_factory.return_value = Mock()

            operator = ACLOperator(sample_acl_config)
            metadata = operator.get_metadata()

            features = metadata[OperatorConstants.Config.FEATURES]

            assert OperatorConstants.ACL.ALLOWED_USERS_COLUMN in features
            allowed_users_feature = features[OperatorConstants.ACL.ALLOWED_USERS_COLUMN]
            assert allowed_users_feature[OperatorConstants.Config.AVAILABLE_FOR_OPENSEARCH] is True

    def test_get_metadata_attributes(self, sample_acl_config):
        """Test metadata includes correct attributes."""
        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_factory.return_value = Mock()

            operator = ACLOperator(sample_acl_config)
            metadata = operator.get_metadata()

            attributes = metadata[OperatorConstants.Config.ATTRIBUTES]

            assert OperatorConstants.Config.PROVIDER_CONFIG in attributes
            assert OperatorConstants.Config.FAIL_ON_ERROR in attributes


class TestACLOperatorTransform:
    """Test the transform method with various scenarios."""

    def test_transform_single_document_success(
        self, sample_acl_config, sample_acl_table_single_doc, mock_acl_response_success
    ):
        """Test transform with a single document successfully."""
        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_adapter = Mock()
            mock_adapter.extract_acls_batch = AsyncMock(return_value=[mock_acl_response_success])
            mock_factory.return_value = mock_adapter

            operator = ACLOperator(sample_acl_config)
            result_tables, metadata = operator.transform(sample_acl_table_single_doc)

            assert len(result_tables) == 1
            result_table = result_tables[0]

            # Check allowed_users column was added
            assert OperatorConstants.ACL.ALLOWED_USERS_COLUMN in result_table.column_names
            assert result_table.num_rows == 1

            # Check allowed_users content
            allowed_users_json = result_table[OperatorConstants.ACL.ALLOWED_USERS_COLUMN][0].as_py()
            assert isinstance(allowed_users_json, list)
            assert len(allowed_users_json) == 3

            # Check metadata
            assert metadata[Metrics.External.TOTAL_DOCS] == 1
            assert metadata[Metrics.External.PROCESSED_DOCS] == 1
            assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0
            assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED.value

    def test_transform_multiple_documents_success(self, sample_acl_config, sample_acl_table, mock_acl_response_success):
        """Test transform with multiple documents successfully."""
        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_adapter = Mock()
            # Return 3 responses for 3 documents
            mock_adapter.extract_acls_batch = AsyncMock(
                return_value=[mock_acl_response_success, mock_acl_response_success, mock_acl_response_success]
            )
            mock_factory.return_value = mock_adapter

            operator = ACLOperator(sample_acl_config)
            result_tables, metadata = operator.transform(sample_acl_table)

            result_table = result_tables[0]

            # Check all documents were processed
            assert result_table.num_rows == 3
            assert OperatorConstants.ACL.ALLOWED_USERS_COLUMN in result_table.column_names

            # Check metadata
            assert metadata[Metrics.External.TOTAL_DOCS] == 3
            assert metadata[Metrics.External.PROCESSED_DOCS] == 3
            assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0

    def test_transform_empty_table(self, sample_acl_config, sample_acl_table_empty):
        """Test transform with an empty table."""
        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_factory.return_value = Mock()

            operator = ACLOperator(sample_acl_config)
            result_tables, metadata = operator.transform(sample_acl_table_empty)

            result_table = result_tables[0]

            # Should handle empty table gracefully
            assert result_table.num_rows == 0
            assert metadata[Metrics.External.TOTAL_DOCS] == 0
            assert metadata[Metrics.External.PROCESSED_DOCS] == 0

    def test_transform_fail_on_error_true_raises_exception(
        self, sample_acl_config, sample_acl_table_single_doc, mock_acl_response_failure
    ):
        """Test transform with fail_on_error=true raises exception on failure."""
        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_adapter = Mock()
            mock_adapter.extract_acl = AsyncMock(return_value=mock_acl_response_failure)
            mock_factory.return_value = mock_adapter

            operator = ACLOperator(sample_acl_config)

            with pytest.raises(FlowExecutionFailedException) as exc_info:
                operator.transform(sample_acl_table_single_doc)

            assert "ACL extraction failed" in str(exc_info.value)

    def test_transform_fail_on_error_false_skips_failed_docs(
        self, sample_acl_config, sample_acl_table, mock_acl_response_success, mock_acl_response_failure
    ):
        """Test transform with fail_on_error=false skips failed documents."""
        config = sample_acl_config.copy()
        config["fail_on_error"] = False

        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_adapter = Mock()
            # Return batch with mixed success/failure
            mock_adapter.extract_acls_batch = AsyncMock(
                return_value=[mock_acl_response_success, mock_acl_response_failure, mock_acl_response_success]
            )
            mock_factory.return_value = mock_adapter

            operator = ACLOperator(config)
            result_tables, metadata = operator.transform(sample_acl_table)

            result_table = result_tables[0]

            # Should have 2 successful documents (failed one removed)
            assert result_table.num_rows == 2
            assert metadata[Metrics.External.PROCESSED_DOCS] == 2
            assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
            assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED_WITH_ERRORS.value

    def test_transform_missing_source_id_fail_on_error_true(
        self, sample_acl_config, sample_acl_table_missing_source_id, mock_acl_response_success
    ):
        """Test transform with missing source_id and fail_on_error=true."""
        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_adapter = Mock()
            mock_adapter.extract_acl = AsyncMock(return_value=mock_acl_response_success)
            mock_factory.return_value = mock_adapter

            operator = ACLOperator(sample_acl_config)

            with pytest.raises(FlowExecutionFailedException) as exc_info:
                operator.transform(sample_acl_table_missing_source_id)

            assert "Missing required metadata" in str(exc_info.value)

    def test_transform_missing_source_id_fail_on_error_false(
        self, sample_acl_config, sample_acl_table_missing_source_id, mock_acl_response_success
    ):
        """Test transform with missing source_id and fail_on_error=false."""
        config = sample_acl_config.copy()
        config["fail_on_error"] = False

        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_adapter = Mock()
            mock_adapter.extract_acls_batch = AsyncMock(return_value=[mock_acl_response_success])
            mock_factory.return_value = mock_adapter

            operator = ACLOperator(config)
            result_tables, metadata = operator.transform(sample_acl_table_missing_source_id)

            result_table = result_tables[0]

            # Should have 1 successful document (one with missing source_id skipped)
            assert result_table.num_rows == 1
            assert metadata[Metrics.External.PROCESSED_DOCS] == 1
            assert metadata[Metrics.External.SKIPPED_DOCS_COUNT] == 1

    def test_transform_with_warnings(
        self, sample_acl_config, sample_acl_table_single_doc, mock_acl_response_with_warnings
    ):
        """Test transform with ACL extraction warnings."""
        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_adapter = Mock()
            mock_adapter.extract_acls_batch = AsyncMock(return_value=[mock_acl_response_with_warnings])
            mock_factory.return_value = mock_adapter

            operator = ACLOperator(sample_acl_config)
            result_tables, metadata = operator.transform(sample_acl_table_single_doc)

            result_table = result_tables[0]

            # Should succeed despite warnings
            assert result_table.num_rows == 1
            assert metadata[Metrics.External.PROCESSED_DOCS] == 1
            assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0

    def test_transform_preserves_existing_columns(self, sample_acl_config, sample_acl_table, mock_acl_response_success):
        """Test that transform preserves existing columns."""
        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_adapter = Mock()
            mock_adapter.extract_acls_batch = AsyncMock(
                return_value=[mock_acl_response_success, mock_acl_response_success, mock_acl_response_success]
            )
            mock_factory.return_value = mock_adapter

            operator = ACLOperator(sample_acl_config)
            result_tables, _metadata = operator.transform(sample_acl_table)

            result_table = result_tables[0]

            # Check all original columns are preserved
            assert "id" in result_table.column_names
            assert "name" in result_table.column_names
            assert "source_id" in result_table.column_names
            assert "content" in result_table.column_names
            assert "path" in result_table.column_names
            assert OperatorConstants.ACL.ALLOWED_USERS_COLUMN in result_table.column_names

    def test_transform_adapter_exception_fail_on_error_true(self, sample_acl_config, sample_acl_table_single_doc):
        """Test transform when adapter raises exception with fail_on_error=true."""
        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_adapter = Mock()
            mock_adapter.extract_acl = AsyncMock(side_effect=Exception("API error"))
            mock_factory.return_value = mock_adapter

            operator = ACLOperator(sample_acl_config)

            with pytest.raises(FlowExecutionFailedException) as exc_info:
                operator.transform(sample_acl_table_single_doc)

            assert "ACL extraction failed" in str(exc_info.value)

    def test_transform_adapter_exception_fail_on_error_false(self, sample_acl_config, sample_acl_table_single_doc):
        """Test transform when adapter raises exception with fail_on_error=false."""
        config = sample_acl_config.copy()
        config["fail_on_error"] = False

        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_adapter = Mock()
            mock_adapter.extract_acl = AsyncMock(side_effect=Exception("API error"))
            mock_factory.return_value = mock_adapter

            operator = ACLOperator(config)
            result_tables, metadata = operator.transform(sample_acl_table_single_doc)

            result_table = result_tables[0]

            # Should have 0 documents (failed one removed)
            assert result_table.num_rows == 0
            assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
            assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED_WITH_ERRORS.value


class TestACLOperatorMetadataTracking:
    """Test metadata tracking in various scenarios."""

    def test_metadata_includes_processed_docs_count(
        self, sample_acl_config, sample_acl_table, mock_acl_response_success
    ):
        """Test metadata includes processed_docs count."""
        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_adapter = Mock()
            mock_adapter.extract_acls_batch = AsyncMock(
                return_value=[mock_acl_response_success, mock_acl_response_success, mock_acl_response_success]
            )
            mock_factory.return_value = mock_adapter

            operator = ACLOperator(sample_acl_config)
            _result_tables, metadata = operator.transform(sample_acl_table)

            assert Metrics.External.PROCESSED_DOCS in metadata
            assert metadata[Metrics.External.PROCESSED_DOCS] == 3

    def test_metadata_includes_failed_docs_count(
        self, sample_acl_config, sample_acl_table, mock_acl_response_success, mock_acl_response_failure
    ):
        """Test metadata includes failed_docs count."""
        config = sample_acl_config.copy()
        config["fail_on_error"] = False

        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_adapter = Mock()
            mock_adapter.extract_acls_batch = AsyncMock(
                return_value=[mock_acl_response_success, mock_acl_response_failure, mock_acl_response_success]
            )
            mock_factory.return_value = mock_adapter

            operator = ACLOperator(config)
            _result_tables, metadata = operator.transform(sample_acl_table)

            assert Metrics.External.FAILED_DOCS_COUNT in metadata
            assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1

    def test_metadata_includes_node_status(
        self, sample_acl_config, sample_acl_table_single_doc, mock_acl_response_success
    ):
        """Test metadata includes node_status."""
        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_adapter = Mock()
            mock_adapter.extract_acls_batch = AsyncMock(return_value=[mock_acl_response_success])
            mock_factory.return_value = mock_adapter

            operator = ACLOperator(sample_acl_config)
            _result_tables, metadata = operator.transform(sample_acl_table_single_doc)

            assert Metrics.External.NODE_STATUS in metadata
            assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED.value

    def test_metadata_node_status_with_errors(
        self, sample_acl_config, sample_acl_table_single_doc, mock_acl_response_failure
    ):
        """Test node_status is COMPLETED_WITH_ERRORS when failures occur."""
        config = sample_acl_config.copy()
        config["fail_on_error"] = False

        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_adapter = Mock()
            mock_adapter.extract_acl = AsyncMock(return_value=mock_acl_response_failure)
            mock_factory.return_value = mock_adapter

            operator = ACLOperator(config)
            _result_tables, metadata = operator.transform(sample_acl_table_single_doc)

            assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED_WITH_ERRORS.value

    def test_metadata_completeness(self, sample_acl_config, sample_acl_table_single_doc, mock_acl_response_success):
        """Test that all required metadata fields are present."""
        with patch("docpipe.core.operators.acl.acl_operator.ACLAdapterFactory.create_adapter") as mock_factory:
            mock_adapter = Mock()
            mock_adapter.extract_acls_batch = AsyncMock(return_value=[mock_acl_response_success])
            mock_factory.return_value = mock_adapter

            operator = ACLOperator(sample_acl_config)
            _result_tables, metadata = operator.transform(sample_acl_table_single_doc)

            # Check all required fields
            required_fields = [
                Metrics.External.TOTAL_DOCS,
                Metrics.External.PROCESSED_DOCS,
                Metrics.External.FAILED_DOCS_COUNT,
                Metrics.External.FAILED_DOCS,
                Metrics.External.SKIPPED_DOCS_COUNT,
                Metrics.External.SKIPPED_DOCS,
                Metrics.External.NODE_STATUS,
            ]

            for field in required_fields:
                assert field in metadata, f"Missing required metadata field: {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
