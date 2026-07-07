"""Service for enriching flow definitions with per-operator feature metadata."""

from __future__ import annotations

import logging
from typing import Any, Callable

from docpipe.core.assets.flows.application.services.validation_service import ValidationService
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.orchestration.flow_validator import FlowValidator

logger = logging.getLogger(__name__)


def _default_validator_factory() -> FlowValidator:
    """Create a FlowValidator backed by a fresh Python orchestrator.

    Constructs a Python-mode orchestrator, initialises it with fixed
    job/run IDs suitable for metadata work (no persistence side-effects),
    and wraps it in a FlowValidator ready for feature propagation.

    Returns:
        FlowValidator: A fully initialised validator instance.
    """
    from docpipe.core.constants.constants import OrchestratorType
    from docpipe.core.orchestration.orchestrator_factory import OrchestratorFactory

    orchestrator = OrchestratorFactory.create_orchestrator(orchestrator_name=OrchestratorType.PYTHON)
    orchestrator.initialize(job_id="enrich-flow", job_run_id="enrich-flow-run")
    return FlowValidator(orchestrator=orchestrator)


class FlowEnrichmentService:
    """Enriches Elyra flow definitions with per-operator feature metadata.

    Uses FlowValidator.propagate_features_per_node() to run the DAG traversal
    without raising on validation warnings, enabling enrichment for flows
    that are still under construction.

    Metadata is injected into each Elyra node's top-level `parameters` key
    rather than `app_data`.

    Reuses ValidationService._convert_to_dag_flow() for Elyra-to-DAG
    conversion to avoid duplicating that logic.

    Args:
        validator_factory: Zero-argument callable returning a ready-to-use
            FlowValidator. Defaults to _default_validator_factory (production).
            Override in tests to inject a mock validator directly.
    """

    def __init__(
        self,
        validator_factory: Callable[[], FlowValidator] | None = None,
    ) -> None:
        """Initialise the service with an optional validator factory.

        Args:
            validator_factory: Zero-argument callable that returns a ready-to-use
                FlowValidator. Defaults to _default_validator_factory, which
                creates a Python-mode orchestrator per call. Override in tests
                to inject a mock validator without touching the orchestrator stack.
        """
        self._validator_factory = validator_factory or _default_validator_factory
        self._validation_service = ValidationService()

    def enrich_flow_with_features(
        self,
        *,
        flow_definition: dict[str, Any],
    ) -> dict[str, Any]:
        """Enrich a flow definition with per-operator feature metadata.

        Args:
            flow_definition: Flow definition in Elyra format.

        Returns:
            Deep copy of the input flow with metadata injected into each
            node's top-level `parameters` key.

        Raises:
            ValueError: If flow_definition is missing or empty.
            FlowValidationException: If the flow structure is critically invalid
                (e.g., missing node IDs, cycles).
        """
        if not flow_definition:
            raise ValueError("flow_definition is required")

        # 1. Convert Elyra JSON to internal DAG (reuses ValidationService logic)
        internal_dag = self._validation_service._convert_to_dag_flow(flow_definition=flow_definition, is_elyra=True)

        # 2. Run feature propagation without raising on warnings
        validator = self._validator_factory()
        logger.debug("Running feature propagation for flow enrichment")
        node_features = validator.propagate_features_per_node(
            flow_def=internal_dag, global_config=internal_dag.get(OperatorConstants.Config.GLOBAL_CONFIG, {})
        )
        logger.debug("Feature propagation complete: %d nodes", len(node_features))

        # 3. Inject metadata back into each Elyra node's parameters
        return self._inject_node_metadata(
            original_flow=flow_definition,
            node_features=node_features,
        )

    def _inject_node_metadata(
        self,
        *,
        original_flow: dict[str, Any],
        node_features: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Deep-copy an Elyra flow and inject feature metadata into every node.

        Iterates over all pipelines and nodes in the Elyra JSON. For each node
        whose ID has a corresponding entry in ``node_features``, builds a
        metadata block via _build_node_feature_metadata() and merges it into
        the node's top-level ``parameters`` dict. Nodes absent from
        ``node_features`` (e.g. nodes skipped by the propagator) are left
        untouched.

        Metadata is written to ``node.parameters``, never to ``node.app_data``,
        to avoid coupling to the Elyra-specific app_data nesting.

        Args:
            original_flow: The original Elyra pipeline JSON. Not mutated.
            node_features: Mapping of node ID to per-node feature result dict as
                returned by FlowValidator.propagate_features_per_node(). Each
                entry contains ``available_features``, ``input_features``,
                ``output_features``, and ``dropped_features`` keys.

        Returns:
            A deep copy of ``original_flow`` with metadata merged into each
            matched node's ``parameters`` dict.
        """
        import copy

        enriched_flow = copy.deepcopy(original_flow)
        for pipeline in enriched_flow.get("pipelines", []):
            for node in pipeline.get("nodes", []):
                node_id = node.get(OperatorConstants.Misc.ID, "")
                node_feature_result = node_features.get(node_id)
                if node_feature_result is None:
                    continue
                operator_name = node.get(OperatorConstants.Misc.OPERATOR, "")
                # Inject into node.parameters (top-level), never into app_data
                node_params = node.setdefault(OperatorConstants.Config.PARAMETERS, {})
                node_params.update(
                    self._build_node_feature_metadata(
                        node_id=node_id,
                        node_feature_result=node_feature_result,
                        operator_type=operator_name,
                    )
                )
        return enriched_flow

    def _build_node_feature_metadata(
        self,
        *,
        node_id: str,
        node_feature_result: dict[str, Any],
        operator_type: str,
    ) -> dict[str, Any]:
        """Build the feature metadata dict to merge into a single node's ``parameters``.

        Converts raw feature maps from the propagator result into the
        normalised shape expected by the UI,
        and applies operator-specific rules for ``available_features``.

        Args:
            node_id: The Elyra node ID, used as the fallback ``node_id`` value
                when a feature's ``source_node_id`` is absent from the result.
            node_feature_result: Per-node feature result as returned by
                FlowValidator.propagate_features_per_node(). Expected keys:

                - ``available_features`` (dict[str, dict]): post-special-case
                  feature set visible at this node after SELECT/merge logic.
                - ``input_features`` (dict[str, dict]): features flowing in
                  from all upstream nodes.
                - ``output_features`` (dict[str, dict]): new features produced
                  by this node.
                - ``dropped_features`` (list[str]): feature names removed by
                  this node (informational only, not included in output).

            operator_type: The ``op`` value from the Elyra node (e.g.
                ``"sql_filter"``, ``"vectordb"``, ``"chunker"``). Determines
                which ``available_features`` population rule applies.

        Returns:
            Dict with three keys ready to be merged into ``node.parameters``:

            - ``available_features``: populated for ``sql_filter`` (criteria
              dropdown) and ``vectordb`` (field-mapping UI); ``{}`` for all
              other operators. For ``merge``, returns a flat dict for the
              configured strategy.
            - ``input_features``: normalised map of features received from
              upstream nodes.
            - ``output_features``: normalised map of features this node adds.

        Note:
            ``OperatorConstants.Operators.VECTORDB`` is ``"vectordb"``, not
            ``"vectordb_operator"``. This must match the ``op`` value set by
            ElyraConverter on VectorDB nodes.
        """
        available_feature_map = node_feature_result.get(OperatorConstants.Config.AVAILABLE_FEATURES, {})
        input_feature_map = node_feature_result.get(OperatorConstants.Config.INPUT_FEATURES, {})
        output_feature_map = node_feature_result.get(OperatorConstants.Config.OUTPUT_FEATURES, {})

        def _normalise_feature_map(feature_map: dict[str, Any], fallback_node_id: str) -> dict[str, Any]:
            return {
                feature_name: {
                    OperatorConstants.Misc.FEATURE_ATTR_NAME: feature_name,
                    OperatorConstants.Misc.FEATURE_ATTR_DESCRIPTION: feature_meta.get(
                        OperatorConstants.Misc.FEATURE_ATTR_DESCRIPTION, ""
                    ),
                    OperatorConstants.Misc.FEATURE_ATTR_AVAILABLE_FOR_FILTER: feature_meta.get(
                        OperatorConstants.Misc.FEATURE_ATTR_AVAILABLE_FOR_FILTER, True
                    ),
                    OperatorConstants.Misc.FEATURE_ATTR_AVAILABLE_FOR_VECTOR_DB: feature_meta.get(
                        OperatorConstants.Misc.FEATURE_ATTR_AVAILABLE_FOR_VECTOR_DB, False
                    ),
                    OperatorConstants.Misc.TYPE: feature_meta.get(OperatorConstants.Misc.TYPE, "string"),
                    OperatorConstants.Misc.FEATURE_ATTR_NODE_ID: feature_meta.get("source_node_id", fallback_node_id),
                    OperatorConstants.Misc.TAGS: feature_meta.get(OperatorConstants.Misc.TAGS, []),
                }
                for feature_name, feature_meta in feature_map.items()
            }

        if operator_type == OperatorConstants.Operators.SQL_FILTER:
            # TODO: available_features for sql_filter should contain only the features
            # that survive the SQL SELECT clause (post-filter feature set). Currently the
            # full available_feature_map is returned without applying SELECT-clause
            # pruning. This needs to be driven by the operator's configured SQL expression.
            available_features = _normalise_feature_map(available_feature_map, node_id)
        elif operator_type == OperatorConstants.Operators.VECTORDB:
            # TODO: available_features for vectordb should also include adapter-level
            # metadata: available_resources (index/collection names), selected_resource_schema
            # (field-level schema for the configured resource), feature_mappings, and
            # is_docpipe_supported_resource. These require a live OpenSearch/Milvus
            # connection and are not yet populated.
            available_features = _normalise_feature_map(available_feature_map, node_id)
        elif operator_type == OperatorConstants.Operators.MERGE:
            # TODO: available_features for merge should be a three-key nested dict, one
            # entry per strategy, keyed by strategy name:
            #   OperatorConstants.Misc.MERGE_STRATEGY_FULL_OUTER_JOIN
            #   OperatorConstants.Misc.MERGE_STRATEGY_INNER_JOIN
            #   OperatorConstants.Misc.MERGE_STRATEGY_CONCATENATION
            # Each value should be the feature set produced by calling merge_features()
            # with that strategy applied. The configured strategy
            # (node_feature_result["operator_config"].get(OperatorConstants.Misc.MERGE_TYPE))
            # determines which entry the UI pre-selects, but all three must be present.
            # Currently a flat dict for the single configured strategy is returned.
            available_features = _normalise_feature_map(available_feature_map, node_id)
        else:
            available_features = {}

        return {
            OperatorConstants.Config.AVAILABLE_FEATURES: available_features,
            OperatorConstants.Config.INPUT_FEATURES: _normalise_feature_map(input_feature_map, node_id),
            OperatorConstants.Config.OUTPUT_FEATURES: _normalise_feature_map(output_feature_map, node_id),
        }
