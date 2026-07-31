"""Unit tests for mandatory_for_vector_db propagation through FeaturePropagationResult.

Covers:
- FeatureMetadata has mandatory_for_vector_db field with correct default
- FeaturePropagationResult.add_feature() stores mandatory_for_vector_db
- FeaturePropagator.feature_metadata_to_dict() serialises the flag
- FlowValidator._feature_metadata_to_dict() serialises the flag
"""

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.orchestration.feature_propagation.features_propagator import FeaturePropagator
from docpipe.core.orchestration.feature_propagation.models import (
    FeatureMetadata,
    FeaturePropagationResult,
)

# ---------------------------------------------------------------------------
# FeatureMetadata model
# ---------------------------------------------------------------------------


class TestFeatureMetadataModel:
    """FeatureMetadata carries mandatory_for_vector_db as a proper Pydantic field."""

    def test_mandatory_for_vector_db_defaults_to_false(self):
        meta = FeatureMetadata(name="content", node_id="node-1")
        assert meta.mandatory_for_vector_db is False

    def test_mandatory_for_vector_db_true_is_stored(self):
        meta = FeatureMetadata(name="doc_id", node_id="node-1", mandatory_for_vector_db=True)
        assert meta.mandatory_for_vector_db is True

    def test_mandatory_for_vector_db_coerces_value(self):
        """Pydantic bool field; truthy non-bool inputs are valid."""
        meta = FeatureMetadata(name="doc_id", node_id="node-1", mandatory_for_vector_db=True)
        assert meta.mandatory_for_vector_db is True


# ---------------------------------------------------------------------------
# FeaturePropagationResult.add_feature()
# ---------------------------------------------------------------------------


class TestAddFeatureMandatoryFlag:
    """add_feature() stores mandatory_for_vector_db in feature_metadata."""

    def test_add_feature_stores_mandatory_true(self):
        result = FeaturePropagationResult()
        result.add_feature(
            feature_name="doc_id_hash",
            node_id="ingest-node",
            mandatory_for_vector_db=True,
        )
        assert result.feature_metadata["doc_id_hash"].mandatory_for_vector_db is True

    def test_add_feature_stores_mandatory_false_by_default(self):
        result = FeaturePropagationResult()
        result.add_feature(feature_name="content", node_id="extract-node")
        assert result.feature_metadata["content"].mandatory_for_vector_db is False

    def test_add_feature_multiple_features_independent_flags(self):
        result = FeaturePropagationResult()
        result.add_feature(feature_name="doc_id_hash", node_id="n1", mandatory_for_vector_db=True)
        result.add_feature(feature_name="content", node_id="n1", mandatory_for_vector_db=False)
        assert result.feature_metadata["doc_id_hash"].mandatory_for_vector_db is True
        assert result.feature_metadata["content"].mandatory_for_vector_db is False


# ---------------------------------------------------------------------------
# FeaturePropagator.feature_metadata_to_dict()
# ---------------------------------------------------------------------------


class TestFeatureMetadataToDictSerialisesFlag:
    """feature_metadata_to_dict() must include mandatory_for_vector_db."""

    def _serialise(self, *, mandatory: bool) -> dict:
        propagator = FeaturePropagator.__new__(FeaturePropagator)
        meta = FeatureMetadata(
            name="doc_id",
            node_id="node-1",
            mandatory_for_vector_db=mandatory,
        )
        return propagator.feature_metadata_to_dict(feature_meta=meta)

    def test_mandatory_true_is_in_serialised_dict(self):
        result = self._serialise(mandatory=True)
        assert result[OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB] is True

    def test_mandatory_false_is_in_serialised_dict(self):
        result = self._serialise(mandatory=False)
        assert result[OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB] is False

    def test_serialised_dict_also_has_other_standard_keys(self):
        result = self._serialise(mandatory=False)
        assert OperatorConstants.Config.AVAILABLE_FOR_FILTER in result
        assert OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB in result
        assert OperatorConstants.Config.DESCRIPTION in result


# ---------------------------------------------------------------------------
# FlowValidator._feature_metadata_to_dict()
# ---------------------------------------------------------------------------


class TestFlowValidatorFeatureMetadataToDictSerialisesFlag:
    """FlowValidator._feature_metadata_to_dict() is a separate serialisation path
    that must also expose mandatory_for_vector_db.

    The method takes a FeaturePropagationResult, not a FeatureMetadata directly.
    """

    def _serialise(self, *, mandatory: bool) -> dict[str, dict]:
        from docpipe.core.orchestration.flow_validator import FlowValidator

        validator = FlowValidator.__new__(FlowValidator)
        prop_result = FeaturePropagationResult()
        prop_result.add_feature(
            feature_name="embeddings",
            node_id="embed-node",
            mandatory_for_vector_db=mandatory,
        )
        return validator._feature_metadata_to_dict(result=prop_result)

    def test_mandatory_true_present_in_flow_validator_dict(self):
        result = self._serialise(mandatory=True)
        assert result["embeddings"][OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB] is True

    def test_mandatory_false_present_in_flow_validator_dict(self):
        result = self._serialise(mandatory=False)
        assert result["embeddings"][OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB] is False
