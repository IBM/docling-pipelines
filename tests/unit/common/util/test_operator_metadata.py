"""Unit tests for operator_metadata module."""

from unittest.mock import Mock, patch

import pytest

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.operator_metadata import OperatorMetadata


class TestOperatorMetadata:
    """Test OperatorMetadata class."""

    @patch("docpipe.core.operators.operator_metadata.OperatorFactoryProvider")
    @patch("docpipe.core.operators.operator_metadata.get_session_info")
    def test_init(self, mock_session, mock_factory_provider):
        """Test OperatorMetadata initialization."""
        mock_session.return_value = Mock()

        metadata = OperatorMetadata()

        assert metadata.operator_metadata == {}
        assert metadata.session_info is not None

    @patch("docpipe.core.operators.operator_metadata.OperatorFactoryProvider")
    @patch("docpipe.core.operators.operator_metadata.get_session_info")
    def test_get_operator_metadata_basic(self, mock_session, mock_factory_provider):
        """Test getting operator metadata."""
        mock_session.return_value = Mock()

        # Mock operator factory
        mock_factory = Mock()
        mock_operator_class = Mock()
        mock_operator_instance = Mock()

        # get_metadata() and get_required_features() are now static methods on the class
        mock_operator_class.get_metadata.return_value = {
            OperatorConstants.Config.FEATURES: {
                "feature1": {
                    OperatorConstants.Columns.NAME: "Feature 1",
                    OperatorConstants.Misc.TAGS: [],
                }
            },
            OperatorConstants.Misc.CATEGORY: "Ingest",
        }
        mock_operator_class.get_required_features.return_value = ["input_feature"]

        mock_operator_class.return_value = mock_operator_instance
        mock_factory.operators = {"test_op": mock_operator_class}
        mock_factory_provider.get_operator_factory.return_value = mock_factory

        metadata = OperatorMetadata()
        result = metadata.get_operator_metadata(internal_features=False)

        assert "test_op" in result
        assert result["test_op"]["required_features"] == ["input_feature"]

    @patch("docpipe.core.operators.operator_metadata.OperatorFactoryProvider")
    @patch("docpipe.core.operators.operator_metadata.get_session_info")
    def test_get_operator_metadata_filters_internal_features(self, mock_session, mock_factory_provider):
        """Test that internal features are filtered out."""
        mock_session.return_value = Mock()

        mock_factory = Mock()
        mock_operator_class = Mock()
        mock_operator_instance = Mock()

        # get_metadata() and get_required_features() are now static methods on the class
        mock_operator_class.get_metadata.return_value = {
            OperatorConstants.Config.FEATURES: {
                "public_feature": {
                    OperatorConstants.Columns.NAME: "Public",
                    OperatorConstants.Misc.TAGS: [],
                },
                "internal_feature": {
                    OperatorConstants.Columns.NAME: "Internal",
                    OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.INTERNAL_FEATURE],
                },
            }
        }
        mock_operator_class.get_required_features.return_value = []

        mock_operator_class.return_value = mock_operator_instance
        mock_factory.operators = {"test_op": mock_operator_class}
        mock_factory_provider.get_operator_factory.return_value = mock_factory

        metadata = OperatorMetadata()
        result = metadata.get_operator_metadata(internal_features=False)

        features = result["test_op"][OperatorConstants.Config.FEATURES]
        assert "public_feature" in features
        assert "internal_feature" not in features

    @patch("docpipe.core.operators.operator_metadata.OperatorFactoryProvider")
    @patch("docpipe.core.operators.operator_metadata.get_session_info")
    def test_get_operator_metadata_includes_internal_features(self, mock_session, mock_factory_provider):
        """Test that internal features are included when requested."""
        mock_session.return_value = Mock()

        mock_factory = Mock()
        mock_operator_class = Mock()
        mock_operator_instance = Mock()

        # get_metadata() is now a static method on the class
        mock_operator_class.get_metadata.return_value = {
            OperatorConstants.Config.FEATURES: {
                "public_feature": {
                    OperatorConstants.Columns.NAME: "Public",
                    OperatorConstants.Misc.TAGS: [],
                },
                "internal_feature": {
                    OperatorConstants.Columns.NAME: "Internal",
                    OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.INTERNAL_FEATURE],
                },
            }
        }
        mock_operator_instance.get_required_features.return_value = []

        mock_operator_class.return_value = mock_operator_instance
        mock_factory.operators = {"test_op": mock_operator_class}
        mock_factory_provider.get_operator_factory.return_value = mock_factory

        metadata = OperatorMetadata()
        result = metadata.get_operator_metadata(internal_features=True)

        features = result["test_op"][OperatorConstants.Config.FEATURES]
        assert "public_feature" in features
        assert "internal_feature" in features

    @patch("docpipe.core.operators.operator_metadata.OperatorFactoryProvider")
    @patch("docpipe.core.operators.operator_metadata.get_session_info")
    def test_get_operator_metadata_handles_exceptions(self, mock_session, mock_factory_provider):
        """Test handling of operator initialization exceptions."""
        mock_session.return_value = Mock()

        mock_factory = Mock()
        mock_operator_class = Mock()
        mock_operator_class.side_effect = Exception("Initialization failed")

        mock_factory.operators = {"failing_op": mock_operator_class}
        mock_factory.get_operator.return_value = Mock(is_available=Mock(return_value=True))
        mock_factory_provider.get_operator_factory.return_value = mock_factory

        metadata = OperatorMetadata()
        result = metadata.get_operator_metadata(internal_features=False)

        assert "failing_op" in result
        assert result["failing_op"] == {}

    @patch("docpipe.core.operators.operator_metadata.get_session_info")
    def test_get_features_basic(self, mock_session):
        """Test getting features for an operator."""
        mock_session.return_value = Mock()

        metadata = OperatorMetadata()
        metadata.operator_metadata = {
            "test_op": {
                OperatorConstants.Config.FEATURES: {
                    "feature1": {"name": "Feature 1"},
                    "feature2": {"name": "Feature 2"},
                }
            }
        }

        result = metadata.get_features(short_name="test_op")

        assert len(result) == 2
        assert "feature1" in result
        assert "feature2" in result

    @patch("docpipe.core.operators.operator_metadata.get_session_info")
    def test_get_features_with_purpose_filter(self, mock_session):
        """Test getting features filtered by purpose."""
        mock_session.return_value = Mock()

        metadata = OperatorMetadata()
        metadata.operator_metadata = {
            "test_op": {
                OperatorConstants.Config.FEATURES: {
                    "filterable_feature": {
                        "name": "Filterable",
                        OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    },
                    "non_filterable_feature": {
                        "name": "Non-filterable",
                        OperatorConstants.Config.AVAILABLE_FOR_FILTER: False,
                    },
                }
            }
        }

        result = metadata.get_features(short_name="test_op", purpose=OperatorConstants.Config.AVAILABLE_FOR_FILTER)

        assert len(result) == 1
        assert "filterable_feature" in result
        assert "non_filterable_feature" not in result

    @patch("docpipe.core.operators.operator_metadata.get_session_info")
    def test_get_features_nonexistent_operator(self, mock_session):
        """Test getting features for nonexistent operator."""
        mock_session.return_value = Mock()

        metadata = OperatorMetadata()
        metadata.operator_metadata = {}

        result = metadata.get_features(short_name="nonexistent_op")

        assert result == {}

    @patch("docpipe.core.operators.operator_metadata.get_session_info")
    def test_get_features_from_input_output_features(self, mock_session):
        """Test getting features from input and output features."""
        mock_session.return_value = Mock()

        metadata = OperatorMetadata()

        input_features = {"input_feat": {"name": "Input Feature"}}
        output_features = {"output_feat": {"name": "Output Feature"}}

        result = metadata.get_features_from_input_output_features(
            input_features=input_features, output_features=output_features
        )

        assert len(result) == 2
        assert "input_feat" in result
        assert "output_feat" in result

    @patch("docpipe.core.operators.operator_metadata.get_session_info")
    def test_get_features_from_input_output_features_with_purpose(self, mock_session):
        """Test getting features with purpose filter."""
        mock_session.return_value = Mock()

        metadata = OperatorMetadata()

        input_features = {
            "feat1": {
                "name": "Feature 1",
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
            },
            "feat2": {
                "name": "Feature 2",
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
            },
        }

        result = metadata.get_features_from_input_output_features(
            input_features=input_features,
            purpose=OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB,
        )

        assert len(result) == 1
        assert "feat1" in result

    @patch("docpipe.core.operators.operator_metadata.get_session_info")
    def test_get_features_from_input_output_features_output_overrides(self, mock_session):
        """Test that output features override input features."""
        mock_session.return_value = Mock()

        metadata = OperatorMetadata()

        input_features = {"shared_feat": {"name": "Input Version"}}
        output_features = {"shared_feat": {"name": "Output Version"}}

        result = metadata.get_features_from_input_output_features(
            input_features=input_features, output_features=output_features
        )

        assert result["shared_feat"]["name"] == "Output Version"

    @patch("docpipe.core.operators.operator_metadata.get_session_info")
    def test_required_feature_names(self, mock_session):
        """Test getting required feature names."""
        mock_session.return_value = Mock()

        metadata = OperatorMetadata()
        metadata.operator_metadata = {"test_op": {"required_features": ["feature1", "feature2"]}}

        result = metadata.required_feature_names(short_name="test_op")

        assert result == ["feature1", "feature2"]

    @patch("docpipe.core.operators.operator_metadata.get_session_info")
    def test_required_feature_names_nonexistent(self, mock_session):
        """Test getting required features for nonexistent operator."""
        mock_session.return_value = Mock()

        metadata = OperatorMetadata()
        metadata.operator_metadata = {}

        result = metadata.required_feature_names(short_name="nonexistent_op")

        assert result == []

    @patch("docpipe.core.operators.operator_metadata.OperatorFactoryProvider")
    @patch("docpipe.core.operators.operator_metadata.get_session_info")
    def test_get_feature_operators_map(self, mock_session, mock_factory_provider):
        """Test getting feature to operators mapping."""
        mock_session.return_value = Mock()

        mock_factory = Mock()
        mock_operator_class = Mock()
        mock_operator_instance = Mock()

        # get_metadata() is now a static method on the class
        mock_operator_class.get_metadata.return_value = {
            OperatorConstants.Config.FEATURES: {
                "feature1": {
                    OperatorConstants.Columns.NAME: "Feature 1",
                    OperatorConstants.Misc.TAGS: [],
                }
            },
            OperatorConstants.Misc.LABEL: "Test Operator",
        }
        mock_operator_instance.get_required_features.return_value = []

        mock_operator_class.return_value = mock_operator_instance
        mock_factory.operators = {"test_op": mock_operator_class}
        mock_factory_provider.get_operator_factory.return_value = mock_factory

        metadata = OperatorMetadata()
        result = metadata.get_feature_operators_map()

        assert "feature1" in result
        assert "Test Operator" in result["feature1"]

    @patch("docpipe.core.operators.operator_metadata.OperatorFactoryProvider")
    @patch("docpipe.core.operators.operator_metadata.get_session_info")
    def test_get_feature_operators_map_no_label(self, mock_session, mock_factory_provider):
        """Test feature operators map when operator has no label."""
        mock_session.return_value = Mock()

        mock_factory = Mock()
        mock_operator_class = Mock()
        mock_operator_instance = Mock()

        mock_operator_instance.get_metadata.return_value = {
            OperatorConstants.Config.FEATURES: {
                "feature1": {
                    OperatorConstants.Columns.NAME: "Feature 1",
                    OperatorConstants.Misc.TAGS: [],
                }
            }
            # No LABEL key
        }
        mock_operator_instance.get_required_features.return_value = []

        mock_operator_class.return_value = mock_operator_instance
        mock_factory.operators = {"test_op": mock_operator_class}
        mock_factory_provider.get_operator_factory.return_value = mock_factory

        metadata = OperatorMetadata()
        result = metadata.get_feature_operators_map()

        # Feature should not be in map if operator has no label
        assert result.get("feature1", []) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
