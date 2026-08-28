"""
Tests for Elyra pipeline format converter.

Tests the conversion from Elyra visual pipeline format to internal DAG format.
"""

import pytest

from docpipe.exceptions.docpipe_exceptions import FlowValidationException
from docpipe.utils.orchestration.elyra_converter import ElyraConverter


class TestElyraConverter:
    """Test suite for ElyraConverter."""

    @pytest.fixture
    def converter(self):
        """Create converter instance."""
        return ElyraConverter()

    @pytest.fixture
    def simple_elyra_pipeline(self):
        """
        Simple Elyra pipeline with 3 nodes: ingest -> extract -> chunker.
        """
        return {
            "pipelines": [
                {
                    "id": "pipeline-1",
                    "nodes": [
                        {
                            "id": "node-1",
                            "op": "ingest_source",
                            "app_data": {
                                "ui_data": {
                                    "label": "Ingest Documents",
                                    "x": 100,
                                    "y": 200,
                                },
                                "ds_flow": {
                                    "name": "Document Processing",
                                    "description": "Process documents",
                                    "global_config": {"batch_size": 100},
                                },
                            },
                            "parameters": {
                                "folder_path": "/data/docs",
                                "file_types": ["pdf", "docx"],
                            },
                            "outputs": [{"id": "port-1"}],
                            "inputs": [],
                        },
                        {
                            "id": "node-2",
                            "op": "extract_operator",
                            "app_data": {
                                "ui_data": {
                                    "label": "Extract Text",
                                    "x": 300,
                                    "y": 200,
                                },
                            },
                            "parameters": {
                                "text_extraction": {"provider": "docling_library"},
                                "entity_extraction": {"provider": "litellm"},
                            },
                            "inputs": [
                                {
                                    "id": "port-2",
                                    "links": [
                                        {
                                            "node_id_ref": "node-1",
                                            "port_id_ref": "port-1",
                                        }
                                    ],
                                }
                            ],
                            "outputs": [{"id": "port-3"}],
                        },
                        {
                            "id": "node-3",
                            "op": "chunker",
                            "app_data": {
                                "ui_data": {"label": "Chunk Text", "x": 500, "y": 200},
                            },
                            "parameters": {
                                "chunk_size": 512,
                                "strategy": "semantic",
                            },
                            "inputs": [
                                {
                                    "id": "port-4",
                                    "links": [
                                        {
                                            "node_id_ref": "node-2",
                                            "port_id_ref": "port-3",
                                        }
                                    ],
                                }
                            ],
                            "outputs": [],
                        },
                    ],
                    "app_data": {
                        "ds_flow": {
                            "name": "Document Processing Pipeline",
                            "description": "Extract and chunk documents",
                            "global_config": {"batch_size": 100},
                        }
                    },
                }
            ]
        }

    @pytest.fixture
    def branching_elyra_pipeline(self):
        """
        Elyra pipeline with branching operator.
        """
        return {
            "pipelines": [
                {
                    "id": "pipeline-1",
                    "nodes": [
                        {
                            "id": "node-1",
                            "op": "ingest_source",
                            "app_data": {
                                "ui_data": {"label": "Ingest", "x": 100, "y": 200},
                                "folder_path": "/data",
                            },
                            "outputs": [{"id": "port-1"}],
                            "inputs": [],
                        },
                        {
                            "id": "node-2",
                            "op": "branching",
                            "app_data": {
                                "ui_data": {
                                    "label": "Branch by Type",
                                    "x": 300,
                                    "y": 200,
                                },
                            },
                            "parameters": {
                                "link_conditions": [
                                    {
                                        "target_node_id": "node-3",
                                        "link_id": "link-1",
                                        "link_name": "pdf_branch",
                                        "condition": {
                                            "criteria_list": [
                                                {
                                                    "column": "type",
                                                    "operator": "==",
                                                    "value": "pdf",
                                                }
                                            ],
                                            "logical_operator": "AND",
                                        },
                                    },
                                    {
                                        "target_node_id": "node-4",
                                        "link_id": "link-2",
                                        "link_name": "docx_branch",
                                        "condition": {
                                            "criteria_list": [
                                                {
                                                    "column": "type",
                                                    "operator": "==",
                                                    "value": "docx",
                                                }
                                            ],
                                            "logical_operator": "AND",
                                        },
                                    },
                                ],
                            },
                            "inputs": [
                                {
                                    "id": "port-2",
                                    "links": [
                                        {
                                            "node_id_ref": "node-1",
                                            "port_id_ref": "port-1",
                                        }
                                    ],
                                }
                            ],
                            "outputs": [{"id": "port-3"}, {"id": "port-4"}],
                        },
                        {
                            "id": "node-3",
                            "op": "extract_operator",
                            "app_data": {
                                "ui_data": {"label": "Extract PDF", "x": 500, "y": 100},
                            },
                            "parameters": {"mode": "pdf"},
                            "inputs": [
                                {
                                    "id": "port-5",
                                    "links": [
                                        {
                                            "node_id_ref": "node-2",
                                            "port_id_ref": "port-3",
                                        }
                                    ],
                                }
                            ],
                            "outputs": [],
                        },
                        {
                            "id": "node-4",
                            "op": "extract_operator",
                            "app_data": {
                                "ui_data": {
                                    "label": "Extract DOCX",
                                    "x": 500,
                                    "y": 300,
                                },
                            },
                            "parameters": {"mode": "docx"},
                            "inputs": [
                                {
                                    "id": "port-6",
                                    "links": [
                                        {
                                            "node_id_ref": "node-2",
                                            "port_id_ref": "port-4",
                                        }
                                    ],
                                }
                            ],
                            "outputs": [],
                        },
                    ],
                    "app_data": {
                        "ds_flow": {
                            "name": "Branching Pipeline",
                            "description": "Branch by document type",
                            "global_config": {},
                        }
                    },
                }
            ]
        }

    def test_simple_pipeline_conversion(self, *, converter, simple_elyra_pipeline):
        """Test conversion of simple linear pipeline."""
        simple_elyra_pipeline["id"] = "test-flow-1"
        result = converter.transform_elyra_to_internal(elyra_json=simple_elyra_pipeline, flow_id="test-flow-1")

        # Verify flow structure
        assert "flow" in result
        flow = result["flow"]
        assert flow["id"] == "test-flow-1"
        assert flow["name"] == "Document Processing Pipeline"
        assert flow["description"] == "Extract and chunk documents"
        assert flow["global_config"]["batch_size"] == 100

        # Verify DAG
        dag = flow["dag"]
        assert len(dag) == 3

        # Verify node order (topologically sorted)
        assert dag[0]["id"] == "node-1"
        assert dag[0]["operator"] == "ingest_source"
        assert dag[0]["name"] == "Ingest Documents"
        assert len(dag[0]["input_edges"]) == 0
        assert len(dag[0]["output_edges"]) == 1

        assert dag[1]["id"] == "node-2"
        assert dag[1]["operator"] == "extract_operator"
        assert len(dag[1]["input_edges"]) == 1
        assert len(dag[1]["output_edges"]) == 1

        assert dag[2]["id"] == "node-3"
        assert dag[2]["operator"] == "chunker"
        assert len(dag[2]["input_edges"]) == 1
        assert len(dag[2]["output_edges"]) == 0

    def test_branching_pipeline_conversion(self, *, converter, branching_elyra_pipeline):
        """Test conversion of pipeline with branching operator."""
        branching_elyra_pipeline["id"] = "test-flow-2"
        result = converter.transform_elyra_to_internal(elyra_json=branching_elyra_pipeline, flow_id="test-flow-2")

        dag = result["flow"]["dag"]
        assert len(dag) == 4

        # Find branching node
        branching_node = next(node for node in dag if node["operator"] == "branching")
        assert branching_node is not None

        # Verify branches configuration
        config = branching_node["config"]
        assert "branches" in config
        assert len(config["branches"]) == 2

        # Verify first branch
        branch1 = config["branches"][0]
        assert branch1["link_id"] == "link-1"
        assert branch1["link_name"] == "pdf_branch"
        assert len(branch1["criteria_list"]) == 1
        assert branch1["criteria_list"][0]["column"] == "type"

        # Verify second branch
        branch2 = config["branches"][1]
        assert branch2["link_id"] == "link-2"
        assert branch2["link_name"] == "docx_branch"

        # Verify branch target nodes have link metadata
        pdf_node = next(node for node in dag if node["id"] == "node-3")
        assert pdf_node["link_id"] == "link-1"
        assert pdf_node["link_name"] == "pdf_branch"

        docx_node = next(node for node in dag if node["id"] == "node-4")
        assert docx_node["link_id"] == "link-2"
        assert docx_node["link_name"] == "docx_branch"

    def test_empty_pipeline(self, *, converter):
        """Test conversion of empty pipeline."""
        elyra_json = {
            "id": "empty-flow",
            "pipelines": [
                {
                    "id": "pipeline-1",
                    "nodes": [],
                    "app_data": {
                        "ds_flow": {
                            "name": "Empty Pipeline",
                            "description": "No nodes",
                            "global_config": {},
                        }
                    },
                }
            ],
        }

        result = converter.transform_elyra_to_internal(elyra_json=elyra_json, flow_id="test-merge-flow")

        assert result["flow"]["dag"] == []
        assert result["flow"]["name"] == "Empty Pipeline"

    def test_cyclic_pipeline_raises_error(self, *, converter):
        """Test that cyclic pipeline raises validation error."""
        cyclic_pipeline = {
            "id": "cyclic-flow",
            "pipelines": [
                {
                    "id": "pipeline-1",
                    "nodes": [
                        {
                            "id": "node-1",
                            "op": "ingest_source",
                            "app_data": {"ui_data": {"label": "Node 1"}},
                            "outputs": [{"id": "port-1"}],
                            "inputs": [
                                {
                                    "id": "port-4",
                                    "links": [
                                        {
                                            "node_id_ref": "node-2",
                                            "port_id_ref": "port-3",
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "id": "node-2",
                            "op": "extract_operator",
                            "app_data": {"ui_data": {"label": "Node 2"}},
                            "outputs": [{"id": "port-3"}],
                            "inputs": [
                                {
                                    "id": "port-2",
                                    "links": [
                                        {
                                            "node_id_ref": "node-1",
                                            "port_id_ref": "port-1",
                                        }
                                    ],
                                }
                            ],
                        },
                    ],
                    "app_data": {
                        "ds_flow": {
                            "name": "Cyclic",
                            "description": "",
                            "global_config": {},
                        }
                    },
                }
            ],
        }

        with pytest.raises(FlowValidationException) as exc_info:
            converter.transform_elyra_to_internal(elyra_json=cyclic_pipeline, flow_id="test-cyclic-flow")

        # Check that error details contain cycle information
        error_details = str(exc_info.value.errors) if hasattr(exc_info.value, "errors") else str(exc_info.value)
        assert "cycle" in error_details.lower() or "loop" in error_details.lower()

    def test_invalid_node_reference_raises_error(self, *, converter):
        """Test that invalid node reference raises validation error."""
        invalid_pipeline = {
            "id": "invalid-flow",
            "pipelines": [
                {
                    "id": "pipeline-1",
                    "nodes": [
                        {
                            "id": "node-1",
                            "op": "ingest_source",
                            "app_data": {"ui_data": {"label": "Node 1"}},
                            "outputs": [{"id": "port-1"}],
                            "inputs": [],
                        },
                        {
                            "id": "node-2",
                            "op": "extract_operator",
                            "app_data": {"ui_data": {"label": "Node 2"}},
                            "outputs": [{"id": "port-3"}],
                            "inputs": [
                                {
                                    "id": "port-2",
                                    "links": [
                                        {
                                            "node_id_ref": "non-existent-node",
                                            "port_id_ref": "port-1",
                                        }
                                    ],
                                }
                            ],
                        },
                    ],
                    "app_data": {
                        "ds_flow": {
                            "name": "Invalid",
                            "description": "",
                            "global_config": {},
                        }
                    },
                }
            ],
        }

        with pytest.raises(FlowValidationException) as exc_info:
            converter.transform_elyra_to_internal(elyra_json=invalid_pipeline, flow_id="test-invalid-flow")

        # Check that error details contain node reference information
        error_details = str(exc_info.value.errors) if hasattr(exc_info.value, "errors") else str(exc_info.value)
        assert "does not exist" in error_details or "non-existent" in error_details.lower()

    def test_missing_pipeline_raises_error(self, *, converter):
        """Test that missing pipeline raises validation error."""
        with pytest.raises(FlowValidationException) as exc_info:
            converter.transform_elyra_to_internal(
                elyra_json={"id": "missing-flow", "pipelines": []}, flow_id="missing-flow"
            )

        # Check that error details contain missing pipeline information
        error_details = str(exc_info.value.errors) if hasattr(exc_info.value, "errors") else str(exc_info.value)
        assert "missing" in error_details.lower() or "primary pipeline" in error_details.lower()

    def test_config_extraction(self, *, converter, simple_elyra_pipeline):
        """Test that node configuration is correctly extracted."""
        simple_elyra_pipeline["id"] = "test-config"
        result = converter.transform_elyra_to_internal(elyra_json=simple_elyra_pipeline, flow_id="test-config")

        dag = result["flow"]["dag"]

        # Check ingest node config
        ingest_node = dag[0]
        assert ingest_node["config"]["folder_path"] == "/data/docs"
        assert ingest_node["config"]["file_types"] == ["pdf", "docx"]
        assert "ui_data" not in ingest_node["config"]

        # Check extract node config
        extract_node = dag[1]
        assert extract_node["config"]["text_extraction"]["provider"] == "docling_library"
        assert extract_node["config"]["entity_extraction"]["provider"] == "litellm"

    def test_topological_sort_order(self, *, converter):
        """Test that nodes are correctly sorted in topological order."""
        # Create pipeline with specific dependency order
        pipeline = {
            "id": "topo-test",
            "pipelines": [
                {
                    "id": "pipeline-1",
                    "nodes": [
                        {
                            "id": "node-3",
                            "op": "chunker",
                            "app_data": {"ui_data": {"label": "Chunker"}},
                            "outputs": [],
                            "inputs": [
                                {
                                    "id": "port-4",
                                    "links": [
                                        {
                                            "node_id_ref": "node-2",
                                            "port_id_ref": "port-3",
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "id": "node-1",
                            "op": "ingest_source",
                            "app_data": {"ui_data": {"label": "Ingest"}},
                            "outputs": [{"id": "port-1"}],
                            "inputs": [],
                        },
                        {
                            "id": "node-2",
                            "op": "extract_operator",
                            "app_data": {"ui_data": {"label": "Extract"}},
                            "outputs": [{"id": "port-3"}],
                            "inputs": [
                                {
                                    "id": "port-2",
                                    "links": [
                                        {
                                            "node_id_ref": "node-1",
                                            "port_id_ref": "port-1",
                                        }
                                    ],
                                }
                            ],
                        },
                    ],
                    "app_data": {
                        "ds_flow": {
                            "name": "Test",
                            "description": "",
                            "global_config": {},
                        }
                    },
                }
            ],
        }

        result = converter.transform_elyra_to_internal(elyra_json=pipeline, flow_id="test-port-cardinality-flow")

        dag = result["flow"]["dag"]
        # Despite nodes being in wrong order in input, output should be topologically sorted
        assert dag[0]["id"] == "node-1"  # Ingest first (no dependencies)
        assert dag[1]["id"] == "node-2"  # Extract second (depends on ingest)
        assert dag[2]["id"] == "node-3"  # Chunker last (depends on extract)

    def test_get_global_config_from_elyra_ds_flow(self, *, converter, simple_elyra_pipeline):
        """Returns global_config from ds_flow when properties is absent."""
        result = converter.get_global_config_from_elyra(elyra_json=simple_elyra_pipeline)
        assert result == {"batch_size": 100}

    def test_get_global_config_from_elyra_properties(self, *, converter):
        """Returns global_config from app_data.properties (newer Elyra format)."""
        elyra_json = {
            "pipelines": [
                {
                    "id": "pipeline-1",
                    "nodes": [],
                    "app_data": {
                        "properties": {"doc_column": "text", "storage": "in-memory"},
                        "ds_flow": {"global_config": {"should_not_use": True}},
                    },
                }
            ]
        }
        result = converter.get_global_config_from_elyra(elyra_json=elyra_json)
        assert result == {"doc_column": "text", "storage": "in-memory"}

    def test_get_global_config_from_elyra_empty_when_absent(self, *, converter):
        """Returns empty dict when global_config is not present in either location."""
        elyra_json = {
            "pipelines": [
                {
                    "id": "pipeline-1",
                    "nodes": [],
                    "app_data": {"ds_flow": {"name": "no-config"}},
                }
            ]
        }
        result = converter.get_global_config_from_elyra(elyra_json=elyra_json)
        assert result == {}

    def test_get_global_config_from_elyra_no_pipeline(self, *, converter):
        """Returns empty dict when there are no pipelines."""
        result = converter.get_global_config_from_elyra(elyra_json={"pipelines": []})
        assert result == {}
