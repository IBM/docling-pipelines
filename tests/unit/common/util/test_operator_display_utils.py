"""Unit tests for operator_display_utils module."""

from unittest.mock import Mock, patch

import pytest

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.utils.operators.display import (
    display_operator_summary,
    format_operator_details,
    list_operators,
)


class TestFormatOperatorDetails:
    """Test format_operator_details function."""

    def test_format_operator_details_basic(self):
        """Test basic operator details formatting."""
        operator_metadata = {
            "test_operator": {
                OperatorConstants.Misc.CATEGORY: "Ingest",
                OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: True,
                OperatorConstants.Config.FEATURES: {
                    "feature1": {
                        OperatorConstants.Columns.NAME: "Feature 1",
                        OperatorConstants.Config.DESCRIPTION: "Test feature",
                        OperatorConstants.Misc.TYPE: "string",
                    }
                },
                OperatorConstants.Config.ATTRIBUTES: {
                    "attr1": {
                        OperatorConstants.Columns.NAME: "Attribute 1",
                        OperatorConstants.Config.DESCRIPTION: "Test attribute",
                        OperatorConstants.Config.REQUIRED: True,
                        OperatorConstants.Misc.TYPE: "string",
                    }
                },
            }
        }

        result = format_operator_details(operator_metadata, verbose=False)

        assert "test_operator" in result
        assert "Ingest" in result
        assert "Available" in result
        assert "Feature 1" in result
        assert "Attribute 1" in result

    def test_format_operator_details_verbose(self):
        """Test verbose operator details formatting."""
        operator_metadata = {
            "test_op": {
                OperatorConstants.Misc.CATEGORY: "Extract",
                OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: True,
                OperatorConstants.Config.FEATURES: {
                    "feat1": {
                        OperatorConstants.Columns.NAME: "Feature One",
                        OperatorConstants.Config.DESCRIPTION: "Feature description",
                        OperatorConstants.Misc.TYPE: "int",
                        OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                        OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                        OperatorConstants.Misc.IS_PRIMARY: True,
                    }
                },
                OperatorConstants.Config.ATTRIBUTES: {
                    "param1": {
                        OperatorConstants.Columns.NAME: "Parameter 1",
                        OperatorConstants.Config.DESCRIPTION: "Param description",
                        OperatorConstants.Config.REQUIRED: False,
                        OperatorConstants.Config.DEFAULT: "default_value",
                        OperatorConstants.Misc.TYPE: "string",
                    }
                },
            }
        }

        result = format_operator_details(operator_metadata, verbose=True)

        assert "Feature One" in result
        assert "Feature description" in result
        assert "filterable" in result
        assert "primary" in result
        assert "Parameter 1" in result
        assert "default_value" in result
        assert "[OPTIONAL]" in result

    def test_format_operator_details_unavailable(self):
        """Test formatting unavailable operator."""
        operator_metadata = {
            "unavailable_op": {
                OperatorConstants.Misc.CATEGORY: "Unknown",
                OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: False,
                OperatorConstants.Config.FEATURES: {},
                OperatorConstants.Config.ATTRIBUTES: {},
            }
        }

        result = format_operator_details(operator_metadata, verbose=False)

        assert "unavailable_op" in result
        assert "Unavailable" in result

    def test_format_operator_details_empty_metadata(self):
        """Test with empty metadata."""
        result = format_operator_details({}, verbose=False)
        assert result == ""

    def test_format_operator_details_with_required_features(self):
        """Test formatting with required features."""
        operator_metadata = {
            "test_op": {
                OperatorConstants.Misc.CATEGORY: "Transform",
                OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: True,
                OperatorConstants.Config.FEATURES: {},
                OperatorConstants.Config.ATTRIBUTES: {},
                "required_features": ["feature1", "feature2"],
            }
        }

        result = format_operator_details(operator_metadata, verbose=False)

        assert "Required Input Features" in result
        assert "feature1" in result
        assert "feature2" in result

    def test_format_operator_details_none_metadata(self):
        """Test with None values in metadata."""
        operator_metadata = {
            "test_op": None,
            "valid_op": {
                OperatorConstants.Misc.CATEGORY: "Ingest",
                OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: True,
                OperatorConstants.Config.FEATURES: {},
                OperatorConstants.Config.ATTRIBUTES: {},
            },
        }

        result = format_operator_details(operator_metadata, verbose=False)

        assert "test_op" not in result
        assert "valid_op" in result


class TestDisplayOperatorSummary:
    """Test display_operator_summary function."""

    def test_display_operator_summary_basic(self):
        """Test basic operator summary display."""
        operator_metadata = {
            "op1": {
                OperatorConstants.Misc.CATEGORY: "Ingest",
                OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: True,
                OperatorConstants.Config.FEATURES: {"f1": {}, "f2": {}},
            },
            "op2": {
                OperatorConstants.Misc.CATEGORY: "Extract",
                OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: False,
                OperatorConstants.Config.FEATURES: {"f1": {}},
            },
        }

        result = display_operator_summary(operator_metadata)

        assert "AVAILABLE OPERATORS SUMMARY" in result
        assert "op1" in result
        assert "op2" in result
        assert "Ingest" in result
        assert "Extract" in result
        assert "Available" in result
        assert "Unavailable" in result
        assert "Total operators: 2" in result

    def test_display_operator_summary_empty(self):
        """Test summary with empty metadata."""
        result = display_operator_summary({})

        assert "AVAILABLE OPERATORS SUMMARY" in result
        assert "Total operators: 0" in result

    def test_display_operator_summary_feature_count(self):
        """Test that feature counts are displayed correctly."""
        operator_metadata = {
            "op_with_features": {
                OperatorConstants.Misc.CATEGORY: "Transform",
                OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: True,
                OperatorConstants.Config.FEATURES: {"f1": {}, "f2": {}, "f3": {}},
            },
            "op_no_features": {
                OperatorConstants.Misc.CATEGORY: "Utility",
                OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: True,
                OperatorConstants.Config.FEATURES: {},
            },
        }

        result = display_operator_summary(operator_metadata)

        assert "3" in result  # Feature count for op_with_features
        assert "0" in result  # Feature count for op_no_features


class TestListOperators:
    """Test list_operators function."""

    @patch("docpipe.core.operators.operator_metadata.OperatorMetadata")
    def test_list_operators_summary_only(self, mock_metadata_class):
        """Test listing operators with summary only."""
        mock_metadata = Mock()
        mock_metadata.get_operator_metadata.return_value = {
            "op1": {
                OperatorConstants.Misc.CATEGORY: "Ingest",
                OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: True,
                OperatorConstants.Config.FEATURES: {},
            }
        }
        mock_metadata_class.return_value = mock_metadata

        result = list_operators(verbose=False, summary_only=True)

        assert "AVAILABLE OPERATORS SUMMARY" in result
        assert "op1" in result
        mock_metadata.get_operator_metadata.assert_called_once_with(internal_features=False)

    @patch("docpipe.core.operators.operator_metadata.OperatorMetadata")
    def test_list_operators_verbose(self, mock_metadata_class):
        """Test listing operators with verbose output."""
        mock_metadata = Mock()
        mock_metadata.get_operator_metadata.return_value = {
            "op1": {
                OperatorConstants.Misc.CATEGORY: "Extract",
                OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: True,
                OperatorConstants.Config.FEATURES: {
                    "feat1": {
                        OperatorConstants.Columns.NAME: "Feature 1",
                        OperatorConstants.Config.DESCRIPTION: "Description",
                        OperatorConstants.Misc.TYPE: "string",
                    }
                },
                OperatorConstants.Config.ATTRIBUTES: {},
            }
        }
        mock_metadata_class.return_value = mock_metadata

        result = list_operators(verbose=True, summary_only=False)

        assert "op1" in result
        assert "Feature 1" in result
        mock_metadata.get_operator_metadata.assert_called_once_with(internal_features=False)

    @patch("docpipe.core.operators.operator_metadata.OperatorMetadata")
    def test_list_operators_default_params(self, mock_metadata_class):
        """Test listing operators with default parameters."""
        mock_metadata = Mock()
        mock_metadata.get_operator_metadata.return_value = {
            "op1": {
                OperatorConstants.Misc.CATEGORY: "Ingest",
                OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: True,
                OperatorConstants.Config.FEATURES: {},
            }
        }
        mock_metadata_class.return_value = mock_metadata

        result = list_operators()

        assert "AVAILABLE OPERATORS SUMMARY" in result
        mock_metadata.get_operator_metadata.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
