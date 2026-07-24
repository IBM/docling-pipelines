"""
Tests for Elyra pipeline format converter.

Tests the conversion from Elyra visual pipeline format to internal DAG format.
"""

import networkx as nx
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
                            "op": "ingest_local",
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
                            "op": "ingest_local",
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
        assert dag[0]["operator"] == "ingest_local"
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
                            "op": "ingest_local",
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
                            "op": "ingest_local",
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
                            "op": "ingest_local",
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


class TestGetPrimaryPipeline:
    @pytest.fixture
    def converter(self):
        return ElyraConverter()

    def test_single_pipeline(self, *, converter):
        elyra_json = {"pipelines": [{"id": "pipeline-1", "nodes": []}]}

        result = converter._get_primary_pipeline(elyra_json=elyra_json)

        assert result == {"id": "pipeline-1", "nodes": []}

    def test_multiple_pipelines_first_primary(self, *, converter):
        elyra_json = {
            "primary_pipeline": "pipeline-2",
            "pipelines": [
                {"id": "pipeline-1", "nodes": []},
                {"id": "pipeline-2", "nodes": [{"id": "node-1"}]},
            ],
        }

        result = converter._get_primary_pipeline(elyra_json=elyra_json)

        assert result == {"id": "pipeline-2", "nodes": [{"id": "node-1"}]}

    def test_missing_primary_pipeline(self, *, converter):
        elyra_json = {
            "primary_pipeline": "missing-pipeline",
            "pipelines": [
                {"id": "pipeline-1", "nodes": []},
                {"id": "pipeline-2", "nodes": [{"id": "node-1"}]},
            ],
        }

        result = converter._get_primary_pipeline(elyra_json=elyra_json)

        assert result == {"id": "pipeline-1", "nodes": []}

    def test_empty_pipelines(self, *, converter):
        result = converter._get_primary_pipeline(elyra_json={"pipelines": []})

        assert result is None


class TestGetNodePosition:
    @pytest.fixture
    def converter(self):
        return ElyraConverter()

    def test_position_with_x_pos_y_pos(self, *, converter):
        node = {"app_data": {"ui_data": {"x_pos": 250, "y_pos": 400, "x": 1, "y": 2}}}

        result = converter._get_node_position(node=node)

        assert result == (250, 400)

    def test_position_with_x_y(self, *, converter):
        node = {"app_data": {"ui_data": {"x": 125, "y": 275}}}

        result = converter._get_node_position(node=node)

        assert result == (125, 275)

    def test_missing_position_data(self, *, converter):
        result = converter._get_node_position(node={"app_data": {"ui_data": {}}})

        assert result == (100, 100)

    def test_invalid_position_format(self, *, converter):
        node = {"app_data": {"ui_data": {"x_pos": "invalid", "y_pos": "200"}}}

        with pytest.raises(ValueError):
            converter._get_node_position(node=node)


class TestTransformBranchingConfig:
    @pytest.fixture
    def converter(self):
        return ElyraConverter()

    def test_valid_branching_config(self, *, converter):
        config = {
            "link_conditions": [
                {
                    "link_id": "link-1",
                    "link_name": "pdf_branch",
                    "condition": {
                        "criteria_list": [{"column": "type", "operator": "==", "value": "pdf"}],
                        "criteria_json": {
                            "logical_operator": "AND",
                            "criteria_list": [{"column": "type", "operator": "==", "value": "pdf"}],
                        },
                        "logical_operator": "AND",
                    },
                }
            ],
            "preserve": True,
        }

        result = converter._transform_branching_config(config=config)

        assert "link_conditions" not in result
        assert result["preserve"] is True
        assert result["branches"] == [
            {
                "criteria_list": [{"column": "type", "operator": "==", "value": "pdf"}],
                "criteria_json": {
                    "logical_operator": "AND",
                    "criteria_list": [{"column": "type", "operator": "==", "value": "pdf"}],
                },
                "logical_operator": "AND",
                "link_id": "link-1",
                "link_name": "pdf_branch",
            }
        ]

    def test_missing_criteria_json(self, *, converter):
        config = {
            "link_conditions": [
                {
                    "link_id": "link-1",
                    "link_name": "fallback_branch",
                    "condition": {
                        "criteria_list": [{"column": "status", "operator": "==", "value": "new"}],
                        "logical_operator": "OR",
                    },
                }
            ]
        }

        result = converter._transform_branching_config(config=config)

        assert result["branches"][0]["criteria_json"] == {}
        assert result["branches"][0]["logical_operator"] == "OR"

    def test_malformed_criteria_json(self, *, converter):
        config = {
            "link_conditions": [
                {
                    "link_id": "link-1",
                    "link_name": "bad_branch",
                    "condition": {
                        "criteria_list": [],
                        "criteria_json": ["not", "a", "dict"],
                        "logical_operator": "AND",
                    },
                }
            ]
        }

        result = converter._transform_branching_config(config=config)

        assert result["branches"][0]["criteria_json"] == {
            "logical_operator": "AND",
            "criteria_list": [],
        }

    def test_empty_branching_config(self, *, converter):
        result = converter._transform_branching_config(config={})

        assert result == {"branches": []}

    def test_multiple_criteria(self, *, converter):
        config = {
            "link_conditions": [
                {
                    "link_id": "link-1",
                    "link_name": "branch-a",
                    "condition": {
                        "criteria_list": [{"column": "type", "operator": "==", "value": "pdf"}],
                        "criteria_json": {
                            "logical_operator": "AND",
                            "criteria_list": [{"column": "type", "operator": "==", "value": "pdf"}],
                        },
                        "logical_operator": "AND",
                    },
                },
                {
                    "link_id": "link-2",
                    "link_name": "branch-b",
                    "condition": {
                        "criteria_list": [
                            {"column": "lang", "operator": "==", "value": "en"},
                            {"column": "pages", "operator": ">", "value": 10},
                        ],
                        "criteria_json": {
                            "logical_operator": "OR",
                            "criteria_list": [
                                {"column": "lang", "operator": "==", "value": "en"},
                                {"column": "pages", "operator": ">", "value": 10},
                            ],
                        },
                        "logical_operator": "OR",
                    },
                },
            ]
        }

        result = converter._transform_branching_config(config=config)

        assert len(result["branches"]) == 2
        assert result["branches"][1]["link_name"] == "branch-b"
        assert len(result["branches"][1]["criteria_list"]) == 2
        assert result["branches"][1]["criteria_json"]["logical_operator"] == "OR"


class TestValidateDag:
    @pytest.fixture
    def converter(self):
        return ElyraConverter()

    def test_valid_dag(self, *, converter):
        graph = nx.DiGraph()
        graph.add_edge("node-1", "node-2")

        converter._validate_dag(graph=graph, first_nodes=["node-1"], node_count=2)

    def test_dag_with_cycle(self, *, converter):
        graph = nx.DiGraph()
        graph.add_edge("node-1", "node-2")
        graph.add_edge("node-2", "node-1")

        with pytest.raises(FlowValidationException) as exc_info:
            converter._validate_dag(graph=graph, first_nodes=["node-1"], node_count=2)

        assert "cycle" in str(exc_info.value.errors).lower() or "loop" in str(exc_info.value.errors).lower()

    def test_exceeds_node_limit(self, *, converter):
        graph = nx.DiGraph()
        graph.add_nodes_from([f"node-{index}" for index in range(101)])

        with pytest.raises(FlowValidationException) as exc_info:
            converter._validate_dag(graph=graph, first_nodes=["node-1"], node_count=101)

        assert "more than 100 nodes" in str(exc_info.value.errors).lower()

    def test_disconnected_nodes(self, *, converter):
        graph = nx.DiGraph()
        graph.add_edge("node-1", "node-2")
        graph.add_node("node-3")

        converter._validate_dag(graph=graph, first_nodes=["node-1", "node-3"], node_count=3)

    def test_empty_dag(self, *, converter):
        graph = nx.DiGraph()

        with pytest.raises(FlowValidationException) as exc_info:
            converter._validate_dag(graph=graph, first_nodes=[], node_count=0)

        assert "no starting node found" in str(exc_info.value.errors).lower()


class TestTransformInternalToElyra:
    """Test suite for internal DAG to Elyra conversion."""

    @pytest.fixture
    def converter(self):
        return ElyraConverter()

    @pytest.fixture
    def simple_internal_dag(self):
        """Simple internal DAG with 3 nodes."""
        return {
            "flow": {
                "id": "test-flow-1",
                "name": "Test Pipeline",
                "description": "Test description",
                "global_config": {"batch_size": 100},
                "dag": [
                    {
                        "id": "node-1",
                        "name": "Ingest",
                        "operator": "ingest_local",
                        "config": {"folder_path": "/data"},
                        "input_edges": [],
                        "output_edges": [{"node_id_ref": "node-2"}],
                    },
                    {
                        "id": "node-2",
                        "name": "Extract",
                        "operator": "extract_operator",
                        "config": {"mode": "text"},
                        "input_edges": [{"node_id_ref": "node-1"}],
                        "output_edges": [{"node_id_ref": "node-3"}],
                    },
                    {
                        "id": "node-3",
                        "name": "Chunk",
                        "operator": "chunker",
                        "config": {"chunk_size": 512},
                        "input_edges": [{"node_id_ref": "node-2"}],
                        "output_edges": [],
                    },
                ],
            }
        }

    @pytest.fixture
    def branching_internal_dag(self):
        """Internal DAG with branching operator."""
        return {
            "flow": {
                "id": "branch-flow",
                "name": "Branching Pipeline",
                "description": "Branch by type",
                "global_config": {},
                "dag": [
                    {
                        "id": "node-1",
                        "name": "Ingest",
                        "operator": "ingest_local",
                        "config": {},
                        "input_edges": [],
                        "output_edges": [{"node_id_ref": "node-2"}],
                    },
                    {
                        "id": "node-2",
                        "name": "Branch",
                        "operator": "branching",
                        "config": {
                            "branches": [
                                {
                                    "link_id": "link-1",
                                    "link_name": "pdf_branch",
                                    "criteria_json": {
                                        "logical_operator": "AND",
                                        "criteria_list": [{"column": "type", "operator": "==", "value": "pdf"}],
                                    },
                                },
                                {
                                    "link_id": "link-2",
                                    "link_name": "docx_branch",
                                    "criteria_json": {
                                        "logical_operator": "AND",
                                        "criteria_list": [{"column": "type", "operator": "==", "value": "docx"}],
                                    },
                                },
                            ]
                        },
                        "input_edges": [{"node_id_ref": "node-1"}],
                        "output_edges": [{"node_id_ref": "node-3"}, {"node_id_ref": "node-4"}],
                    },
                    {
                        "id": "node-3",
                        "name": "PDF Extract",
                        "operator": "extract_operator",
                        "config": {},
                        "link_id": "link-1",
                        "link_name": "pdf_branch",
                        "input_edges": [{"node_id_ref": "node-2", "link_name": "pdf_branch"}],
                        "output_edges": [],
                    },
                    {
                        "id": "node-4",
                        "name": "DOCX Extract",
                        "operator": "extract_operator",
                        "config": {},
                        "link_id": "link-2",
                        "link_name": "docx_branch",
                        "input_edges": [{"node_id_ref": "node-2", "link_name": "docx_branch"}],
                        "output_edges": [],
                    },
                ],
            }
        }

    def test_simple_internal_to_elyra(self, *, converter, simple_internal_dag):
        """Test conversion of simple internal DAG to Elyra format."""
        result = converter.transform_internal_to_elyra(internal_json=simple_internal_dag)

        # Verify top-level structure
        assert "pipelines" in result
        assert "id" in result
        assert "primary_pipeline" in result
        assert result["doc_type"] == "pipeline"
        assert result["version"] == "3.0"

        # Verify pipeline
        pipeline = result["pipelines"][0]
        assert "nodes" in pipeline
        assert len(pipeline["nodes"]) == 3

        # Verify flow metadata
        assert pipeline["app_data"]["ds_flow"]["name"] == "Test Pipeline"
        assert pipeline["app_data"]["ds_flow"]["description"] == "Test description"
        assert pipeline["app_data"]["ds_flow"]["global_config"]["batch_size"] == 100

        # Verify nodes have required Elyra fields
        for node in pipeline["nodes"]:
            assert "id" in node
            assert "type" in node
            assert "op" in node
            assert "app_data" in node
            assert "parameters" in node
            assert node["type"] == "execution_node"

    def test_internal_to_elyra_with_branching(self, *, converter, branching_internal_dag):
        """Test conversion with branching operator."""
        result = converter.transform_internal_to_elyra(internal_json=branching_internal_dag)

        pipeline = result["pipelines"][0]
        nodes = pipeline["nodes"]

        # Find branching node
        branching_node = next(n for n in nodes if n["op"] == "branching")
        assert branching_node is not None

        # Verify branching config converted to link_conditions
        params = branching_node["parameters"]
        assert "link_conditions" in params
        assert len(params["link_conditions"]) == 2

        # Verify link_conditions structure
        link_cond = params["link_conditions"][0]
        assert "link_id" in link_cond
        assert "link_name" in link_cond
        assert "condition" in link_cond
        assert "target_node_id" in link_cond
        assert "target_port_id" in link_cond

    def test_internal_to_elyra_node_ports(self, *, converter, simple_internal_dag):
        """Test that nodes have correct input/output ports."""
        result = converter.transform_internal_to_elyra(internal_json=simple_internal_dag)

        nodes = result["pipelines"][0]["nodes"]

        # First node (ingest) - no inputs, has outputs
        ingest_node = nodes[0]
        assert "inputs" not in ingest_node or len(ingest_node.get("inputs", [])) == 0
        assert "outputs" in ingest_node
        assert len(ingest_node["outputs"]) == 1

        # Middle node (extract) - has both
        extract_node = nodes[1]
        assert "inputs" in extract_node
        assert "outputs" in extract_node
        assert len(extract_node["inputs"]) == 1
        assert len(extract_node["outputs"]) == 1

        # Last node (chunker) - has inputs, no outputs
        chunker_node = nodes[2]
        assert "inputs" in chunker_node
        assert "outputs" not in chunker_node or len(chunker_node.get("outputs", [])) == 0

    def test_internal_to_elyra_links(self, *, converter, simple_internal_dag):
        """Test that links are correctly added to input ports."""
        result = converter.transform_internal_to_elyra(internal_json=simple_internal_dag)

        nodes = result["pipelines"][0]["nodes"]

        # Second node should have link to first node
        extract_node = nodes[1]
        input_port = extract_node["inputs"][0]
        assert "links" in input_port
        assert len(input_port["links"]) == 1

        link = input_port["links"][0]
        assert "id" in link
        assert "node_id_ref" in link
        assert "port_id_ref" in link
        assert link["node_id_ref"] == "node-1"

    def test_internal_to_elyra_missing_flow_key(self, *, converter):
        """Test error handling when 'flow' key is missing."""
        invalid_json = {"not_flow": {}}

        with pytest.raises(FlowValidationException) as exc_info:
            converter.transform_internal_to_elyra(internal_json=invalid_json)

        assert "missing 'flow' key" in str(exc_info.value.errors).lower()

    def test_internal_to_elyra_empty_dag(self, *, converter):
        """Test conversion with empty DAG."""
        empty_dag = {
            "flow": {
                "id": "empty",
                "name": "Empty",
                "description": "",
                "global_config": {},
                "dag": [],
            }
        }

        result = converter.transform_internal_to_elyra(internal_json=empty_dag)

        pipeline = result["pipelines"][0]
        assert len(pipeline["nodes"]) == 0

    def test_internal_to_elyra_with_custom_spacing(self, *, converter, simple_internal_dag):
        """Test conversion with custom node spacing."""
        result = converter.transform_internal_to_elyra(
            internal_json=simple_internal_dag, node_spacing_x=300, node_spacing_y=250
        )

        # Verify nodes have positions (exact positions depend on layout algorithm)
        nodes = result["pipelines"][0]["nodes"]
        for node in nodes:
            ui_data = node["app_data"]["ui_data"]
            assert "x_pos" in ui_data
            assert "y_pos" in ui_data
            assert isinstance(ui_data["x_pos"], (int, float))
            assert isinstance(ui_data["y_pos"], (int, float))


class TestConvertDagNodeToElyra:
    """Test _convert_dag_node_to_elyra method."""

    @pytest.fixture
    def converter(self):
        return ElyraConverter()

    def test_convert_simple_node(self, *, converter):
        """Test conversion of simple node."""
        node = {
            "id": "node-1",
            "name": "Test Node",
            "operator": "ingest_local",
            "config": {"folder_path": "/data"},
            "input_edges": [],
            "output_edges": [{"node_id_ref": "node-2"}],
        }

        elyra_node, _ = converter._convert_dag_node_to_elyra(node=node, position=(100, 200))

        assert elyra_node["id"] == "node-1"
        assert elyra_node["type"] == "execution_node"
        assert elyra_node["op"] == "ingest_local"
        assert elyra_node["parameters"]["folder_path"] == "/data"
        assert elyra_node["app_data"]["ui_data"]["x_pos"] == 100
        assert elyra_node["app_data"]["ui_data"]["y_pos"] == 200

    def test_convert_node_with_branching_operator(self, *, converter):
        """Test conversion of branching operator node."""
        node = {
            "id": "branch-1",
            "name": "Branch",
            "operator": "branching",
            "config": {
                "branches": [
                    {
                        "link_id": "link-1",
                        "link_name": "branch_a",
                        "criteria_json": {"logical_operator": "AND", "criteria_list": []},
                    }
                ]
            },
            "input_edges": [{"node_id_ref": "node-1"}],
            "output_edges": [{"node_id_ref": "node-2"}],
        }

        elyra_node, _ = converter._convert_dag_node_to_elyra(node=node, position=(200, 300))

        # Verify branching config converted
        assert "link_conditions" in elyra_node["parameters"]
        assert len(elyra_node["parameters"]["link_conditions"]) == 1

        # Verify unlimited output cardinality for branching
        assert len(elyra_node["outputs"]) == 1
        cardinality = elyra_node["outputs"][0]["app_data"]["ui_data"]["cardinality"]
        assert cardinality["max"] == -1  # Unlimited

    def test_convert_node_with_merge_operator(self, *, converter):
        """Test conversion of merge operator node."""
        node = {
            "id": "merge-1",
            "name": "Merge",
            "operator": "merge",
            "config": {},
            "input_edges": [{"node_id_ref": "node-1"}, {"node_id_ref": "node-2"}],
            "output_edges": [{"node_id_ref": "node-3"}],
        }

        elyra_node, _ = converter._convert_dag_node_to_elyra(node=node, position=(300, 400))

        # Verify unlimited input cardinality for merge
        assert len(elyra_node["inputs"]) == 1
        cardinality = elyra_node["inputs"][0]["app_data"]["ui_data"]["cardinality"]
        assert cardinality["max"] == -1  # Unlimited

    def test_convert_node_no_edges(self, *, converter):
        """Test conversion of node with no edges."""
        node = {
            "id": "isolated",
            "name": "Isolated",
            "operator": "noop",
            "config": {},
            "input_edges": [],
            "output_edges": [],
        }

        elyra_node, _ = converter._convert_dag_node_to_elyra(node=node, position=(0, 0))

        # No inputs or outputs should be added
        assert "inputs" not in elyra_node
        assert "outputs" not in elyra_node


class TestGetOperatorColor:
    """Test _get_operator_color method."""

    @pytest.fixture
    def converter(self):
        converter = ElyraConverter()
        # Mock metadata
        converter.metadata = {
            "ingest_local": {"category": "Ingest"},
            "extract_operator": {"category": "Extract"},
            "chunker": {"category": "Functional"},
            "unknown_op": {"category": "InvalidCategory"},
            "no_category": {},
        }
        return converter

    def test_get_color_for_ingest(self, *, converter):
        """Test color for ingest operator."""
        color = converter._get_operator_color(operator="ingest_local")
        assert color == "#b28600"

    def test_get_color_for_extract(self, *, converter):
        """Test color for extract operator."""
        color = converter._get_operator_color(operator="extract_operator")
        assert color == "#00539a"

    def test_get_color_for_functional(self, *, converter):
        """Test color for functional operator."""
        color = converter._get_operator_color(operator="chunker")
        assert color == "#520408"

    def test_get_color_for_unknown_operator(self, *, converter):
        """Test fallback color for unknown operator."""
        color = converter._get_operator_color(operator="nonexistent")
        assert color == "#000000"

    def test_get_color_for_invalid_category(self, *, converter):
        """Test fallback color for invalid category."""
        color = converter._get_operator_color(operator="unknown_op")
        assert color == "#000000"

    def test_get_color_no_category(self, *, converter):
        """Test fallback color when no category."""
        color = converter._get_operator_color(operator="no_category")
        assert color == "#000000"


class TestGetOperatorDescription:
    """Test _get_operator_description method."""

    @pytest.fixture
    def converter(self):
        converter = ElyraConverter()
        converter.metadata = {
            "ingest_local": {"category": "Ingest"},
            "extract_operator": {"category": "Extract"},
            "unknown_op": {"category": "InvalidCategory"},
        }
        return converter

    def test_get_description_for_ingest(self, *, converter):
        """Test description for ingest operator."""
        desc = converter._get_operator_description(operator="ingest_local")
        assert desc == "Ingest data"

    def test_get_description_for_extract(self, *, converter):
        """Test description for extract operator."""
        desc = converter._get_operator_description(operator="extract_operator")
        assert desc == "Extract data"

    def test_get_description_for_unknown(self, *, converter):
        """Test fallback description."""
        desc = converter._get_operator_description(operator="nonexistent")
        assert desc == "Custom operator"


class TestGetDetailedOperatorDescription:
    """Test _get_detailed_operator_description method."""

    @pytest.fixture
    def converter(self):
        converter = ElyraConverter()
        converter.metadata = {
            "ingest_local": {"description": "Ingest documents from local filesystem"},
            "extract_operator": {"description": "Extract text and entities"},
            "no_desc": {},
        }
        return converter

    def test_get_detailed_description_from_metadata(self, *, converter):
        """Test getting description from metadata."""
        desc = converter._get_detailed_operator_description(operator="ingest_local")
        assert desc == "Ingest documents from local filesystem"

    def test_get_detailed_description_fallback(self, *, converter):
        """Test fallback when no description in metadata."""
        desc = converter._get_detailed_operator_description(operator="no_desc")
        assert desc == "no_desc operator"

    def test_get_detailed_description_unknown_operator(self, *, converter):
        """Test fallback for unknown operator."""
        desc = converter._get_detailed_operator_description(operator="unknown")
        assert desc == "unknown operator"


class TestConvertBranchingToElyra:
    """Test _convert_branching_to_elyra method."""

    @pytest.fixture
    def converter(self):
        return ElyraConverter()

    def test_convert_branching_config(self, *, converter):
        """Test conversion of branching config."""
        config = {
            "branches": [
                {
                    "link_id": "link-1",
                    "link_name": "branch_a",
                    "criteria_json": {
                        "logical_operator": "AND",
                        "criteria_list": [{"column": "type", "operator": "==", "value": "pdf"}],
                    },
                }
            ],
            "preserve": True,
        }
        node = {"id": "branch-1"}

        result = converter._convert_branching_to_elyra(config=config, node=node)

        assert "branches" not in result
        assert "link_conditions" in result
        assert result["preserve"] is True
        assert len(result["link_conditions"]) == 1

        link_cond = result["link_conditions"][0]
        assert link_cond["link_id"] == "link-1"
        assert link_cond["link_name"] == "branch_a"
        assert "condition" in link_cond
        assert link_cond["condition"]["criteria_json"]["logical_operator"] == "AND"

    def test_convert_empty_branches(self, *, converter):
        """Test conversion with no branches."""
        config = {"other_param": "value"}
        node = {"id": "branch-1"}

        result = converter._convert_branching_to_elyra(config=config, node=node)

        assert "link_conditions" not in result
        assert result["other_param"] == "value"

    def test_convert_multiple_branches(self, *, converter):
        """Test conversion with multiple branches."""
        config = {
            "branches": [
                {
                    "link_id": "link-1",
                    "link_name": "branch_a",
                    "criteria_json": {"logical_operator": "AND", "criteria_list": []},
                },
                {
                    "link_id": "link-2",
                    "link_name": "branch_b",
                    "criteria_json": {"logical_operator": "OR", "criteria_list": []},
                },
            ]
        }
        node = {"id": "branch-1"}

        result = converter._convert_branching_to_elyra(config=config, node=node)

        assert len(result["link_conditions"]) == 2
        assert result["link_conditions"][0]["link_id"] == "link-1"
        assert result["link_conditions"][1]["link_id"] == "link-2"
