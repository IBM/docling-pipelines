#!/usr/bin/env python3
"""
Unit tests for OperatorMetadata class.
Tests metadata retrieval, feature filtering, and operator mapping functionality.
"""

from collections import defaultdict
from unittest.mock import Mock, patch

import pytest

from docpipe.core.constants.constants import OrchestratorType
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.operator_metadata import OperatorMetadata

# ---------------------------------------------------------------------------
# Test Fixtures and Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_operator_factory():
    """Create a mock OperatorFactory with test operators."""
    factory = Mock()

    # Mock operator 1: successful operator with features
    op1_class = Mock()
    op1_instance = Mock()
    # get_metadata() and get_required_features() are now static methods on the class
    op1_class.get_metadata.return_value = {
        OperatorConstants.Misc.LABEL: "Test Operator 1",
        OperatorConstants.Config.FEATURES: {
            "feature1": {
                "type": "string",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                OperatorConstants.Misc.TAGS: [],
            },
            "feature2": {
                "type": "int",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: False,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TAGS: [],
            },
            "internal_feature": {
                "type": "string",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: False,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.INTERNAL_FEATURE],
            },
        },
    }
    op1_class.get_required_features.return_value = ["required_feature1"]
    op1_class.return_value = op1_instance

    # Mock operator 2: successful operator without features
    op2_class = Mock()
    op2_instance = Mock()
    # get_metadata() and get_required_features() are now static methods on the class
    op2_class.get_metadata.return_value = {
        OperatorConstants.Misc.LABEL: "Test Operator 2",
    }
    op2_class.get_required_features.return_value = []
    op2_class.return_value = op2_instance

    # Mock operator 3: failing operator
    op3_class = Mock()
    op3_class.side_effect = Exception("Operator initialization failed")

    # Mock operator 4: operator with is_available() = False
    op4_class = Mock()
    op4_instance = Mock()
    # get_metadata() is now a static method on the class
    op4_class.get_metadata.side_effect = Exception("Not available")
    op4_instance.is_available.return_value = False
    op4_class.return_value = op4_instance

    factory.operators = {
        "test_op1": op1_class,
        "test_op2": op2_class,
        "test_op3": op3_class,
        "test_op4": op4_class,
    }

    def get_operator_side_effect(operator_name):
        """Return mock operator with is_available method."""
        mock_op = Mock()
        if operator_name == "test_op4":
            mock_op.is_available.return_value = False
        else:
            mock_op.is_available.return_value = True
        return mock_op

    factory.get_operator.side_effect = get_operator_side_effect

    return factory


@pytest.fixture
def mock_session_info():
    """Create a mock session_info."""
    return Mock()


# ---------------------------------------------------------------------------
# 1. Constructor Tests
# ---------------------------------------------------------------------------


def test_init_creates_empty_operator_metadata():
    """Constructor initializes with empty operator_metadata dict."""
    with patch("docpipe.core.operators.operator_metadata.get_session_info"):
        metadata = OperatorMetadata()

        assert isinstance(metadata.operator_metadata, dict)
        assert len(metadata.operator_metadata) == 0


def test_init_calls_get_session_info():
    """Constructor calls get_session_info to initialize session."""
    with patch("docpipe.core.operators.operator_metadata.get_session_info") as mock_get_session:
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        metadata = OperatorMetadata()

        mock_get_session.assert_called_once()
        assert metadata.session_info == mock_session


# ---------------------------------------------------------------------------
# 2. get_operator_metadata() Tests - Basic Functionality
# ---------------------------------------------------------------------------


def test_get_operator_metadata_returns_dict(mock_operator_factory, mock_session_info):
    """get_operator_metadata() returns a dictionary."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            result = metadata.get_operator_metadata()

            assert isinstance(result, dict)


def test_get_operator_metadata_processes_all_operators(mock_operator_factory, mock_session_info):
    """get_operator_metadata() processes all operators from factory."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            result = metadata.get_operator_metadata()

            # Should have entries for all operators (even failed ones get empty dict)
            assert "test_op1" in result
            assert "test_op2" in result
            assert "test_op3" in result
            assert "test_op4" in result


def test_get_operator_metadata_includes_required_features(mock_operator_factory, mock_session_info):
    """get_operator_metadata() includes required_features in metadata."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            result = metadata.get_operator_metadata()

            assert "required_features" in result["test_op1"]
            assert result["test_op1"]["required_features"] == ["required_feature1"]


def test_get_operator_metadata_handles_failed_operators(mock_operator_factory, mock_session_info):
    """get_operator_metadata() handles operators that fail to initialize."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            result = metadata.get_operator_metadata()

            # Failed operator should have empty dict
            assert result["test_op3"] == {}


def test_get_operator_metadata_updates_internal_cache(mock_operator_factory, mock_session_info):
    """get_operator_metadata() updates internal operator_metadata cache."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            result = metadata.get_operator_metadata()

            # Internal cache should be updated
            assert metadata.operator_metadata == result


# ---------------------------------------------------------------------------
# 3. get_operator_metadata() Tests - Internal Features Filtering
# ---------------------------------------------------------------------------


def test_get_operator_metadata_filters_internal_features_by_default(mock_operator_factory, mock_session_info):
    """get_operator_metadata() filters internal features by default."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            result = metadata.get_operator_metadata(internal_features=False)

            features = result["test_op1"][OperatorConstants.Config.FEATURES]
            assert "feature1" in features
            assert "feature2" in features
            assert "internal_feature" not in features


def test_get_operator_metadata_includes_internal_features_when_requested(mock_operator_factory, mock_session_info):
    """get_operator_metadata() includes internal features when internal_features=True."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            result = metadata.get_operator_metadata(internal_features=True)

            features = result["test_op1"][OperatorConstants.Config.FEATURES]
            assert "feature1" in features
            assert "feature2" in features
            assert "internal_feature" in features


def test_get_operator_metadata_handles_missing_features_key(mock_session_info):
    """get_operator_metadata() handles operators without FEATURES key."""
    factory = Mock()
    op_class = Mock()
    op_instance = Mock()
    op_class.get_metadata.return_value = {
        OperatorConstants.Misc.LABEL: "No Features Operator",
    }
    op_class.get_required_features.return_value = []
    op_class.return_value = op_instance
    factory.operators = {"test_op": op_class}
    factory.get_operator.return_value = Mock(is_available=Mock(return_value=True))

    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=factory,
        ):
            metadata = OperatorMetadata()
            result = metadata.get_operator_metadata(internal_features=False)

            # Should not crash, operator should be in result
            assert "test_op" in result


# ---------------------------------------------------------------------------
# 4. get_operator_metadata() Tests - Error Handling and Logging
# ---------------------------------------------------------------------------


def test_get_operator_metadata_logs_available_operators(mock_operator_factory, mock_session_info):
    """get_operator_metadata() logs available operators."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            with patch("docpipe.core.operators.operator_metadata.logger") as mock_logger:
                metadata = OperatorMetadata()
                metadata.get_operator_metadata()

                # Should log discovering operators
                mock_logger.info.assert_called()
                call_args = str(mock_logger.info.call_args)
                assert "Discovering operators" in call_args


def test_get_operator_metadata_logs_warning_for_unavailable_operators(mock_operator_factory, mock_session_info):
    """get_operator_metadata() logs warning for unavailable operators with missing metadata."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            with patch("docpipe.core.operators.operator_metadata.logger") as mock_logger:
                metadata = OperatorMetadata()
                metadata.get_operator_metadata()

                # Should log warning for operators that failed but are available
                mock_logger.warning.assert_called()
                call_args = str(mock_logger.warning.call_args)
                assert "Metadata missing" in call_args


def test_get_operator_metadata_does_not_warn_for_unavailable_operators(mock_operator_factory, mock_session_info):
    """get_operator_metadata() does not warn for operators that are not available."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            with patch("docpipe.core.operators.operator_metadata.logger") as mock_logger:
                metadata = OperatorMetadata()
                metadata.get_operator_metadata()

                # Check that test_op4 (unavailable) is not in warning
                if mock_logger.warning.called:
                    call_args = str(mock_logger.warning.call_args)
                    # test_op4 should not be in the warning since it's not available
                    assert "test_op4" not in call_args or "test_op3" in call_args


# ---------------------------------------------------------------------------
# 5. get_features() Tests - Basic Functionality
# ---------------------------------------------------------------------------


def test_get_features_returns_all_features_when_no_purpose(mock_operator_factory, mock_session_info):
    """get_features() returns all features when purpose is None."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            metadata.get_operator_metadata(internal_features=True)

            result = metadata.get_features(short_name="test_op1", purpose=None)

            assert "feature1" in result
            assert "feature2" in result
            assert "internal_feature" in result


def test_get_features_filters_by_available_for_filter(mock_operator_factory, mock_session_info):
    """get_features() filters features by AVAILABLE_FOR_FILTER purpose."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            metadata.get_operator_metadata(internal_features=True)

            result = metadata.get_features(
                short_name="test_op1",
                purpose=OperatorConstants.Config.AVAILABLE_FOR_FILTER,
            )

            assert "feature1" in result
            assert "feature2" not in result
            assert "internal_feature" not in result


def test_get_features_filters_by_available_for_vector_db(mock_operator_factory, mock_session_info):
    """get_features() filters features by AVAILABLE_FOR_VECTOR_DB purpose."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            metadata.get_operator_metadata(internal_features=True)

            result = metadata.get_features(
                short_name="test_op1",
                purpose=OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB,
            )

            assert "feature1" not in result
            assert "feature2" in result
            assert "internal_feature" not in result


def test_get_features_returns_empty_dict_for_nonexistent_operator(mock_operator_factory, mock_session_info):
    """get_features() returns empty dict for nonexistent operator."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            metadata.get_operator_metadata()

            result = metadata.get_features(short_name="nonexistent_op")

            assert result == {}


def test_get_features_returns_empty_dict_for_operator_without_features(mock_operator_factory, mock_session_info):
    """get_features() returns empty dict for operator without features."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            metadata.get_operator_metadata()

            result = metadata.get_features(short_name="test_op2")

            assert result == {}


# ---------------------------------------------------------------------------
# 6. get_features_from_input_output_features() Tests
# ---------------------------------------------------------------------------


def test_get_features_from_input_output_features_merges_features():
    """get_features_from_input_output_features() merges input and output features."""
    with patch("docpipe.core.operators.operator_metadata.get_session_info"):
        metadata = OperatorMetadata()

        input_features = {
            "input1": {"type": "string"},
            "input2": {"type": "int"},
        }
        output_features = {
            "output1": {"type": "string"},
            "output2": {"type": "int"},
        }

        result = metadata.get_features_from_input_output_features(
            purpose=None,
            input_features=input_features,
            output_features=output_features,
        )

        assert "input1" in result
        assert "input2" in result
        assert "output1" in result
        assert "output2" in result


def test_get_features_from_input_output_features_output_overwrites_input():
    """get_features_from_input_output_features() output features overwrite input features."""
    with patch("docpipe.core.operators.operator_metadata.get_session_info"):
        metadata = OperatorMetadata()

        input_features = {
            "feature1": {"type": "string", "value": "input"},
        }
        output_features = {
            "feature1": {"type": "int", "value": "output"},
        }

        result = metadata.get_features_from_input_output_features(
            purpose=None,
            input_features=input_features,
            output_features=output_features,
        )

        assert result["feature1"]["value"] == "output"
        assert result["feature1"]["type"] == "int"


def test_get_features_from_input_output_features_filters_by_purpose():
    """get_features_from_input_output_features() filters by purpose."""
    with patch("docpipe.core.operators.operator_metadata.get_session_info"):
        metadata = OperatorMetadata()

        input_features = {
            "feature1": {
                "type": "string",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
            },
            "feature2": {
                "type": "int",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: False,
            },
        }

        result = metadata.get_features_from_input_output_features(
            purpose=OperatorConstants.Config.AVAILABLE_FOR_FILTER,
            input_features=input_features,
            output_features=None,
        )

        assert "feature1" in result
        assert "feature2" not in result


def test_get_features_from_input_output_features_handles_none_input():
    """get_features_from_input_output_features() handles None input_features."""
    with patch("docpipe.core.operators.operator_metadata.get_session_info"):
        metadata = OperatorMetadata()

        output_features = {
            "output1": {"type": "string"},
        }

        result = metadata.get_features_from_input_output_features(
            purpose=None,
            input_features=None,
            output_features=output_features,
        )

        assert "output1" in result


def test_get_features_from_input_output_features_handles_none_output():
    """get_features_from_input_output_features() handles None output_features."""
    with patch("docpipe.core.operators.operator_metadata.get_session_info"):
        metadata = OperatorMetadata()

        input_features = {
            "input1": {"type": "string"},
        }

        result = metadata.get_features_from_input_output_features(
            purpose=None,
            input_features=input_features,
            output_features=None,
        )

        assert "input1" in result


def test_get_features_from_input_output_features_returns_empty_for_both_none():
    """get_features_from_input_output_features() returns empty dict when both are None."""
    with patch("docpipe.core.operators.operator_metadata.get_session_info"):
        metadata = OperatorMetadata()

        result = metadata.get_features_from_input_output_features(
            purpose=None,
            input_features=None,
            output_features=None,
        )

        assert result == {}


# ---------------------------------------------------------------------------
# 7. required_feature_names() Tests
# ---------------------------------------------------------------------------


def test_required_feature_names_returns_list(mock_operator_factory, mock_session_info):
    """required_feature_names() returns list of required features."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            metadata.get_operator_metadata()

            result = metadata.required_feature_names(short_name="test_op1")

            assert isinstance(result, list)
            assert result == ["required_feature1"]


def test_required_feature_names_returns_empty_list_for_nonexistent_operator(mock_operator_factory, mock_session_info):
    """required_feature_names() returns empty list for nonexistent operator."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            metadata.get_operator_metadata()

            result = metadata.required_feature_names(short_name="nonexistent_op")

            assert result == []


def test_required_feature_names_returns_empty_list_for_operator_without_required_features(
    mock_operator_factory, mock_session_info
):
    """required_feature_names() returns empty list for operator without required features."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            metadata.get_operator_metadata()

            result = metadata.required_feature_names(short_name="test_op2")

            assert result == []


# ---------------------------------------------------------------------------
# 8. get_feature_operators_map() Tests
# ---------------------------------------------------------------------------


def test_get_feature_operators_map_returns_defaultdict(mock_operator_factory, mock_session_info):
    """get_feature_operators_map() returns a defaultdict."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            result = metadata.get_feature_operators_map()

            assert isinstance(result, defaultdict)


def test_get_feature_operators_map_maps_features_to_operators(mock_operator_factory, mock_session_info):
    """get_feature_operators_map() creates feature-to-operators mapping."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            result = metadata.get_feature_operators_map()

            # feature1 and feature2 should map to Test Operator 1
            assert "Test Operator 1" in result["feature1"]
            assert "Test Operator 1" in result["feature2"]


def test_get_feature_operators_map_calls_get_operator_metadata_with_internal_features(
    mock_operator_factory, mock_session_info
):
    """get_feature_operators_map() calls get_operator_metadata with internal_features=True."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()

            with patch.object(metadata, "get_operator_metadata") as mock_get_metadata:
                mock_get_metadata.return_value = {}
                metadata.get_feature_operators_map()

                mock_get_metadata.assert_called_once_with(internal_features=True)


def test_get_feature_operators_map_includes_internal_features(mock_operator_factory, mock_session_info):
    """get_feature_operators_map() includes internal features in mapping."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            result = metadata.get_feature_operators_map()

            # internal_feature should be in the map
            assert "Test Operator 1" in result["internal_feature"]


def test_get_feature_operators_map_handles_operators_without_label(mock_session_info):
    """get_feature_operators_map() handles operators without label."""
    factory = Mock()
    op_class = Mock()
    op_instance = Mock()
    op_class.get_metadata.return_value = {
        OperatorConstants.Config.FEATURES: {
            "feature1": {"type": "string"},
        },
    }
    op_class.get_required_features.return_value = []
    op_class.return_value = op_instance
    factory.operators = {"test_op": op_class}
    factory.get_operator.return_value = Mock(is_available=Mock(return_value=True))

    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=factory,
        ):
            metadata = OperatorMetadata()
            result = metadata.get_feature_operators_map()

            # feature1 should not be in map since operator has no label
            assert "feature1" not in result or len(result["feature1"]) == 0


def test_get_feature_operators_map_handles_empty_features(mock_session_info):
    """get_feature_operators_map() handles operators with no features."""
    factory = Mock()
    op_class = Mock()
    op_instance = Mock()
    op_class.get_metadata.return_value = {
        OperatorConstants.Misc.LABEL: "Empty Operator",
    }
    op_class.get_required_features.return_value = []
    op_class.return_value = op_instance
    factory.operators = {"test_op": op_class}
    factory.get_operator.return_value = Mock(is_available=Mock(return_value=True))

    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=factory,
        ):
            metadata = OperatorMetadata()
            result = metadata.get_feature_operators_map()

            # Should not crash, result should be valid defaultdict
            assert isinstance(result, defaultdict)


# ---------------------------------------------------------------------------
# 9. Edge Cases and Integration Tests
# ---------------------------------------------------------------------------


def test_multiple_calls_to_get_operator_metadata_accumulate(mock_operator_factory, mock_session_info):
    """Multiple calls to get_operator_metadata() accumulate in cache."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()

            result1 = metadata.get_operator_metadata()
            result2 = metadata.get_operator_metadata()

            # Both results should be the same
            assert result1 == result2
            # Internal cache should match
            assert metadata.operator_metadata == result2


def test_get_features_uses_cached_metadata(mock_operator_factory, mock_session_info):
    """get_features() uses cached metadata from previous get_operator_metadata() call."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=mock_operator_factory,
        ):
            metadata = OperatorMetadata()
            metadata.get_operator_metadata(internal_features=True)

            # Manually modify cache to verify it's being used
            metadata.operator_metadata["test_op1"][OperatorConstants.Config.FEATURES]["custom_feature"] = {
                "type": "custom"
            }

            result = metadata.get_features(short_name="test_op1")

            assert "custom_feature" in result


def test_empty_operator_factory(mock_session_info):
    """Handles empty operator factory gracefully."""
    factory = Mock()
    factory.operators = {}

    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=factory,
        ):
            metadata = OperatorMetadata()
            result = metadata.get_operator_metadata()

            assert result == {}


def test_operator_factory_provider_called_with_python_orchestrator(mock_session_info):
    """get_operator_metadata() calls OperatorFactoryProvider with PYTHON orchestrator."""
    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory"
        ) as mock_get_factory:
            mock_factory = Mock()
            mock_factory.operators = {}
            mock_get_factory.return_value = mock_factory

            metadata = OperatorMetadata()
            metadata.get_operator_metadata()

            mock_get_factory.assert_called_once_with(orchestrator=OrchestratorType.PYTHON)


def test_get_operator_metadata_handles_non_static_get_metadata(mock_session_info):
    """get_operator_metadata() handles operators with non-static get_metadata() (backward compatibility)."""
    factory = Mock()

    # Mock operator with non-static get_metadata (raises TypeError when called on class)
    op_class = Mock()
    op_instance = Mock()

    # Simulate TypeError when calling get_metadata() as static method
    op_class.get_metadata.side_effect = TypeError("get_metadata() missing 1 required positional argument: 'self'")

    # Instance method should work
    op_instance.get_metadata.return_value = {
        OperatorConstants.Misc.LABEL: "Legacy Operator",
        OperatorConstants.Config.FEATURES: {
            "legacy_feature": {"type": "string"},
        },
    }

    # get_required_features is static
    op_class.get_required_features.return_value = ["input_feature"]

    factory.operators = {"legacy_op": op_class}
    factory.get_operator.return_value = op_instance

    with patch(
        "docpipe.core.operators.operator_metadata.get_session_info",
        return_value=mock_session_info,
    ):
        with patch(
            "docpipe.core.operators.operator_metadata.OperatorFactoryProvider.get_operator_factory",
            return_value=factory,
        ):
            with patch("docpipe.core.operators.operator_metadata.logger") as mock_logger:
                metadata = OperatorMetadata()
                result = metadata.get_operator_metadata()

                # Should successfully get metadata via instance method
                assert "legacy_op" in result
                assert result["legacy_op"][OperatorConstants.Misc.LABEL] == "Legacy Operator"
                assert "legacy_feature" in result["legacy_op"][OperatorConstants.Config.FEATURES]
                assert result["legacy_op"]["required_features"] == ["input_feature"]

                # Should log debug message about backward compatibility
                mock_logger.debug.assert_called()
                debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
                assert any(
                    "non-static get_metadata()" in call and "backward compatibility" in call for call in debug_calls
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
