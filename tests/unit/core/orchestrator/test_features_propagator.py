"""Unit tests for FeaturePropagator."""

from unittest.mock import Mock, patch

import pytest

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.orchestration.feature_propagation.features_propagator import FeaturePropagator
from docpipe.core.orchestration.feature_propagation.models import (
    FeaturePropagationResult,
)
from docpipe.exceptions.docpipe_exceptions import FlowValidationException


class TestFeaturePropagator:
    """Tests for FeaturePropagator class."""

    @pytest.fixture
    def propagator(self):
        """Create FeaturePropagator instance."""
        with patch.object(FeaturePropagator, "__init__", lambda x: None):
            prop = FeaturePropagator()
            prop.operator_metadata = Mock()
            prop.operator_metadata.get_features = Mock(return_value={})
            return prop

    def test_init_loads_operator_metadata(self):
        """Test that __init__ loads operator metadata."""
        propagator = FeaturePropagator()

        # Verify operator_metadata is initialized
        assert propagator.operator_metadata is not None
        assert hasattr(propagator.operator_metadata, "get_operator_metadata")
        assert hasattr(propagator.operator_metadata, "get_features")

    def test_propagate_features_preserves_input_features(self, propagator):
        """Test that input features are preserved in output."""
        input_features = {
            "id": {
                "description": "Document ID",
                "tags": ["mandatory"],
                "available_for_filter": True,
                "available_for_vector_db": False,
                "type": "string",
            },
            "content": {
                "description": "Document content",
                "tags": ["mandatory"],
                "available_for_filter": False,
                "available_for_vector_db": False,
                "type": "string",
            },
        }

        result = propagator.propagate_features(
            node_id="test-node",
            operator_short_name="test_operator",
            operator_config={},
            input_features=input_features,
            global_config={},
            parent_results=[],
        )

        assert "id" in result.feature_metadata
        assert "content" in result.feature_metadata
        assert result.feature_metadata["id"].description == "Document ID"

    def test_propagate_features_adds_operator_features(self, propagator):
        """Test that operator-defined features are added."""
        input_features = {
            "id": {
                "description": "ID",
                "tags": [],
                "available_for_filter": True,
                "available_for_vector_db": False,
                "type": "string",
            }
        }
        operator_features = {
            "new_feature": {
                "description": "New feature from operator",
                "tags": ["operator"],
                "available_for_filter": True,
                "available_for_vector_db": False,
                "type": "string",
            }
        }
        propagator.operator_metadata.get_features = Mock(return_value=operator_features)

        result = propagator.propagate_features(
            node_id="test-node",
            operator_short_name="test_operator",
            operator_config={},
            input_features=input_features,
            global_config={},
            parent_results=[],
        )

        assert "new_feature" in result.feature_metadata
        assert result.feature_metadata["new_feature"].description == "New feature from operator"

    def test_propagate_features_stores_input_features_explicitly(self, propagator):
        """Test that input features are stored separately for inspection."""
        input_features = {
            "id": {
                "description": "ID",
                "tags": [],
                "available_for_filter": True,
                "available_for_vector_db": False,
                "type": "string",
            },
            "content": {
                "description": "Content",
                "tags": [],
                "available_for_filter": False,
                "available_for_vector_db": False,
                "type": "string",
            },
        }

        result = propagator.propagate_features(
            node_id="test-node",
            operator_short_name="test_operator",
            operator_config={},
            input_features=input_features,
            global_config={},
            parent_results=[],
        )

        stored_input = result.get_input_features(node_id="test-node")
        assert "id" in stored_input
        assert "content" in stored_input

    def test_propagate_features_computes_output_features(self, propagator):
        """Test that output features (new features only) are computed."""
        input_features = {
            "id": {
                "description": "ID",
                "tags": [],
                "available_for_filter": True,
                "available_for_vector_db": False,
                "type": "string",
            }
        }
        operator_features = {
            "new_feature": {
                "description": "New",
                "tags": [],
                "available_for_filter": True,
                "available_for_vector_db": False,
                "type": "string",
            }
        }
        propagator.operator_metadata.get_features = Mock(return_value=operator_features)

        result = propagator.propagate_features(
            node_id="test-node",
            operator_short_name="test_operator",
            operator_config={},
            input_features=input_features,
            global_config={},
            parent_results=[],
        )

        output = result.get_output_features(node_id="test-node")
        assert "new_feature" in output
        assert "id" not in output  # Input feature should not be in output

    def test_propagate_features_vectordb_produces_no_output(self, propagator):
        """Test that VectorDB operator produces no output features."""
        input_features = {
            "id": {
                "description": "ID",
                "tags": [],
                "available_for_filter": True,
                "available_for_vector_db": False,
                "type": "string",
            },
            "embeddings": {
                "description": "Embeddings",
                "tags": [],
                "available_for_filter": False,
                "available_for_vector_db": True,
                "type": "list",
            },
        }

        result = propagator.propagate_features(
            node_id="vectordb-node",
            operator_short_name=OperatorConstants.Operators.VECTORDB,
            operator_config={},
            input_features=input_features,
            global_config={},
            parent_results=[],
        )

        output = result.get_output_features(node_id="vectordb-node")
        assert len(output) == 0  # VectorDB produces no output features


class TestExtractOperatorSpecialCase:
    """Tests for Extract operator special case handling."""

    @pytest.fixture
    def propagator(self):
        """Create FeaturePropagator instance."""
        with patch.object(FeaturePropagator, "__init__", lambda x: None):
            prop = FeaturePropagator()
            prop.operator_metadata = Mock()
            # Extract operator defines entities and document_type features
            prop.operator_metadata.get_features = Mock(
                return_value={
                    "text": {
                        "description": "Extracted text",
                        "tags": [],
                        "available_for_filter": False,
                        "available_for_vector_db": False,
                        "type": "string",
                    },
                    "entities": {
                        "description": "Entities",
                        "tags": ["entity"],
                        "available_for_filter": False,
                        "available_for_vector_db": False,
                        "type": "list",
                    },
                    OperatorConstants.Columns.DOCUMENT_TYPE: {
                        "description": "Doc type",
                        "tags": ["entity"],
                        "available_for_filter": True,
                        "available_for_vector_db": False,
                        "type": "string",
                    },
                }
            )
            return prop

    def test_extract_with_entity_mode_none_removes_entity_features(self, propagator):
        """Test that entity_extraction_mode=none removes entity features."""
        input_features = {
            "id": {
                "description": "ID",
                "tags": [],
                "available_for_filter": True,
                "available_for_vector_db": False,
                "type": "string",
            },
            "content": {
                "description": "Content",
                "tags": [],
                "available_for_filter": False,
                "available_for_vector_db": False,
                "type": "string",
            },
        }

        result = propagator.propagate_features(
            node_id="extract-node",
            operator_short_name=OperatorConstants.Operators.EXTRACT_OPERATOR,
            operator_config={OperatorConstants.Config.PROVIDER: OperatorConstants.ExtractionModes.ENTITY_MODE_NONE},
            input_features=input_features,
            global_config={},
            parent_results=[],
        )

        assert "entities" not in result.feature_metadata
        assert OperatorConstants.Columns.DOCUMENT_TYPE not in result.feature_metadata
        assert "text" in result.feature_metadata  # Text feature should still be present

    def test_extract_with_entity_mode_ollama_adds_entity_features(self, propagator):
        """Test that entity_extraction_mode=ollama adds entity features."""
        input_features = {
            "id": {
                "description": "ID",
                "tags": [],
                "available_for_filter": True,
                "available_for_vector_db": False,
                "type": "string",
            },
            "content": {
                "description": "Content",
                "tags": [],
                "available_for_filter": False,
                "available_for_vector_db": False,
                "type": "string",
            },
        }

        result = propagator.propagate_features(
            node_id="extract-node",
            operator_short_name=OperatorConstants.Operators.EXTRACT_OPERATOR,
            operator_config={OperatorConstants.Config.PROVIDER: "litellm"},
            input_features=input_features,
            global_config={},
            parent_results=[],
        )

        assert "entities" in result.feature_metadata
        assert OperatorConstants.Columns.DOCUMENT_TYPE in result.feature_metadata


class TestSQLFilterSpecialCase:
    """Tests for SQLFilter operator special case handling."""

    @pytest.fixture
    def propagator(self):
        """Create FeaturePropagator instance."""
        with patch.object(FeaturePropagator, "__init__", lambda x: None):
            prop = FeaturePropagator()
            prop.operator_metadata = Mock()
            prop.operator_metadata.get_features = Mock(return_value={})
            return prop

    def test_sql_filter_with_select_star_keeps_all_features(self, propagator):
        """Test that SELECT * keeps all features."""
        input_features = {
            "id": {
                "description": "ID",
                "tags": ["mandatory"],
                "available_for_filter": True,
                "available_for_vector_db": False,
                "type": "string",
            },
            "content": {
                "description": "Content",
                "tags": [],
                "available_for_filter": False,
                "available_for_vector_db": False,
                "type": "string",
            },
            "metadata": {
                "description": "Metadata",
                "tags": [],
                "available_for_filter": True,
                "available_for_vector_db": False,
                "type": "string",
            },
        }

        result = propagator.propagate_features(
            node_id="filter-node",
            operator_short_name=OperatorConstants.Operators.SQL_FILTER,
            operator_config={"sql_query": "SELECT * FROM table WHERE condition"},
            input_features=input_features,
            global_config={},
            parent_results=[],
        )

        assert "id" in result.feature_metadata
        assert "content" in result.feature_metadata
        assert "metadata" in result.feature_metadata

    def test_sql_filter_with_specific_columns_removes_others(self, propagator):
        """Test that SELECT specific columns removes non-selected features."""
        input_features = {
            "id": {
                "description": "ID",
                "tags": ["mandatory"],
                "available_for_filter": True,
                "available_for_vector_db": False,
                "type": "string",
            },
            "content": {
                "description": "Content",
                "tags": [],
                "available_for_filter": False,
                "available_for_vector_db": False,
                "type": "string",
            },
            "metadata": {
                "description": "Metadata",
                "tags": [],
                "available_for_filter": True,
                "available_for_vector_db": False,
                "type": "string",
            },
        }

        result = propagator.propagate_features(
            node_id="filter-node",
            operator_short_name=OperatorConstants.Operators.SQL_FILTER,
            operator_config={"sql_query": "SELECT id, content FROM table WHERE condition"},
            input_features=input_features,
            global_config={},
            parent_results=[],
        )

        assert "id" in result.feature_metadata
        assert "content" in result.feature_metadata
        assert "metadata" not in result.feature_metadata

    def test_sql_filter_tracks_dropped_features(self, propagator):
        """Test that SQLFilter tracks which features were dropped."""
        input_features = {
            "id": {
                "description": "ID",
                "tags": ["mandatory"],
                "available_for_filter": True,
                "available_for_vector_db": False,
                "type": "string",
            },
            "content": {
                "description": "Content",
                "tags": [],
                "available_for_filter": False,
                "available_for_vector_db": False,
                "type": "string",
            },
            "metadata": {
                "description": "Metadata",
                "tags": [],
                "available_for_filter": True,
                "available_for_vector_db": False,
                "type": "string",
            },
        }

        result = propagator.propagate_features(
            node_id="filter-node",
            operator_short_name=OperatorConstants.Operators.SQL_FILTER,
            operator_config={"sql_query": "SELECT id, content FROM table"},
            input_features=input_features,
            global_config={},
            parent_results=[],
        )

        dropped = result.get_output_features_to_drop(node_id="filter-node")
        assert "metadata" in dropped.get_features_to_drop()

    def test_sql_filter_cannot_drop_mandatory_features(self, propagator):
        """Test that SQLFilter raises error when trying to drop mandatory features."""
        input_features = {
            "id": {
                "description": "ID",
                "tags": ["mandatory"],
                "available_for_filter": True,
                "available_for_vector_db": False,
                "type": "string",
            },
            "content": {
                "description": "Content",
                "tags": ["mandatory"],
                "available_for_filter": False,
                "available_for_vector_db": False,
                "type": "string",
            },
        }

        with pytest.raises(FlowValidationException) as exc_info:
            propagator.propagate_features(
                node_id="filter-node",
                operator_short_name=OperatorConstants.Operators.SQL_FILTER,
                operator_config={"sql_query": "SELECT id FROM table"},  # Drops mandatory 'content'
                input_features=input_features,
                global_config={},
                parent_results=[],
            )

        errors = exc_info.value.errors or []
        assert len(errors) > 0
        assert "mandatory" in str(errors[0]).lower()


class TestMergeOperatorSpecialCase:
    """Tests for Merge operator special case handling."""

    @pytest.fixture
    def propagator(self):
        """Create FeaturePropagator instance."""
        with patch.object(FeaturePropagator, "__init__", lambda x: None):
            prop = FeaturePropagator()
            prop.operator_metadata = Mock()
            prop.operator_metadata.get_features = Mock(return_value={})
            return prop

    def test_merge_rows_combines_all_features(self, propagator):
        """Test that ROWS merge combines all features from all parents."""
        parent1_result = FeaturePropagationResult()
        parent1_result.add_feature(
            feature_name="id",
            node_id="parent1",
            description="ID",
            tags=[],
            available_for_filter=True,
            available_for_vector_db=False,
            type="string",
        )
        parent1_result.add_feature(
            feature_name="content",
            node_id="parent1",
            description="Content",
            tags=[],
            available_for_filter=False,
            available_for_vector_db=False,
            type="string",
        )

        parent2_result = FeaturePropagationResult()
        parent2_result.add_feature(
            feature_name="id",
            node_id="parent2",
            description="ID",
            tags=[],
            available_for_filter=True,
            available_for_vector_db=False,
            type="string",
        )
        parent2_result.add_feature(
            feature_name="metadata",
            node_id="parent2",
            description="Metadata",
            tags=[],
            available_for_filter=True,
            available_for_vector_db=False,
            type="string",
        )

        result = propagator.propagate_features(
            node_id="merge-node",
            operator_short_name=OperatorConstants.Operators.MERGE,
            operator_config={OperatorConstants.Merge.MERGE_TYPE: OperatorConstants.Merge.ROWS},
            input_features={},
            global_config={},
            parent_results=[parent1_result, parent2_result],
        )

        assert "id" in result.feature_metadata
        assert "content" in result.feature_metadata
        assert "metadata" in result.feature_metadata

    def test_merge_columns_inner_join_keeps_common_features(self, propagator):
        """Test that COLUMNS + INNER_JOIN keeps only common features."""
        parent1_result = FeaturePropagationResult()
        parent1_result.add_feature(
            feature_name="id",
            node_id="parent1",
            description="ID",
            tags=[],
            available_for_filter=True,
            available_for_vector_db=False,
            type="string",
        )
        parent1_result.add_feature(
            feature_name="content",
            node_id="parent1",
            description="Content",
            tags=[],
            available_for_filter=False,
            available_for_vector_db=False,
            type="string",
        )
        parent1_result.add_feature(
            feature_name="title",
            node_id="parent1",
            description="Title",
            tags=[],
            available_for_filter=True,
            available_for_vector_db=False,
            type="string",
        )

        parent2_result = FeaturePropagationResult()
        parent2_result.add_feature(
            feature_name="id",
            node_id="parent2",
            description="ID",
            tags=[],
            available_for_filter=True,
            available_for_vector_db=False,
            type="string",
        )
        parent2_result.add_feature(
            feature_name="content",
            node_id="parent2",
            description="Content",
            tags=[],
            available_for_filter=False,
            available_for_vector_db=False,
            type="string",
        )
        parent2_result.add_feature(
            feature_name="author",
            node_id="parent2",
            description="Author",
            tags=[],
            available_for_filter=True,
            available_for_vector_db=False,
            type="string",
        )

        result = propagator.propagate_features(
            node_id="merge-node",
            operator_short_name=OperatorConstants.Operators.MERGE,
            operator_config={
                OperatorConstants.Merge.MERGE_TYPE: OperatorConstants.Merge.COLUMNS,
                OperatorConstants.Merge.COLUMN_OPTION: OperatorConstants.Columns.INNER_JOIN_DUPLICATE_COLUMN,
            },
            input_features={},
            global_config={},
            parent_results=[parent1_result, parent2_result],
        )

        assert "id" in result.feature_metadata
        assert "content" in result.feature_metadata
        assert "title" not in result.feature_metadata  # Not common
        assert "author" not in result.feature_metadata  # Not common

    def test_merge_columns_full_outer_join_disambiguates_duplicates(self, propagator):
        """Test that COLUMNS + FULL_OUTER_JOIN disambiguates duplicate features."""
        parent1_result = FeaturePropagationResult()
        parent1_result.add_feature(
            feature_name="id",
            node_id="parent1",
            description="ID",
            tags=[],
            available_for_filter=True,
            available_for_vector_db=False,
            type="string",
        )
        parent1_result.add_feature(
            feature_name="content",
            node_id="parent1",
            description="Content1",
            tags=[],
            available_for_filter=False,
            available_for_vector_db=False,
            type="string",
        )

        parent2_result = FeaturePropagationResult()
        parent2_result.add_feature(
            feature_name="id",
            node_id="parent2",
            description="ID",
            tags=[],
            available_for_filter=True,
            available_for_vector_db=False,
            type="string",
        )
        parent2_result.add_feature(
            feature_name="content",
            node_id="parent2",
            description="Content2",
            tags=[],
            available_for_filter=False,
            available_for_vector_db=False,
            type="string",
        )

        result = propagator.propagate_features(
            node_id="merge-node",
            operator_short_name=OperatorConstants.Operators.MERGE,
            operator_config={
                OperatorConstants.Merge.MERGE_TYPE: OperatorConstants.Merge.COLUMNS,
                OperatorConstants.Merge.COLUMN_OPTION: OperatorConstants.Merge.FULL_OUTER_JOIN,
            },
            input_features={},
            global_config={},
            parent_results=[parent1_result, parent2_result],
        )

        assert "id" in result.feature_metadata  # Join key not duplicated
        assert "content_0" in result.feature_metadata  # Disambiguated
        assert "content_1" in result.feature_metadata  # Disambiguated
        assert "content" not in result.feature_metadata  # Original removed

    def test_merge_with_features_to_drop_config(self, propagator):
        """Test that Merge operator respects features_to_drop configuration."""
        parent1_result = FeaturePropagationResult()
        parent1_result.add_feature(
            feature_name="id",
            node_id="parent1",
            description="ID",
            tags=[],
            available_for_filter=True,
            available_for_vector_db=False,
            type="string",
        )
        parent1_result.add_feature(
            feature_name="content",
            node_id="parent1",
            description="Content",
            tags=[],
            available_for_filter=False,
            available_for_vector_db=False,
            type="string",
        )
        parent1_result.add_feature(
            feature_name="metadata",
            node_id="parent1",
            description="Metadata",
            tags=[],
            available_for_filter=True,
            available_for_vector_db=False,
            type="string",
        )

        result = propagator.propagate_features(
            node_id="merge-node",
            operator_short_name=OperatorConstants.Operators.MERGE,
            operator_config={
                OperatorConstants.Merge.MERGE_TYPE: OperatorConstants.Merge.ROWS,
                "features_to_drop": ["metadata"],
            },
            input_features={},
            global_config={},
            parent_results=[parent1_result],
        )

        assert "id" in result.feature_metadata
        assert "content" in result.feature_metadata
        assert "metadata" not in result.feature_metadata


class TestGlobalParameterPropagation:
    """Tests for global parameter propagation."""

    @pytest.fixture
    def propagator(self):
        """Create FeaturePropagator instance."""
        with patch.object(FeaturePropagator, "__init__", lambda x: None):
            prop = FeaturePropagator()
            prop.operator_metadata = Mock()
            prop.operator_metadata.get_features = Mock(return_value={})
            return prop

    def test_embeddings_operator_propagates_model_id(self, propagator):
        """Test that Embeddings operator propagates model_id as global parameter."""
        result = propagator.propagate_features(
            node_id="embeddings-node",
            operator_short_name=OperatorConstants.Operators.EMBEDDINGS,
            operator_config={OperatorConstants.Config.MODEL_ID: "nomic-embed-text"},
            input_features={},
            global_config={},
            parent_results=[],
        )

        assert OperatorConstants.Config.EMBEDDINGS_MODEL_ID in result.global_params
        assert result.global_params[OperatorConstants.Config.EMBEDDINGS_MODEL_ID] == "nomic-embed-text"


class TestMergeFeaturesMethod:
    """Tests for merge_features method."""

    @pytest.fixture
    def propagator(self):
        """Create FeaturePropagator instance."""
        with patch.object(FeaturePropagator, "__init__", lambda x: None):
            prop = FeaturePropagator()
            return prop

    def test_merge_features_empty_parents_returns_empty(self, propagator):
        """Test that empty parent_results returns empty dict."""
        result = propagator.merge_features(
            parent_results=[], merge_type=OperatorConstants.Merge.ROWS, column_option=None
        )

        assert result == {}

    def test_merge_features_rows_type(self, propagator):
        """Test ROWS merge type combines all features."""
        parent1 = FeaturePropagationResult()
        parent1.add_feature(
            feature_name="feat1",
            node_id="p1",
            description="F1",
            tags=[],
            available_for_filter=True,
            available_for_vector_db=False,
            type="string",
        )

        parent2 = FeaturePropagationResult()
        parent2.add_feature(
            feature_name="feat2",
            node_id="p2",
            description="F2",
            tags=[],
            available_for_filter=True,
            available_for_vector_db=False,
            type="string",
        )

        result = propagator.merge_features(
            parent_results=[parent1, parent2], merge_type=OperatorConstants.Merge.ROWS, column_option=None
        )

        assert "feat1" in result
        assert "feat2" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
