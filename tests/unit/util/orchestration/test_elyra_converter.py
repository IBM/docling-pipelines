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

    def test_force_ingest_stripped_from_ingest_node_config(self, *, converter):
        """force_ingest in ingest node parameters must be stripped — it belongs in global_config only."""
        pipeline = {
            "id": "fi-test",
            "pipelines": [
                {
                    "id": "pipeline-1",
                    "nodes": [
                        {
                            "id": "node-1",
                            "op": "ingest_source",
                            "app_data": {"ui_data": {"label": "Ingest", "x": 0, "y": 0}},
                            "parameters": {
                                "provider": "filesystem",
                                "connection_params": {"paths": ["./docs"]},
                                "force_ingest": False,
                            },
                            "outputs": [{"id": "port-out"}],
                            "inputs": [],
                        }
                    ],
                    "app_data": {
                        "ds_flow": {
                            "name": "Test",
                            "global_config": {"force_ingest": True},
                        }
                    },
                }
            ],
            "primary_pipeline": "pipeline-1",
        }
        result = converter.transform_elyra_to_internal(elyra_json=pipeline, flow_id="fi-test")
        dag = result["flow"]["dag"]
        assert "force_ingest" not in dag[0]["config"], (
            "force_ingest must be stripped from ingest operator config; it belongs in global_config only"
        )
        # Verify other params are preserved
        assert dag[0]["config"]["provider"] == "filesystem"

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


class TestElyraConverterInternalToElyra:
    """Tests for the internal→Elyra reverse conversion direction."""

    @pytest.fixture
    def converter(self):
        return ElyraConverter()

    @pytest.fixture
    def simple_internal_flow(self):
        """Minimal internal flow: ingest → extract → chunker."""
        return {
            "flow": {
                "id": "flow-abc",
                "name": "My Pipeline",
                "description": "Test pipeline",
                "global_config": {"doc_column": "content"},
                "dag": [
                    {
                        "id": "n1",
                        "name": "Ingest",
                        "operator": "ingest_source",
                        "config": {"paths": ["/data"]},
                        "input_edges": [],
                        "output_edges": [{"node_id_ref": "n2"}],
                    },
                    {
                        "id": "n2",
                        "name": "Extract",
                        "operator": "extract_operator",
                        "config": {},
                        "input_edges": [{"node_id_ref": "n1", "link_name": None}],
                        "output_edges": [{"node_id_ref": "n3"}],
                    },
                    {
                        "id": "n3",
                        "name": "Chunk",
                        "operator": "chunker",
                        "config": {"chunk_size": 512},
                        "input_edges": [{"node_id_ref": "n2", "link_name": None}],
                        "output_edges": [],
                    },
                ],
            }
        }

    @pytest.fixture
    def branching_internal_flow(self):
        """Internal flow: ingest → branching → [extract_a, extract_b] → merge → vectordb."""
        return {
            "flow": {
                "id": "flow-branch",
                "name": "Branch Flow",
                "description": "",
                "global_config": {},
                "dag": [
                    {
                        "id": "n1",
                        "name": "Ingest",
                        "operator": "ingest_source",
                        "config": {},
                        "input_edges": [],
                        "output_edges": [{"node_id_ref": "n2"}],
                    },
                    {
                        "id": "n2",
                        "name": "Branch",
                        "operator": "branching",
                        "config": {
                            "branches": [
                                {
                                    "link_id": "link-1",
                                    "link_name": "pdf_branch",
                                    "criteria_list": [],
                                    "criteria_json": {"logical_operator": "AND", "criteria_list": []},
                                    "logical_operator": "AND",
                                },
                                {
                                    "link_id": "link-2",
                                    "link_name": "docx_branch",
                                    "criteria_list": [],
                                    "criteria_json": {"logical_operator": "AND", "criteria_list": []},
                                    "logical_operator": "AND",
                                },
                            ]
                        },
                        "input_edges": [{"node_id_ref": "n1", "link_name": None}],
                        "output_edges": [{"node_id_ref": "n3"}, {"node_id_ref": "n4"}],
                    },
                    {
                        "id": "n3",
                        "name": "Extract A",
                        "operator": "extract_operator",
                        "config": {},
                        "input_edges": [{"node_id_ref": "n2", "link_name": "pdf_branch"}],
                        "output_edges": [{"node_id_ref": "n5"}],
                        "link_id": "link-1",
                        "link_name": "pdf_branch",
                    },
                    {
                        "id": "n4",
                        "name": "Extract B",
                        "operator": "extract_operator",
                        "config": {},
                        "input_edges": [{"node_id_ref": "n2", "link_name": "docx_branch"}],
                        "output_edges": [{"node_id_ref": "n5"}],
                        "link_id": "link-2",
                        "link_name": "docx_branch",
                    },
                    {
                        "id": "n5",
                        "name": "Merge",
                        "operator": "merge",
                        "config": {},
                        "input_edges": [
                            {"node_id_ref": "n3", "link_name": None},
                            {"node_id_ref": "n4", "link_name": None},
                        ],
                        "output_edges": [],
                    },
                ],
            }
        }

    # ------------------------------------------------------------------ #
    # transform_internal_to_elyra — top-level structure                   #
    # ------------------------------------------------------------------ #

    def test_returns_valid_elyra_structure(self, *, converter, simple_internal_flow):
        """Output has doc_type, primary_pipeline, and exactly one pipeline."""
        result = converter.transform_internal_to_elyra(internal_json=simple_internal_flow)

        assert result["doc_type"] == "pipeline"
        assert result["version"] == "3.0"
        pipeline_id = result["primary_pipeline"]
        pipelines = result["pipelines"]
        assert len(pipelines) == 1
        assert pipelines[0]["id"] == pipeline_id

    def test_flow_metadata_preserved(self, *, converter, simple_internal_flow):
        """flow_name, description, and global_config round-trip through Elyra."""
        result = converter.transform_internal_to_elyra(internal_json=simple_internal_flow)

        ds_flow = result["pipelines"][0]["app_data"]["ds_flow"]
        assert ds_flow["name"] == "My Pipeline"
        assert ds_flow["description"] == "Test pipeline"
        assert ds_flow["global_config"]["doc_column"] == "content"

    def test_node_count_matches(self, *, converter, simple_internal_flow):
        """Each DAG node becomes exactly one Elyra node."""
        result = converter.transform_internal_to_elyra(internal_json=simple_internal_flow)

        nodes = result["pipelines"][0]["nodes"]
        assert len(nodes) == 3

    def test_missing_flow_key_raises(self, *, converter):
        """Internal JSON without 'flow' key raises FlowValidationException."""
        with pytest.raises(FlowValidationException):
            converter.transform_internal_to_elyra(internal_json={})

    def test_node_op_matches_operator(self, *, converter, simple_internal_flow):
        """Each Elyra node's 'op' field equals the internal node's 'operator'."""
        result = converter.transform_internal_to_elyra(internal_json=simple_internal_flow)

        nodes = result["pipelines"][0]["nodes"]
        ops = {n["op"] for n in nodes}
        assert "ingest_source" in ops
        assert "extract_operator" in ops
        assert "chunker" in ops

    def test_middle_node_has_input_and_output_ports(self, *, converter, simple_internal_flow):
        """A node with both input and output edges has both port sections."""
        result = converter.transform_internal_to_elyra(internal_json=simple_internal_flow)

        nodes = {n["op"]: n for n in result["pipelines"][0]["nodes"]}
        extract = nodes["extract_operator"]
        assert "inputs" in extract
        assert len(extract["inputs"]) == 1
        assert "outputs" in extract
        assert len(extract["outputs"]) == 1

    def test_root_node_has_no_inputs(self, *, converter, simple_internal_flow):
        """A node with no input_edges must not have an 'inputs' key."""
        result = converter.transform_internal_to_elyra(internal_json=simple_internal_flow)

        nodes = {n["op"]: n for n in result["pipelines"][0]["nodes"]}
        ingest = nodes["ingest_source"]
        assert "inputs" not in ingest

    def test_leaf_node_has_no_outputs(self, *, converter, simple_internal_flow):
        """A node with no output_edges must not have an 'outputs' key."""
        result = converter.transform_internal_to_elyra(internal_json=simple_internal_flow)

        nodes = {n["op"]: n for n in result["pipelines"][0]["nodes"]}
        chunker = nodes["chunker"]
        assert "outputs" not in chunker

    def test_input_port_links_connect_to_parent(self, *, converter, simple_internal_flow):
        """Input port links on extract node must reference the ingest node."""
        result = converter.transform_internal_to_elyra(internal_json=simple_internal_flow)

        nodes = {n["id"]: n for n in result["pipelines"][0]["nodes"]}
        extract = nodes["n2"]
        links = extract["inputs"][0]["links"]
        assert len(links) == 1
        assert links[0]["node_id_ref"] == "n1"

    def test_node_positions_are_assigned(self, *, converter, simple_internal_flow):
        """Every node gets x_pos and y_pos in its ui_data."""
        result = converter.transform_internal_to_elyra(internal_json=simple_internal_flow)

        for node in result["pipelines"][0]["nodes"]:
            ui = node["app_data"]["ui_data"]
            assert "x_pos" in ui
            assert "y_pos" in ui

    # ------------------------------------------------------------------ #
    # branching / merge special cases                                      #
    # ------------------------------------------------------------------ #

    def test_branching_node_has_unlimited_output_cardinality(self, *, converter, branching_internal_flow):
        """Branching output port cardinality max must be -1."""
        result = converter.transform_internal_to_elyra(internal_json=branching_internal_flow)

        nodes = {n["op"]: n for n in result["pipelines"][0]["nodes"]}
        branch = nodes["branching"]
        assert branch["outputs"][0]["app_data"]["ui_data"]["cardinality"]["max"] == -1

    def test_merge_node_has_unlimited_input_cardinality(self, *, converter, branching_internal_flow):
        """Merge input port cardinality max must be -1."""
        result = converter.transform_internal_to_elyra(internal_json=branching_internal_flow)

        nodes = {n["op"]: n for n in result["pipelines"][0]["nodes"]}
        merge = nodes["merge"]
        assert merge["inputs"][0]["app_data"]["ui_data"]["cardinality"]["max"] == -1

    def test_branching_config_converted_to_link_conditions(self, *, converter, branching_internal_flow):
        """Branching node parameters must have link_conditions, not branches."""
        result = converter.transform_internal_to_elyra(internal_json=branching_internal_flow)

        nodes = {n["op"]: n for n in result["pipelines"][0]["nodes"]}
        branch = nodes["branching"]
        params = branch["parameters"]
        assert "link_conditions" in params
        assert "branches" not in params
        assert len(params["link_conditions"]) == 2

    def test_branching_targets_have_target_node_id(self, *, converter, branching_internal_flow):
        """link_conditions for branching nodes must have target_node_id populated."""
        result = converter.transform_internal_to_elyra(internal_json=branching_internal_flow)

        nodes = {n["op"]: n for n in result["pipelines"][0]["nodes"]}
        branch = nodes["branching"]
        for lc in branch["parameters"]["link_conditions"]:
            assert "target_node_id" in lc

    def test_metadata_injection_sets_colors(self, *, converter, simple_internal_flow):
        """Passing explicit metadata causes react_nodes_data.color to be set."""
        metadata = {
            "ingest_source": {"category": "Ingest", "description": "Ingest data"},
            "extract_operator": {"category": "Extract", "description": "Extract text"},
            "chunker": {"category": "Functional", "description": "Split text"},
        }
        result = converter.transform_internal_to_elyra(internal_json=simple_internal_flow, metadata=metadata)

        nodes = {n["op"]: n for n in result["pipelines"][0]["nodes"]}
        color = nodes["ingest_source"]["app_data"]["react_nodes_data"]["color"]
        assert color != "#000000"  # should resolve to the Ingest category color

    # ------------------------------------------------------------------ #
    # Helper methods tested directly                                       #
    # ------------------------------------------------------------------ #

    def test_get_operator_color_unknown_returns_black(self, *, converter):
        """Unknown operator with no metadata returns default black color."""
        converter.metadata = {}
        assert converter._get_operator_color(operator="unknown_op") == "#000000"

    def test_get_operator_color_known_category(self, *, converter):
        """Known category returns the expected color."""
        converter.metadata = {"ingest_source": {"category": "Ingest"}}
        color = converter._get_operator_color(operator="ingest_source")
        assert color == "#b28600"  # CATEGORY_COLORS[OperatorCategory.Ingest]

    def test_get_operator_color_invalid_category_returns_black(self, *, converter):
        """Invalid category string returns black color."""
        converter.metadata = {"some_op": {"category": "NotACategory"}}
        assert converter._get_operator_color(operator="some_op") == "#000000"

    def test_get_operator_description_unknown_returns_custom(self, *, converter):
        """Unknown operator returns 'Custom operator' description."""
        converter.metadata = {}
        assert converter._get_operator_description(operator="unknown_op") == "Custom operator"

    def test_get_operator_description_known_category(self, *, converter):
        """Known category returns description from CATEGORY_DESCRIPTIONS."""
        converter.metadata = {"vectordb": {"category": "VectorDB"}}
        desc = converter._get_operator_description(operator="vectordb")
        assert desc == "Vector DB"

    def test_get_detailed_operator_description_from_metadata(self, *, converter):
        """Returns metadata description when present."""
        converter.metadata = {"chunker": {"description": "Splits text into chunks"}}
        assert converter._get_detailed_operator_description(operator="chunker") == "Splits text into chunks"

    def test_get_detailed_operator_description_fallback(self, *, converter):
        """Falls back to '<operator> operator' when metadata has no description."""
        converter.metadata = {}
        assert converter._get_detailed_operator_description(operator="chunker") == "chunker operator"

    def test_get_node_position_x_pos_y_pos(self, *, converter):
        """Reads x_pos/y_pos keys from ui_data."""
        node = {"app_data": {"ui_data": {"x_pos": 200, "y_pos": 300}}}
        assert converter._get_node_position(node=node) == (200, 300)

    def test_get_node_position_x_y_fallback(self, *, converter):
        """Falls back to x/y when x_pos is absent."""
        node = {"app_data": {"ui_data": {"x": 50, "y": 75}}}
        assert converter._get_node_position(node=node) == (50, 75)

    def test_get_node_position_defaults(self, *, converter):
        """Returns (100, 100) when no position keys are present."""
        node: dict = {"app_data": {"ui_data": {}}}
        assert converter._get_node_position(node=node) == (100, 100)

    def test_convert_branching_to_elyra_empty_branches(self, *, converter):
        """Empty branches array returns config unchanged."""
        config = {"some_key": "val", "branches": []}
        result = converter._convert_branching_to_elyra(config=config, node={})
        assert "branches" not in result
        assert "link_conditions" not in result
        assert result["some_key"] == "val"
