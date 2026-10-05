"""
Unit tests for DAG utility functions.

Tests cover:
- DAG node extraction from runtime, authoring, and Elyra flow formats
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from docpipe.utils.orchestration.dag_utils import extract_dag_nodes


class TestExtractDagNodes:
    """Test DAG node extraction from flow definitions."""

    def test_runtime_format_returns_dag_list(self):
        """Runtime format with 'dag' key returns the list directly."""
        dag_nodes = [
            {"id": "uuid-1", "name": "Ingest", "operator": "IngestLocalOperator"},
            {"id": "uuid-2", "name": "Extract", "operator": "ExtractOperator"},
        ]
        flow_definition = {"dag": dag_nodes, "name": "test-flow"}

        result = extract_dag_nodes(flow_definition=flow_definition)

        assert result == dag_nodes

    def test_runtime_format_empty_dag(self):
        """Runtime format with empty dag list returns empty list."""
        flow_definition: dict[str, list] = {"dag": []}

        result = extract_dag_nodes(flow_definition=flow_definition)

        assert result == []

    def test_none_flow_definition_returns_empty(self):
        """None flow definition returns empty list."""
        result = extract_dag_nodes(flow_definition=None)

        assert result == []

    def test_unknown_format_returns_empty(self):
        """Flow definition with neither 'dag' nor 'flow' key returns empty list."""
        flow_definition: dict[str, list] = {"something_else": []}

        result = extract_dag_nodes(flow_definition=flow_definition)

        assert result == []

    def test_authoring_format_without_node_stats_returns_empty(self):
        """Authoring format without node_stats cannot reconstruct — returns empty."""
        flow_definition = {
            "flow": [
                {"name": "Ingest", "type": "IngestLocalOperator", "depends_on": []},
                {"name": "Extract", "type": "ExtractOperator", "depends_on": ["Ingest"]},
            ]
        }

        result = extract_dag_nodes(flow_definition=flow_definition, node_stats=None)

        assert result == []

    def test_authoring_format_reconstructs_dag_nodes(self):
        """Authoring format + node_stats reconstructs dag nodes with real UUIDs."""
        flow_definition = {
            "flow": [
                {"name": "Ingest", "type": "IngestLocalOperator", "depends_on": []},
                {"name": "Extract", "type": "ExtractOperator", "depends_on": ["Ingest"]},
            ]
        }

        ingest_uuid = "aaaa-1111"
        extract_uuid = "bbbb-2222"

        node_stats = {
            ingest_uuid: SimpleNamespace(name="Ingest"),
            extract_uuid: SimpleNamespace(name="Extract"),
        }

        result = extract_dag_nodes(flow_definition=flow_definition, node_stats=node_stats)

        assert len(result) == 2

        by_id = {n["id"]: n for n in result}

        # Ingest node
        assert ingest_uuid in by_id
        ingest_node = by_id[ingest_uuid]
        assert ingest_node["name"] == "Ingest"
        assert ingest_node["operator"] == "IngestLocalOperator"
        assert ingest_node["input_edges"] == []
        # Ingest has Extract as output
        assert len(ingest_node["output_edges"]) == 1
        assert ingest_node["output_edges"][0]["node_id_ref"] == extract_uuid

        # Extract node
        assert extract_uuid in by_id
        extract_node = by_id[extract_uuid]
        assert extract_node["name"] == "Extract"
        assert extract_node["operator"] == "ExtractOperator"
        # Extract depends on Ingest
        assert len(extract_node["input_edges"]) == 1
        assert extract_node["input_edges"][0]["node_id_ref"] == ingest_uuid
        assert extract_node["output_edges"] == []

    def test_authoring_format_node_stats_as_dicts(self):
        """Handles node_stats where values are dicts (not objects with .name)."""
        flow_definition = {
            "flow": [
                {"name": "Ingest", "type": "IngestLocalOperator", "depends_on": []},
            ]
        }

        ingest_uuid = "cccc-3333"
        node_stats = {ingest_uuid: {"name": "Ingest", "node_status": "COMPLETED"}}

        result = extract_dag_nodes(flow_definition=flow_definition, node_stats=node_stats)

        assert len(result) == 1
        assert result[0]["id"] == ingest_uuid
        assert result[0]["name"] == "Ingest"

    def test_authoring_format_missing_depends_on_treated_as_empty(self):
        """Authoring nodes without depends_on key default to no dependencies."""
        flow_definition = {
            "flow": [
                {"name": "Ingest", "type": "IngestLocalOperator"},  # no depends_on key
            ]
        }
        node_stats = {"uuid-x": SimpleNamespace(name="Ingest")}

        result = extract_dag_nodes(flow_definition=flow_definition, node_stats=node_stats)

        assert len(result) == 1
        assert result[0]["input_edges"] == []
        assert result[0]["output_edges"] == []

    def test_branching_dot_notation_depends_on_resolved_correctly(self):
        """depends_on entries with 'node.branch' dot notation are resolved to the plain node name.

        Without the fix, embeddings_model_1 would have input_edges=[] because
        'branch_for_embeddings.embedding_branch_1' is not a known node name, causing it
        to be misidentified as the ingest node and breaking processing time calculation.
        """
        branch_uuid = "uuid-branch"
        embed_uuid = "uuid-embed"

        flow_definition = {
            "flow": [
                {"name": "branch_for_embeddings", "type": "branching", "depends_on": []},
                {
                    "name": "embeddings_model_1",
                    "type": "embeddings",
                    # Dot-notation: refers to the branch output, not a separate node
                    "depends_on": ["branch_for_embeddings.embedding_branch_1"],
                },
            ]
        }
        node_stats = {
            branch_uuid: SimpleNamespace(name="branch_for_embeddings"),
            embed_uuid: SimpleNamespace(name="embeddings_model_1"),
        }

        result = extract_dag_nodes(flow_definition=flow_definition, node_stats=node_stats)

        by_name = {n["name"]: n for n in result}

        # branch_for_embeddings has no input edges (it IS the ingest-side node here)
        assert by_name["branch_for_embeddings"]["input_edges"] == []
        # embeddings_model_1 must have branch_for_embeddings as its input edge
        assert len(by_name["embeddings_model_1"]["input_edges"]) == 1
        assert by_name["embeddings_model_1"]["input_edges"][0]["node_id_ref"] == branch_uuid
        # branch_for_embeddings must have embeddings_model_1 as its output edge
        assert len(by_name["branch_for_embeddings"]["output_edges"]) == 1
        assert by_name["branch_for_embeddings"]["output_edges"][0]["node_id_ref"] == embed_uuid

    def test_elyra_format_returns_converted_dag(self):
        """Elyra pipeline snapshot is converted and its dag list returned."""
        elyra_dag = [
            {
                "id": "node-uuid-1",
                "name": "ingest",
                "operator": "ingest_source",
                "input_edges": [],
                "output_edges": [{"node_id_ref": "node-uuid-2"}],
            },
            {
                "id": "node-uuid-2",
                "name": "extract",
                "operator": "extract_operator",
                "input_edges": [{"node_id_ref": "node-uuid-1"}],
                "output_edges": [],
            },
        ]
        elyra_flow_definition = {
            "doc_type": "pipeline",
            "pipelines": [{"id": "pipe-1", "nodes": []}],
        }

        mock_converter = MagicMock()
        mock_converter.transform_elyra_to_internal.return_value = {"flow": {"dag": elyra_dag, "name": "test-flow"}}

        with patch(
            "docpipe.utils.orchestration.dag_utils.ElyraConverter",
            return_value=mock_converter,
        ):
            result = extract_dag_nodes(flow_definition=elyra_flow_definition)

        assert result == elyra_dag
        mock_converter.transform_elyra_to_internal.assert_called_once_with(
            elyra_json=elyra_flow_definition, flow_id="report-snapshot"
        )

    def test_elyra_format_conversion_failure_falls_through_to_warning(self):
        """If Elyra conversion raises, returns empty list (no crash)."""
        elyra_flow_definition = {
            "doc_type": "pipeline",
            "pipelines": [{"id": "pipe-1"}],
        }

        mock_converter = MagicMock()
        mock_converter.transform_elyra_to_internal.side_effect = RuntimeError("bad pipeline")

        with patch(
            "docpipe.utils.orchestration.dag_utils.ElyraConverter",
            return_value=mock_converter,
        ):
            result = extract_dag_nodes(flow_definition=elyra_flow_definition)

        assert result == []

    def test_elyra_format_not_triggered_without_pipelines_key(self):
        """doc_type=pipeline without 'pipelines' key does not attempt Elyra conversion."""
        flow_definition = {"doc_type": "pipeline"}  # missing 'pipelines'

        with patch("docpipe.utils.orchestration.dag_utils.ElyraConverter") as mock_cls:
            result = extract_dag_nodes(flow_definition=flow_definition)

        mock_cls.assert_not_called()
        assert result == []
