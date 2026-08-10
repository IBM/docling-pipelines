"""
Elyra Pipeline Format Converter.

Bidirectional converter between Elyra visual pipeline format and
Docpipe's internal DAG-based execution format.

Elyra Format:
    - Visual pipeline with nodes, ports, and links
    - Nested structure with canvas/app_data layers
    - UI positioning and visual metadata

Internal Format:
    - Flat DAG with nodes and edges
    - Execution-ready configuration
    - Topologically sorted for execution order
"""

from collections import defaultdict, deque
from copy import deepcopy
from uuid import uuid4

import networkx as nx

from docpipe.core.constants.constants import DocpipeConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import OperatorCategory
from docpipe.exceptions.docpipe_exceptions import FlowValidationException, ValidationAlert
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()

# Category-based colors and descriptions for Elyra node metadata
# Using OperatorCategory enum values as keys
CATEGORY_COLORS = {
    OperatorCategory.Ingest: "#b28600",
    OperatorCategory.Extract: "#00539a",
    OperatorCategory.Quality: "#491d8b",
    OperatorCategory.Functional: "#520408",
    OperatorCategory.VectorDB: "#009d9a",
    OperatorCategory.Storage: "#009d9a",  # Same as VectorDB
}

CATEGORY_DESCRIPTIONS = {
    OperatorCategory.Ingest: "Ingest data",
    OperatorCategory.Extract: "Extract data",
    OperatorCategory.Quality: "Quality",
    OperatorCategory.Functional: "Transform data",
    OperatorCategory.VectorDB: "Generate output",
    OperatorCategory.Storage: "Generate output",  # Same as VectorDB
}

# Maximum nodes allowed in a flow
MAX_NODES = 100


class ElyraConstants:
    """Elyra JSON key and value constants used by the converter."""

    ID = "id"
    DOC_TYPE = "doc_type"
    VERSION = "version"
    JSON_SCHEMA = "json_schema"
    PRIMARY_PIPELINE = "primary_pipeline"
    PIPELINES = "pipelines"
    NODES = "nodes"
    NODE_TYPE = "type"
    EXECUTION_NODE = "execution_node"
    OP = "op"
    APP_DATA = "app_data"
    UI_DATA = "ui_data"
    REACT_NODES_DATA = "react_nodes_data"
    PARAMETERS = "parameters"
    PROPERTIES = "properties"
    DS_FLOW = "ds_flow"
    NAME = "name"
    DESCRIPTION = "description"
    JOB_NAME = "job_name"
    SCHEDULE = "schedule"
    GLOBAL_CONFIG = "global_config"
    RUNTIME_REF = "runtime_ref"
    SCHEMAS = "schemas"
    OUTPUTS = "outputs"
    INPUTS = "inputs"
    LINKS = "links"
    NODE_ID_REF = "node_id_ref"
    PORT_ID_REF = "port_id_ref"
    LINK_ID = "link_id"
    LINK_NAME = "link_name"
    LINK_CONDITIONS = "link_conditions"
    CONDITION = "condition"
    CRITERIA_JSON = "criteria_json"
    CRITERIA_LIST = "criteria_list"
    LOGICAL_OPERATOR = "logical_operator"
    TARGET_NODE_ID = "target_node_id"
    TARGET_PORT_ID = "target_port_id"
    BRANCHES = "branches"
    LABEL = "label"
    IMAGE = "image"
    X_POS = "x_pos"
    Y_POS = "y_pos"
    X = "x"
    Y = "y"
    ZOOM = "zoom"
    COMMENTS = "comments"
    COLOR = "color"
    CARD_DESCRIPTION = "cardDescription"
    CARDINALITY = "cardinality"
    MIN = "min"
    MAX = "max"


class ElyraConverter:
    """Converts Elyra pipeline format to internal DAG format."""

    def __init__(self):
        """Initialize converter with operator metadata."""
        self.metadata: dict[str, dict] = {}
        self._load_operator_metadata()

    def _load_operator_metadata(self) -> None:
        """Load operator metadata for descriptions and other details."""
        try:
            from docpipe.core.operators.operator_metadata import OperatorMetadata

            metadata_loader = OperatorMetadata()
            self.metadata = metadata_loader.get_operator_metadata(internal_features=False)
        except Exception as e:
            # If metadata loading fails, continue with empty metadata
            # Converter will fall back to generic descriptions
            logger.warning(f"Failed to load operator metadata: {e}")
            self.metadata = {}

    def transform_elyra_to_internal(self, *, elyra_json: dict, flow_id: str) -> dict:
        """
        Transform Elyra pipeline JSON to internal DAG format.

        Args:
            elyra_json: Elyra pipeline definition with nodes, links, and metadata.
            flow_id: Flow identifier to use in the internal format. Must not be None.

        Returns:
            Internal flow definition with flat DAG structure

        Raises:
            FlowValidationException: If pipeline structure is invalid or flow_id is None
        """
        # Validate flow_id is provided
        if flow_id is None:
            error = ValidationAlert(
                code=ErrorCode.FLOW_VALIDATION_FAILED.value,
                message="flow_id is required during Elyra to internal format conversion and cannot be None.",
            )
            raise FlowValidationException(errors=[error])

        pipeline = self._get_primary_pipeline(elyra_json=elyra_json)

        if pipeline is None:
            error = ValidationAlert(
                code=ErrorCode.FLOW_VALIDATION_FAILED.value,
                message="Flow definition is missing primary pipeline.",
            )
            raise FlowValidationException(errors=[error])

        # Extract flow metadata from Elyra pipeline metadata
        app_data = pipeline.get(ElyraConstants.APP_DATA, {})

        # Read flow metadata from ui_data when present
        ui_data = app_data.get(ElyraConstants.UI_DATA, {})
        flow_name = ui_data.get(ElyraConstants.NAME)
        flow_description = ui_data.get(ElyraConstants.DESCRIPTION, "")

        # Read global configuration from Elyra pipeline properties
        global_config = app_data.get(ElyraConstants.PROPERTIES, {})

        # Fallback to ds_flow metadata when needed
        if not flow_name:
            flow_metadata = app_data.get(ElyraConstants.DS_FLOW, {})
            flow_name = flow_metadata.get(OperatorConstants.Misc.NAME, DocpipeConstants.UNNAMED_FLOW)
            flow_description = flow_metadata.get(DocpipeConstants.DESCRIPTION, "")
            if not global_config:
                global_config = flow_metadata.get(ElyraConstants.GLOBAL_CONFIG, {})

        # Get nodes from pipeline
        nodes = pipeline.get(ElyraConstants.NODES, [])
        if not nodes:
            logger.warning("No operators exist in the flow.")
            return {
                DocpipeConstants.FLOW: {
                    "flow_id": flow_id,
                    OperatorConstants.Misc.NAME: flow_name,
                    DocpipeConstants.DESCRIPTION: flow_description,
                    "global_config": global_config,
                    DocpipeConstants.DAG: [],
                }
            }

        # Transform nodes to DAG
        dag = self._transform_pipeline_to_dag(nodes=nodes)

        return {
            DocpipeConstants.FLOW: {
                OperatorConstants.Misc.ID: flow_id,
                OperatorConstants.Misc.NAME: flow_name,
                DocpipeConstants.DESCRIPTION: flow_description,
                "global_config": global_config,
                DocpipeConstants.DAG: dag,
            }
        }

    def get_global_config_from_elyra(self, *, elyra_json: dict) -> dict:
        """
        Extract the global_config from an Elyra pipeline JSON.

        Mirrors the lookup order used during conversion:
        1. ``app_data.properties`` (newer Elyra format)
        2. ``app_data.ds_flow.global_config`` (legacy ds_flow format)

        Args:
            elyra_json: Elyra pipeline definition

        Returns:
            global_config dict, or an empty dict if not present
        """
        pipeline = self._get_primary_pipeline(elyra_json=elyra_json)
        if pipeline is None:
            return {}

        app_data = pipeline.get(ElyraConstants.APP_DATA, {})

        global_config = app_data.get(ElyraConstants.PROPERTIES, {})
        if global_config:
            return global_config

        flow_metadata = app_data.get(ElyraConstants.DS_FLOW, {})
        return flow_metadata.get(ElyraConstants.GLOBAL_CONFIG, {})

    def _get_primary_pipeline(self, *, elyra_json: dict) -> dict | None:
        """
        Extract the primary pipeline from Elyra JSON structure.

        Supports:
        - Elyra JSON with an explicit primary pipeline reference
        - Elyra JSON where the first pipeline should be used

        Args:
            elyra_json: Elyra pipeline definition

        Returns:
            Primary pipeline dictionary or None if not found
        """
        # Check for an explicit primary pipeline reference
        primary_id = elyra_json.get(ElyraConstants.PRIMARY_PIPELINE)
        pipelines = elyra_json.get(ElyraConstants.PIPELINES, [])

        if not pipelines:
            return None

        if primary_id:
            # Find the referenced pipeline by ID
            for pipeline in pipelines:
                if pipeline.get(ElyraConstants.ID) == primary_id:
                    return pipeline
            logger.warning(f"Primary pipeline '{primary_id}' not found, using first pipeline")

        # Fallback to the first pipeline in the document
        return pipelines[0]

    def _transform_pipeline_to_dag(self, *, nodes: list[dict]) -> list[dict]:
        """
        Transform Elyra nodes with links to internal DAG format.

        Args:
            nodes: List of Elyra node definitions

        Returns:
            Topologically sorted list of internal node definitions

        Raises:
            FlowValidationException: If DAG is invalid (cycles, disconnected, etc.)
        """
        node_ids: set[str] = set()
        port_ids: set[str] = set()

        # Collect all node and port IDs for validation
        for node in nodes:
            node_ids.add(node[OperatorConstants.Misc.ID])
            # Collect port IDs from both outputs and inputs
            port_ids.update(output[OperatorConstants.Misc.ID] for output in node.get(ElyraConstants.OUTPUTS, []))
            port_ids.update(input_port[OperatorConstants.Misc.ID] for input_port in node.get(ElyraConstants.INPUTS, []))

        # Build directed graph for validation
        graph = nx.DiGraph()
        transformed = []
        first_nodes = []
        link_nodes = {}

        # Handle branching operators - extract link metadata
        branching_nodes = [
            node for node in nodes if node.get(ElyraConstants.OP) == OperatorConstants.Operators.BRANCHING
        ]
        for branching_node in branching_nodes:
            branching_config = branching_node.get(ElyraConstants.PARAMETERS, {})

            for link in branching_config.get(ElyraConstants.LINK_CONDITIONS, []):
                link_nodes[link[ElyraConstants.TARGET_NODE_ID]] = (
                    link.get(ElyraConstants.LINK_ID),
                    link.get(ElyraConstants.LINK_NAME),
                )

        # Transform each node
        for node in nodes:
            node_id = node[OperatorConstants.Misc.ID]
            name = self._get_node_name(node=node)
            operator = node.get(ElyraConstants.OP, "")
            config = self._extract_node_config(node=node, operator=operator)

            # Handle branching operator special case
            if operator == OperatorConstants.Operators.BRANCHING and ElyraConstants.LINK_CONDITIONS in config:
                config = self._transform_branching_config(config=config)

            # Determine if this node is a branch target
            link_id = None
            link_name = None
            if node_id in link_nodes:
                link_id, link_name = link_nodes[node_id]

            # Build input edges from links
            input_edges = []
            has_links = False

            for input_port in node.get(ElyraConstants.INPUTS, []):
                for link in input_port.get(ElyraConstants.LINKS, []):
                    has_links = True
                    ref_node_id = link[ElyraConstants.NODE_ID_REF]
                    ref_port_id = link[ElyraConstants.PORT_ID_REF]
                    link_name_from_link = link.get(DocpipeConstants.LINK_NAME)

                    # Validate references
                    if ref_node_id not in node_ids:
                        error = ValidationAlert(
                            code=ErrorCode.FLOW_VALIDATION_FAILED.value,
                            message=f"Invalid link: node_id_ref '{ref_node_id}' does not exist.",
                        )
                        logger.error(str(error))
                        raise FlowValidationException(errors=[error])

                    if ref_port_id not in port_ids:
                        error = ValidationAlert(
                            code=ErrorCode.FLOW_VALIDATION_FAILED.value,
                            message=f"Invalid link: port_id_ref '{ref_port_id}' does not exist.",
                        )
                        logger.error(str(error))
                        raise FlowValidationException(errors=[error])

                    input_edges.append(
                        {
                            ElyraConstants.NODE_ID_REF: ref_node_id,
                            DocpipeConstants.LINK_NAME: link_name_from_link,
                        }
                    )

                    graph.add_edge(ref_node_id, node_id)

            # Build output edges
            output_edges = []
            for other_node in nodes:
                if other_node[OperatorConstants.Misc.ID] == node_id:
                    continue
                for input_port in other_node.get(ElyraConstants.INPUTS, []):
                    for link in input_port.get(ElyraConstants.LINKS, []):
                        if link[ElyraConstants.NODE_ID_REF] == node_id:
                            output_edges.append(
                                {
                                    ElyraConstants.NODE_ID_REF: other_node[OperatorConstants.Misc.ID],
                                }
                            )

            # Track nodes without inputs (starting nodes)
            if not node.get(ElyraConstants.INPUTS) or not has_links:
                first_nodes.append(node_id)

            # Special handling for merge operator
            if operator == OperatorConstants.Operators.MERGE:
                config["input_links"] = input_edges

            transformed.append(
                {
                    OperatorConstants.Misc.ID: node_id,
                    OperatorConstants.Misc.NAME: name,
                    OperatorConstants.Misc.OPERATOR: operator,
                    "config": config,
                    DocpipeConstants.INPUT_EDGES: input_edges,
                    DocpipeConstants.OUTPUT_EDGES: output_edges,
                    ElyraConstants.LINK_ID: link_id,
                    ElyraConstants.LINK_NAME: link_name,
                }
            )

        # Validate DAG structure
        self._validate_dag(graph=graph, first_nodes=first_nodes, node_count=len(transformed))

        # Sort topologically
        return self._sort_dag_topologically(dag=transformed)

    def _get_node_name(self, *, node: dict) -> str:
        """
        Extract node name from Elyra node definition.

        Args:
            node: Elyra node definition

        Returns:
            Node name or operator type as fallback
        """
        app_data = node.get(ElyraConstants.APP_DATA, {})
        ui_data = app_data.get(ElyraConstants.UI_DATA, {})
        return ui_data.get(ElyraConstants.LABEL, node.get(ElyraConstants.OP, "unnamed"))

    def _extract_node_config(self, *, node: dict, operator: str) -> dict:
        """
        Extract configuration parameters from Elyra node.

        Extract configuration parameters from an Elyra node.

        Args:
            node: Elyra node definition
            operator: Operator type

        Returns:
            Configuration dictionary
        """
        config = node.get(ElyraConstants.PARAMETERS)
        return deepcopy(config) if config else {}

    def _get_node_position(self, *, node: dict) -> tuple[int, int]:
        """
        Extract node position from UI data.

        Supports:
        - Elyra positions stored as x_pos and y_pos
        - Elyra positions stored as x and y

        Args:
            node: Elyra node definition

        Returns:
            Tuple of (x, y) coordinates
        """
        app_data = node.get(ElyraConstants.APP_DATA, {})
        ui_data = app_data.get(ElyraConstants.UI_DATA, {})

        # Prefer x_pos and y_pos when present
        x = ui_data.get(ElyraConstants.X_POS)
        y = ui_data.get(ElyraConstants.Y_POS)

        # Fall back to x and y
        if x is None:
            x = ui_data.get(ElyraConstants.X, 100)
        if y is None:
            y = ui_data.get(ElyraConstants.Y, 100)

        return (int(x), int(y))

    def _transform_branching_config(self, *, config: dict) -> dict:
        """
        Transform branching operator configuration from Elyra to internal format.

        Args:
            config: Branching operator configuration

        Returns:
            Transformed configuration with branches array
        """
        config = deepcopy(config)
        branches = []

        for link in config.get(ElyraConstants.LINK_CONDITIONS, []):
            condition = link.get(ElyraConstants.CONDITION, {})

            # Extract criteria_json from condition
            criteria_json = condition.get(ElyraConstants.CRITERIA_JSON, {})

            # Ensure criteria_json is a dict with proper structure
            if not isinstance(criteria_json, dict):
                # If it's not a dict (e.g., list or None), create default structure
                criteria_json = {
                    ElyraConstants.LOGICAL_OPERATOR: "AND",
                    ElyraConstants.CRITERIA_LIST: [],
                }

            branches.append(
                {
                    ElyraConstants.CRITERIA_LIST: condition.get(ElyraConstants.CRITERIA_LIST, []),
                    ElyraConstants.CRITERIA_JSON: criteria_json,
                    ElyraConstants.LOGICAL_OPERATOR: condition.get(ElyraConstants.LOGICAL_OPERATOR),
                    ElyraConstants.LINK_ID: link.get(ElyraConstants.LINK_ID),
                    ElyraConstants.LINK_NAME: link.get(ElyraConstants.LINK_NAME),
                }
            )

        config.pop(ElyraConstants.LINK_CONDITIONS, None)
        config[ElyraConstants.BRANCHES] = branches
        return config

    def _validate_dag(self, *, graph: nx.DiGraph, first_nodes: list, node_count: int) -> None:
        """
        Validate DAG structure for cycles, disconnected nodes, and size limits.

        Args:
            graph: NetworkX directed graph
            first_nodes: List of starting node IDs
            node_count: Total number of nodes

        Raises:
            FlowValidationException: If validation fails
        """
        # Check for cycles
        if not nx.is_directed_acyclic_graph(graph):
            error = ValidationAlert(
                code=ErrorCode.FLOW_VALIDATION_FAILED.value,
                message="The pipeline contains a loop, which creates a cycle. "
                "Pipelines must follow a Directed Acyclic Graph (DAG) structure, "
                "meaning no circular dependencies are allowed between steps.",
            )
            logger.error(str(error))
            raise FlowValidationException(errors=[error])

        # Check node limit
        if graph.number_of_nodes() > MAX_NODES:
            error = ValidationAlert(
                code=ErrorCode.FLOW_VALIDATION_FAILED.value,
                message=f"Flow has more than {MAX_NODES} nodes.",
            )
            logger.error(str(error))
            raise FlowValidationException(errors=[error])

        # Check for starting nodes
        if not first_nodes:
            error = ValidationAlert(
                code=ErrorCode.FLOW_VALIDATION_FAILED.value,
                message="Pipeline invalid. No starting node found.",
            )
            logger.error(str(error))
            raise FlowValidationException(errors=[error])

        # Warn about disconnected nodes
        if len(first_nodes) > 1:
            logger.warning("Pipeline has multiple disconnected starting nodes.")

    def _sort_dag_topologically(self, *, dag: list[dict]) -> list[dict]:
        """
        Sort DAG nodes in topological order using Kahn's algorithm.

        Args:
            dag: List of node definitions with edges

        Returns:
            Topologically sorted list of nodes

        Raises:
            FlowValidationException: If cycle detected during sorting
        """
        # Build adjacency list from output edges
        adjacency_list = self._get_adjacency_list(dag=dag)
        by_node_id_map = {node[OperatorConstants.Misc.ID]: node for node in dag}

        # Calculate in-degree for each node
        indegree: dict[str, int] = defaultdict(int)
        for u in adjacency_list:
            indegree[u]  # Initialize
            for v in adjacency_list[u]:
                indegree[v] += 1

        # Start with zero in-degree nodes
        queue = deque([u for u, deg in indegree.items() if deg == 0])
        topo_order = []

        # BFS-style topological sort
        while queue:
            u = queue.popleft()
            topo_order.append(by_node_id_map.get(u, {}))
            for v in adjacency_list.get(u, []):
                indegree[v] -= 1
                if indegree[v] == 0:
                    queue.append(v)

        # Verify all nodes processed
        if len(topo_order) != len(indegree):
            error = ValidationAlert(
                code=ErrorCode.FLOW_VALIDATION_FAILED.value,
                message="DAG contains a cycle; topological sort not possible",
            )
            logger.error(str(error))
            raise FlowValidationException(errors=[error])

        return topo_order

    def _get_adjacency_list(self, *, dag: list[dict]) -> dict[str, list[str]]:
        """
        Build adjacency list from DAG output edges.

        Args:
            dag: List of node definitions

        Returns:
            Adjacency list mapping node IDs to their successors
        """
        adjacency_list: dict[str, list[str]] = defaultdict(list)
        for node in dag:
            node_id = node[OperatorConstants.Misc.ID]
            adjacency_list[node_id]  # Initialize
            for edge in node.get(DocpipeConstants.OUTPUT_EDGES, []):
                adjacency_list[node_id].append(edge[ElyraConstants.NODE_ID_REF])
        return adjacency_list

    def transform_internal_to_elyra(
        self,
        *,
        internal_json: dict,
        metadata: dict[str, dict] | None = None,
        node_spacing_x: int = 260,
        node_spacing_y: int = 230,
    ) -> dict:
        """
        Transform internal DAG format to Elyra pipeline format.

        This reverse conversion generates visual layout information using hierarchical layout
        and reconstructs the Elyra structure from the internal DAG.

        Args:
            internal_json: Internal flow definition with DAG
            metadata: Operator metadata dict (operator_name -> metadata). If None, will be loaded automatically.
            node_spacing_x: Horizontal spacing between nodes (pixels)
            node_spacing_y: Vertical spacing between nodes (pixels)

        Returns:
            Elyra pipeline definition with generated UI layout

        Raises:
            FlowValidationException: If internal format is invalid
        """
        # Load metadata if not provided
        if metadata is None:
            from docpipe.core.operators.operator_metadata import OperatorMetadata

            operator_metadata = OperatorMetadata()
            metadata = operator_metadata.get_operator_metadata()

        # Store metadata for use in helper methods
        self.metadata = metadata

        flow = internal_json.get(DocpipeConstants.FLOW)
        if not flow:
            error = ValidationAlert(
                code=ErrorCode.FLOW_VALIDATION_FAILED.value,
                message="Internal format missing 'flow' key.",
            )
            raise FlowValidationException(errors=[error])

        dag = flow.get(DocpipeConstants.DAG, [])
        flow_name = flow.get(OperatorConstants.Misc.NAME, DocpipeConstants.UNNAMED_FLOW)
        flow_description = flow.get(DocpipeConstants.DESCRIPTION, "")
        global_config = flow.get(ElyraConstants.GLOBAL_CONFIG, {})

        # Generate node positions using hierarchical layout
        node_positions = self._generate_node_layout(
            dag=dag,
            spacing_x=node_spacing_x,
            spacing_y=node_spacing_y,
        )

        # Convert DAG nodes to Elyra nodes
        elyra_nodes = []
        port_mappings = {}  # node_id -> {input_ports: [], output_ports: []}

        for node in dag:
            elyra_node, ports = self._convert_dag_node_to_elyra(
                node=node, position=node_positions.get(node[OperatorConstants.Misc.ID], (100, 100))
            )
            elyra_nodes.append(elyra_node)
            port_mappings[node[OperatorConstants.Misc.ID]] = ports

        # Add links to nodes based on edges
        self._add_links_to_elyra_nodes(elyra_nodes=elyra_nodes, dag=dag, port_mappings=port_mappings)

        # Generate pipeline ID
        pipeline_id = str(uuid4())

        # Build Elyra pipeline structure
        return {
            ElyraConstants.DOC_TYPE: "pipeline",
            ElyraConstants.VERSION: "3.0",
            ElyraConstants.JSON_SCHEMA: "http://api.dataplatform.ibm.com/schemas/common-pipeline/pipeline-flow/pipeline-flow-v3-schema.json",
            ElyraConstants.ID: str(uuid4()),
            ElyraConstants.PRIMARY_PIPELINE: pipeline_id,
            ElyraConstants.PIPELINES: [
                {
                    ElyraConstants.ID: pipeline_id,
                    ElyraConstants.NODES: elyra_nodes,
                    ElyraConstants.APP_DATA: {
                        ElyraConstants.DS_FLOW: {
                            ElyraConstants.NAME: flow_name,
                            ElyraConstants.DESCRIPTION: flow_description,
                            ElyraConstants.JOB_NAME: flow_name,
                            ElyraConstants.SCHEDULE: {},
                            ElyraConstants.GLOBAL_CONFIG: global_config,
                        },
                        ElyraConstants.UI_DATA: {
                            ElyraConstants.ZOOM: {"k": 1.0, ElyraConstants.X: 0.0, ElyraConstants.Y: 0.0},
                            ElyraConstants.COMMENTS: [],
                        },
                    },
                    ElyraConstants.RUNTIME_REF: "",
                }
            ],
            ElyraConstants.SCHEMAS: [],
        }

    def _generate_node_layout(self, *, dag: list[dict], spacing_x: int, spacing_y: int) -> dict[str, tuple[int, int]]:
        """
            Processes the graph structure to create a visual layout where:
        - Main flow progresses left-to-right
        - Branches fan out spatially from branching nodes
        - Each branch's operators are grouped together
        - Merge nodes collect from spatially separated branches

        Args:
            dag: List of DAG nodes
            spacing_x: Horizontal spacing between nodes (default 260px like API)
            spacing_y: Vertical spacing between branches (default 230px like API)

        Returns:
            Dictionary mapping node_id to (x, y) coordinates
        """
        positions = {}
        node_by_id = {node[OperatorConstants.Misc.ID]: node for node in dag}

        # Build graph structure
        children_map = defaultdict(list)  # node_id -> [child_node_ids]
        parents_map = defaultdict(list)  # node_id -> [parent_node_ids]

        for node in dag:
            node_id = node[OperatorConstants.Misc.ID]
            for edge in node.get(DocpipeConstants.INPUT_EDGES, []):
                parent_id = edge[ElyraConstants.NODE_ID_REF]
                children_map[parent_id].append(node_id)
                parents_map[node_id].append(parent_id)

        # Find root nodes (no parents)
        root_nodes = [node[OperatorConstants.Misc.ID] for node in dag if not node.get(DocpipeConstants.INPUT_EDGES)]

        # Track which nodes have been positioned
        positioned = set()

        def _position_branch_chain(node_id: str, start_x: int, start_y: int) -> int:
            """
            Position a linear chain of nodes in a branch.

            Args:
                node_id: Starting node of the branch
                start_x: Starting x coordinate
                start_y: Y coordinate for this branch

            Returns:
                Maximum x position used
            """
            current_id = node_id
            current_x = start_x

            while current_id and current_id not in positioned:
                positions[current_id] = (current_x, start_y)
                positioned.add(current_id)

                children = children_map.get(current_id, [])

                # Move to next node in chain (if only one child and it's not positioned)
                if len(children) == 1 and children[0] not in positioned:
                    current_id = children[0]
                    current_x += spacing_x
                else:
                    # End of chain or multiple children
                    break

            return current_x

        def _position_subtree(node_id: str, start_x: int, start_y: int) -> int:
            """
            Position a node and its descendants. Returns the maximum x position used.

            Args:
                node_id: Node to position
                start_x: Starting x coordinate
                start_y: Starting y coordinate

            Returns:
                Maximum x position used by this subtree
            """
            if node_id in positioned:
                return start_x

            node = node_by_id[node_id]
            operator = node.get(OperatorConstants.Misc.OPERATOR)

            # Position current node
            positions[node_id] = (start_x, start_y)
            positioned.add(node_id)

            current_x = start_x
            children = children_map.get(node_id, [])

            if operator == OperatorConstants.Operators.BRANCHING:
                # Handle branching: position each branch separately
                config = node.get("config", {})
                branches = config.get(ElyraConstants.BRANCHES, [])

                # Build map of link_id to branch index
                branch_map = {}
                for idx, branch in enumerate(branches):
                    link_id = branch.get(ElyraConstants.LINK_ID)
                    if link_id:
                        # Find child with this link_id
                        for child_id in children:
                            child_node = node_by_id[child_id]
                            if child_node.get(ElyraConstants.LINK_ID) == link_id:
                                branch_map[child_id] = idx
                                break

                # Position each branch
                max_x = current_x
                for child_id in children:
                    if child_id in branch_map:
                        b_idx = branch_map[child_id]
                        branch_x = current_x + 280  # Branch starts 280px to the right
                        branch_y = start_y + (b_idx * spacing_y)

                        # Position this branch's subtree
                        branch_max_x = _position_branch_chain(child_id, branch_x, branch_y)
                        max_x = max(max_x, branch_max_x)

                return max_x

            if operator == OperatorConstants.Operators.MERGE:
                # Merge node: already positioned, return next x
                return current_x + spacing_x

            # Regular node: position children sequentially
            next_x = current_x + spacing_x
            for child_id in children:
                if child_id not in positioned:
                    child_max_x = _position_subtree(child_id, next_x, start_y)
                    next_x = child_max_x

            return next_x

        # Position from root nodes
        x_pos = 100
        y_pos = 100
        for root_id in root_nodes:
            if root_id not in positioned:
                max_x = _position_subtree(root_id, x_pos, y_pos)
                x_pos = max_x

        # Position any remaining unpositioned nodes (shouldn't happen in valid DAG)
        for node in dag:
            node_id = node[OperatorConstants.Misc.ID]
            if node_id not in positioned:
                positions[node_id] = (x_pos, y_pos)
                x_pos += spacing_x

        return positions

    def _convert_dag_node_to_elyra(self, *, node: dict, position: tuple[int, int]) -> tuple[dict, dict]:
        """
        Convert a single internal DAG node to Elyra node format.

        Args:
            node: Internal DAG node
            position: (x, y) coordinates for visual placement

        Returns:
            Tuple of (elyra_node, port_mappings)
        """
        node_id = node[OperatorConstants.Misc.ID]
        node_name = node[OperatorConstants.Misc.NAME]
        operator = node[OperatorConstants.Misc.OPERATOR]
        config = node.get("config", {})

        # Generate port IDs
        input_edges = node.get(DocpipeConstants.INPUT_EDGES, [])
        output_edges = node.get(DocpipeConstants.OUTPUT_EDGES, [])

        # Use the operator name for port IDs (e.g., "ingest_cpd_assets_outPort")
        # Only create output ports if there are output edges
        output_ports = []
        if output_edges:
            # Branching operator has unlimited output cardinality
            if operator == OperatorConstants.Operators.BRANCHING:
                output_port_id = f"{operator}_outPort"
                output_ports = [
                    {
                        ElyraConstants.ID: output_port_id,
                        ElyraConstants.APP_DATA: {
                            ElyraConstants.UI_DATA: {
                                ElyraConstants.CARDINALITY: {
                                    ElyraConstants.MIN: 1,
                                    ElyraConstants.MAX: -1,  # Unlimited outputs for branching
                                },
                                ElyraConstants.LABEL: "Output Port",
                            }
                        },
                    }
                ]
            else:
                output_port_id = f"{operator}_outPort" if len(output_edges) == 1 else f"{operator}_outPort_0"
                output_ports = [
                    {
                        ElyraConstants.ID: output_port_id,
                        ElyraConstants.APP_DATA: {
                            ElyraConstants.UI_DATA: {
                                ElyraConstants.CARDINALITY: {
                                    ElyraConstants.MIN: 1,
                                    ElyraConstants.MAX: 1,
                                },
                                ElyraConstants.LABEL: "Output Port",
                            }
                        },
                    }
                ]

        # Only create input ports if there are input edges
        input_ports = []
        if input_edges:
            # Merge operator has unlimited input cardinality
            if operator == OperatorConstants.Operators.MERGE:
                input_port_id = f"{operator}_inPort"
                input_ports = [
                    {
                        ElyraConstants.ID: input_port_id,
                        ElyraConstants.APP_DATA: {
                            ElyraConstants.UI_DATA: {
                                ElyraConstants.CARDINALITY: {
                                    ElyraConstants.MIN: 1,
                                    ElyraConstants.MAX: -1,  # Unlimited inputs for merge
                                },
                                ElyraConstants.LABEL: "Input Port",
                            }
                        },
                    }
                ]
            else:
                input_port_id = f"{operator}_inPort" if len(input_edges) == 1 else f"{operator}_inPort_0"
                input_ports = [
                    {
                        ElyraConstants.ID: input_port_id,
                        ElyraConstants.APP_DATA: {
                            ElyraConstants.UI_DATA: {
                                ElyraConstants.CARDINALITY: {
                                    ElyraConstants.MIN: 1,
                                    ElyraConstants.MAX: 1,
                                },
                                ElyraConstants.LABEL: "Input Port",
                            }
                        },
                    }
                ]

        # Handle branching operator special case
        if operator == OperatorConstants.Operators.BRANCHING:
            config = self._convert_branching_to_elyra(config=config, node=node)

        # IBM format: parameters at node level, NOT in app_data
        # app_data contains react_nodes_data and ui_data
        app_data = {
            ElyraConstants.REACT_NODES_DATA: {
                ElyraConstants.COLOR: self._get_operator_color(operator=operator),
                ElyraConstants.CARD_DESCRIPTION: self._get_operator_description(operator=operator),
            },
            ElyraConstants.UI_DATA: {
                ElyraConstants.LABEL: node_name,
                ElyraConstants.IMAGE: "",
                ElyraConstants.X_POS: position[0],
                ElyraConstants.Y_POS: position[1],
                ElyraConstants.DESCRIPTION: self._get_detailed_operator_description(operator=operator),
            },
        }

        elyra_node = {
            ElyraConstants.ID: node_id,
            ElyraConstants.NODE_TYPE: ElyraConstants.EXECUTION_NODE,
            ElyraConstants.OP: operator,
            ElyraConstants.APP_DATA: app_data,
            ElyraConstants.PARAMETERS: config,  # Parameters at node level, not in app_data
        }

        # Only add outputs if they exist
        if output_ports:
            elyra_node[ElyraConstants.OUTPUTS] = output_ports

        # Only add inputs if they exist
        if input_ports:
            elyra_node[ElyraConstants.INPUTS] = input_ports

        port_mappings = {"input_ports": input_ports, "output_ports": output_ports}

        return elyra_node, port_mappings

    def _get_operator_color(self, *, operator: str) -> str:
        """
        Get color for operator based on its category from metadata.
        """
        category = self.metadata.get(operator, {}).get(OperatorConstants.Misc.CATEGORY, "")
        # category is a string like "Ingest", "Extract", etc.
        # Convert to OperatorCategory enum for lookup
        if not category:
            return "#000000"

        try:
            category_enum = OperatorCategory(category)
            return CATEGORY_COLORS.get(category_enum, "#000000")
        except ValueError:
            return "#000000"

    def _get_operator_description(self, *, operator: str) -> str:
        """
        Get description for operator based on its category from metadata.
        """
        category = self.metadata.get(operator, {}).get(OperatorConstants.Misc.CATEGORY, "")
        # category is a string like "Ingest", "Extract", etc.
        # Convert to OperatorCategory enum for lookup
        if not category:
            return "Custom operator"

        try:
            category_enum = OperatorCategory(category)
            return CATEGORY_DESCRIPTIONS.get(category_enum, "Custom operator")
        except ValueError:
            return "Custom operator"

    def _get_detailed_operator_description(self, *, operator: str) -> str:
        """
        Get detailed description for operator from metadata.
        Falls back to generic description if metadata not available.

        Args:
            operator: Operator short name (e.g., 'ingest_cpd_assets')

        Returns:
            Detailed operator description from metadata, or generic fallback
        """
        # Try to get description from operator metadata
        operator_meta = self.metadata.get(operator, {})
        description = operator_meta.get("description", "")

        if description:
            return description

        # Fallback to generic description
        return f"{operator} operator"

    def _convert_branching_to_elyra(self, *, config: dict, node: dict) -> dict:
        """
        Convert branching operator config from internal to Elyra format.

        Internal: branches array with filter criteria
        Elyra: link_conditions with target_node_id
        """
        config = deepcopy(config)
        branches = config.pop(ElyraConstants.BRANCHES, [])

        if not branches:
            return config

        # Build link_conditions from branches
        # Need to find target nodes for each branch using link_id
        link_conditions = []

        for branch in branches:
            link_id = branch.get(ElyraConstants.LINK_ID)
            link_name = branch.get(ElyraConstants.LINK_NAME)

            # Find target node with this link_id (will be set during link creation)
            link_condition = {
                ElyraConstants.LINK_ID: link_id,
                ElyraConstants.LINK_NAME: link_name,
                ElyraConstants.CONDITION: {
                    ElyraConstants.CRITERIA_JSON: branch.get(
                        ElyraConstants.CRITERIA_JSON,
                        {
                            ElyraConstants.LOGICAL_OPERATOR: "AND",
                            ElyraConstants.CRITERIA_LIST: [],
                        },
                    )
                },
                # target_node_id and target_port_id will be added during link creation
            }
            link_conditions.append(link_condition)

        config[ElyraConstants.LINK_CONDITIONS] = link_conditions
        return config

    def _add_links_to_elyra_nodes(self, *, elyra_nodes: list[dict], dag: list[dict], port_mappings: dict) -> None:
        """
        Add link information to Elyra nodes based on DAG edges.

        Modifies elyra_nodes in place by adding links to input ports.
        Generates link UUIDs for Elyra links.
        """
        # Build node lookup
        elyra_node_by_id = {node[ElyraConstants.ID]: node for node in elyra_nodes}
        dag_node_by_id = {node[OperatorConstants.Misc.ID]: node for node in dag}

        # Process each node's input edges
        for dag_node in dag:
            node_id = dag_node[OperatorConstants.Misc.ID]
            input_edges = dag_node.get(DocpipeConstants.INPUT_EDGES, [])

            if not input_edges:
                continue

            elyra_node = elyra_node_by_id[node_id]
            input_ports = elyra_node.get(ElyraConstants.INPUTS, [])

            # All operators have only 1 input port with multiple links
            # Initialize links array for the first (and only) input port
            if input_ports and ElyraConstants.LINKS not in input_ports[0]:
                input_ports[0][ElyraConstants.LINKS] = []

            # Add all links to the single input port
            for edge in input_edges:
                # Internal format only has node_id_ref, not port_id_ref
                source_node_id = edge.get(ElyraConstants.NODE_ID_REF)
                link_name = edge.get(DocpipeConstants.LINK_NAME)

                # Generate port_id from the source node's output ports
                # This ensures the generated link points to the correct Elyra output port
                source_ports = port_mappings.get(source_node_id, {}).get("output_ports", [])
                source_port_id = source_ports[0][ElyraConstants.ID] if source_ports else f"{source_node_id}-out-0"

                # Use the node's link_id if it exists (for branching targets), otherwise generate new UUID
                # This ensures branching link_conditions match the actual link IDs in target nodes
                link_id = dag_node.get(ElyraConstants.LINK_ID) if dag_node.get(ElyraConstants.LINK_ID) else str(uuid4())

                # Build Elyra link structure
                link = {
                    ElyraConstants.ID: link_id,
                    ElyraConstants.NODE_ID_REF: source_node_id,
                    ElyraConstants.PORT_ID_REF: source_port_id,
                }

                if link_name:
                    link[DocpipeConstants.LINK_NAME] = link_name

                # Add link to the single input port
                input_ports[0][ElyraConstants.LINKS].append(link)

        # Update branching operators with target_node_id
        for elyra_node in elyra_nodes:
            if elyra_node[ElyraConstants.OP] == OperatorConstants.Operators.BRANCHING:
                self._update_branching_targets(elyra_node=elyra_node, dag_node_by_id=dag_node_by_id)

    def _update_branching_targets(self, *, elyra_node: dict, dag_node_by_id: dict) -> None:
        """
        Update branching operator link_conditions with target_node_id and target_port_id.

        Finds target nodes by matching link_id from branches.
        """
        # Read branching parameters from the Elyra node
        parameters = elyra_node.get(ElyraConstants.PARAMETERS, {})
        link_conditions = parameters.get(ElyraConstants.LINK_CONDITIONS, [])

        for link_condition in link_conditions:
            link_id = link_condition.get(ElyraConstants.LINK_ID)

            # Find target node with this link_id
            for node_id, dag_node in dag_node_by_id.items():
                if dag_node.get(ElyraConstants.LINK_ID) == link_id:
                    link_condition[ElyraConstants.TARGET_NODE_ID] = node_id
                    # Add target_port_id using operator name
                    operator = dag_node.get(OperatorConstants.Misc.OPERATOR)
                    link_condition[ElyraConstants.TARGET_PORT_ID] = f"{operator}_inPort"
                    break


__all__ = ["MAX_NODES", "ElyraConverter"]
