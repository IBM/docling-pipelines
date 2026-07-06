"""Unit tests for FlowEnrichmentService."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from docpipe.core.assets.flows.application.services.flow_enrichment_service import FlowEnrichmentService
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.exceptions.docpipe_exceptions import FlowValidationException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_feature(*, source_node_id: str = "node-1", type_: str = "string") -> dict[str, Any]:
    """Return a minimal raw feature dict as produced by FeaturePropagator."""
    return {
        "description": "",
        "available_for_filter": True,
        "available_for_vector_db": False,
        "type": type_,
        "source_node_id": source_node_id,
        "tags": [],
    }


def _make_node_feature_result(
    *,
    available: dict | None = None,
    inputs: dict | None = None,
    outputs: dict | None = None,
) -> dict[str, Any]:
    """Return a per-node feature result dict as returned by propagate_features_per_node."""
    return {
        OperatorConstants.Config.AVAILABLE_FEATURES: available or {},
        OperatorConstants.Config.INPUT_FEATURES: inputs or {},
        OperatorConstants.Config.OUTPUT_FEATURES: outputs or {},
        "dropped_features": [],
    }


def _make_service(node_features: dict[str, Any]) -> FlowEnrichmentService:
    """Return a FlowEnrichmentService whose validator returns ``node_features``."""
    mock_validator = MagicMock()
    mock_validator.propagate_features_per_node.return_value = node_features

    with patch(
        "docpipe.core.assets.flows.application.services.flow_enrichment_service.ValidationService"
    ) as mock_vs_cls:
        mock_vs = MagicMock()
        mock_vs._convert_to_dag_flow.return_value = {
            "dag": [],
            OperatorConstants.Config.GLOBAL_CONFIG: {},
        }
        mock_vs_cls.return_value = mock_vs
        service = FlowEnrichmentService(validator_factory=lambda: mock_validator)

    return service


def _minimal_elyra_flow(*node_ids_and_ops: tuple[str, str]) -> dict[str, Any]:
    """Build a minimal Elyra JSON with the given (node_id, op) pairs."""
    nodes = [{"id": node_id, "op": op, "parameters": {}} for node_id, op in node_ids_and_ops]
    return {
        "doc_type": "pipeline",
        "version": "3.0",
        "pipelines": [
            {
                "nodes": nodes,
                "app_data": {"ds_flow": {"name": "Test Flow", "global_config": {}}},
            }
        ],
    }


# ---------------------------------------------------------------------------
# Tests: enrich_flow_with_features — guard clauses
# ---------------------------------------------------------------------------


class TestEnrichFlowWithFeaturesGuards:
    """Tests for input validation in enrich_flow_with_features."""

    def test_raises_value_error_for_empty_dict(self):
        """Empty dict raises ValueError."""
        service = _make_service({})
        with pytest.raises(ValueError, match="flow_definition is required"):
            service.enrich_flow_with_features(flow_definition={})

    def test_raises_value_error_for_none(self):
        """None raises ValueError."""
        service = _make_service({})
        with pytest.raises(ValueError, match="flow_definition is required"):
            service.enrich_flow_with_features(flow_definition=None)  # type: ignore[arg-type]

    def test_propagates_flow_validation_exception(self):
        """FlowValidationException from the validator bubbles up unchanged."""
        mock_validator = MagicMock()
        mock_validator.propagate_features_per_node.side_effect = FlowValidationException(
            errors=[{"code": "CYCLE_DETECTED", "message": "Cycle in DAG"}]
        )

        with patch(
            "docpipe.core.assets.flows.application.services.flow_enrichment_service.ValidationService"
        ) as mock_vs_cls:
            mock_vs = MagicMock()
            mock_vs._convert_to_dag_flow.return_value = {"dag": [], "global_config": {}}
            mock_vs_cls.return_value = mock_vs
            service = FlowEnrichmentService(validator_factory=lambda: mock_validator)

        with pytest.raises(FlowValidationException):
            service.enrich_flow_with_features(flow_definition=_minimal_elyra_flow(("node-1", "ingest_local")))


# ---------------------------------------------------------------------------
# Tests: enrich_flow_with_features — metadata injection
# ---------------------------------------------------------------------------


class TestEnrichFlowWithFeaturesMetadataInjection:
    """Tests for feature metadata injection into node parameters."""

    def test_injects_metadata_into_matched_node(self):
        """Node with a matching ID gets input/output/available_features injected."""
        feature = _make_feature(source_node_id="node-1")
        node_features = {
            "node-1": _make_node_feature_result(
                inputs={"content": feature},
                outputs={"chunk": feature},
            )
        }
        service = _make_service(node_features)
        flow = _minimal_elyra_flow(("node-1", "chunker"))

        result = service.enrich_flow_with_features(flow_definition=flow)

        node_params = result["pipelines"][0]["nodes"][0]["parameters"]
        assert "input_features" in node_params
        assert "output_features" in node_params
        assert "available_features" in node_params
        assert "content" in node_params["input_features"]
        assert "chunk" in node_params["output_features"]

    def test_does_not_inject_into_unmatched_node(self):
        """Node absent from node_features is left untouched."""
        service = _make_service({})  # no features for any node
        flow = _minimal_elyra_flow(("node-unknown", "chunker"))

        result = service.enrich_flow_with_features(flow_definition=flow)

        node_params = result["pipelines"][0]["nodes"][0]["parameters"]
        assert "input_features" not in node_params
        assert "output_features" not in node_params

    def test_does_not_mutate_original_flow(self):
        """The original flow_definition dict is not modified."""
        feature = _make_feature()
        node_features = {"node-1": _make_node_feature_result(inputs={"content": feature})}
        service = _make_service(node_features)
        flow = _minimal_elyra_flow(("node-1", "chunker"))

        import copy

        original = copy.deepcopy(flow)
        service.enrich_flow_with_features(flow_definition=flow)

        assert flow == original

    def test_normalises_feature_shape(self):
        """Raw feature dict is normalised to the expected feature shape."""
        feature = {
            "description": "The document content",
            "available_for_filter": True,
            "available_for_vector_db": True,
            "type": "int64",
            "source_node_id": "node-0",
            "tags": ["mandatory"],
        }
        node_features = {"node-1": _make_node_feature_result(inputs={"content": feature})}
        service = _make_service(node_features)
        flow = _minimal_elyra_flow(("node-1", "chunker"))

        result = service.enrich_flow_with_features(flow_definition=flow)
        normalised = result["pipelines"][0]["nodes"][0]["parameters"]["input_features"]["content"]

        assert normalised["name"] == "content"
        assert normalised["description"] == "The document content"
        assert normalised["available_for_filter"] is True
        assert normalised["available_for_vector_db"] is True
        assert normalised["type"] == "int64"
        assert normalised["node_id"] == "node-0"
        assert normalised["tags"] == ["mandatory"]

    def test_falls_back_to_node_id_when_source_node_id_missing(self):
        """node_id falls back to the Elyra node ID when source_node_id is absent."""
        feature = {
            "description": "",
            "available_for_filter": True,
            "available_for_vector_db": False,
            "type": "string",
            "tags": [],
        }
        node_features = {"node-1": _make_node_feature_result(inputs={"content": feature})}
        service = _make_service(node_features)
        flow = _minimal_elyra_flow(("node-1", "chunker"))

        result = service.enrich_flow_with_features(flow_definition=flow)
        normalised = result["pipelines"][0]["nodes"][0]["parameters"]["input_features"]["content"]

        assert normalised["node_id"] == "node-1"

    def test_merges_into_existing_parameters(self):
        """Existing node parameters are preserved; metadata keys are added."""
        node_features = {"node-1": _make_node_feature_result(outputs={"chunk": _make_feature()})}
        service = _make_service(node_features)
        flow = {
            "doc_type": "pipeline",
            "pipelines": [
                {
                    "nodes": [{"id": "node-1", "op": "chunker", "parameters": {"chunk_size": 512}}],
                    "app_data": {},
                }
            ],
        }

        result = service.enrich_flow_with_features(flow_definition=flow)
        node_params = result["pipelines"][0]["nodes"][0]["parameters"]

        assert node_params["chunk_size"] == 512
        assert "output_features" in node_params

    def test_handles_multiple_nodes_across_pipelines(self):
        """Metadata is injected into all matching nodes across multiple pipelines."""
        node_features = {
            "node-1": _make_node_feature_result(outputs={"id": _make_feature()}),
            "node-2": _make_node_feature_result(inputs={"id": _make_feature()}),
        }

        with patch(
            "docpipe.core.assets.flows.application.services.flow_enrichment_service.ValidationService"
        ) as mock_vs_cls:
            mock_vs = MagicMock()
            mock_vs._convert_to_dag_flow.return_value = {"dag": [], "global_config": {}}
            mock_vs_cls.return_value = mock_vs
            mock_validator = MagicMock()
            mock_validator.propagate_features_per_node.return_value = node_features
            service = FlowEnrichmentService(validator_factory=lambda: mock_validator)

        flow = {
            "doc_type": "pipeline",
            "pipelines": [
                {"nodes": [{"id": "node-1", "op": "ingest_local", "parameters": {}}], "app_data": {}},
                {"nodes": [{"id": "node-2", "op": "chunker", "parameters": {}}], "app_data": {}},
            ],
        }

        result = service.enrich_flow_with_features(flow_definition=flow)

        assert "output_features" in result["pipelines"][0]["nodes"][0]["parameters"]
        assert "input_features" in result["pipelines"][1]["nodes"][0]["parameters"]


# ---------------------------------------------------------------------------
# Tests: _build_node_feature_metadata — available_features rules
# ---------------------------------------------------------------------------


class TestBuildNodeFeatureMetadataAvailableFeatures:
    """Tests for operator-specific available_features population rules."""

    def _build(self, operator_type: str, available: dict | None = None) -> dict[str, Any]:
        service = FlowEnrichmentService.__new__(FlowEnrichmentService)
        return service._build_node_feature_metadata(
            node_id="node-x",
            node_feature_result=_make_node_feature_result(available=available or {}),
            operator_type=operator_type,
        )

    def test_sql_filter_populates_available_features(self):
        """sql_filter returns available_features from the snapshot."""
        available = {"content": _make_feature()}
        result = self._build(OperatorConstants.Operators.SQL_FILTER, available=available)
        assert "content" in result[OperatorConstants.Config.AVAILABLE_FEATURES]

    def test_vectordb_populates_available_features(self):
        """vectordb returns available_features from the snapshot."""
        available = {"content": _make_feature(), "embeddings": _make_feature()}
        result = self._build(OperatorConstants.Operators.VECTORDB, available=available)
        assert "content" in result[OperatorConstants.Config.AVAILABLE_FEATURES]
        assert "embeddings" in result[OperatorConstants.Config.AVAILABLE_FEATURES]

    def test_merge_populates_available_features(self):
        """merge returns available_features from the snapshot (flat dict, current behaviour)."""
        available = {"id": _make_feature()}
        result = self._build(OperatorConstants.Operators.MERGE, available=available)
        assert "id" in result[OperatorConstants.Config.AVAILABLE_FEATURES]

    def test_other_operators_return_empty_available_features(self):
        """All operators other than sql_filter, vectordb, merge return empty available_features."""
        for op in (
            OperatorConstants.Operators.CHUNKER,
            OperatorConstants.Operators.EMBEDDINGS,
            OperatorConstants.Operators.INGEST_LOCAL,
            OperatorConstants.Operators.EXTRACT_OPERATOR,
            OperatorConstants.Operators.LANG_DETECT,
        ):
            result = self._build(op, available={"content": _make_feature()})
            assert result[OperatorConstants.Config.AVAILABLE_FEATURES] == {}, (
                f"Expected empty available_features for operator '{op}'"
            )

    def test_unknown_operator_returns_empty_available_features(self):
        """Unrecognised operator type returns empty available_features."""
        result = self._build("some_future_operator", available={"content": _make_feature()})
        assert result[OperatorConstants.Config.AVAILABLE_FEATURES] == {}

    def test_input_and_output_always_populated(self):
        """input_features and output_features are always populated regardless of operator type."""
        inputs = {"content": _make_feature()}
        outputs = {"chunk": _make_feature()}
        service = FlowEnrichmentService.__new__(FlowEnrichmentService)
        result = service._build_node_feature_metadata(
            node_id="node-x",
            node_feature_result=_make_node_feature_result(inputs=inputs, outputs=outputs),
            operator_type="noop",
        )
        assert "content" in result[OperatorConstants.Config.INPUT_FEATURES]
        assert "chunk" in result[OperatorConstants.Config.OUTPUT_FEATURES]

    def test_empty_feature_maps_produce_empty_dicts(self):
        """Empty snapshot maps produce empty output dicts."""
        service = FlowEnrichmentService.__new__(FlowEnrichmentService)
        result = service._build_node_feature_metadata(
            node_id="node-x",
            node_feature_result=_make_node_feature_result(),
            operator_type="chunker",
        )
        assert result[OperatorConstants.Config.AVAILABLE_FEATURES] == {}
        assert result[OperatorConstants.Config.INPUT_FEATURES] == {}
        assert result[OperatorConstants.Config.OUTPUT_FEATURES] == {}
