"""Feature propagator for flow validation.

This module contains the FeaturePropagator class which handles feature
propagation through DAG flows using operator metadata and special case logic.
"""

import re
from typing import Any

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.operator_metadata import OperatorMetadata
from docpipe.core.orchestration.feature_propagation.models import (
    FeatureMetadata,
    FeaturePropagationResult,
    OutputFeaturesToDrop,
)
from docpipe.exceptions.docpipe_exceptions import (
    ErrorCode,
    FlowValidationException,
    ValidationAlert,
)
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()

# Pre-compile SQL SELECT pattern at module level for performance.
# Uses a negated character class instead of .*? to avoid ReDoS via backtracking:
# SQL column lists cannot contain unquoted semicolons or newlines, so [^;\n] is
# a safe and precise bound for the capture group.
_SQL_SELECT_PATTERN = re.compile(r"SELECT\s+([^;\n]+?)\s+FROM", re.IGNORECASE)


class FeaturePropagator:
    """Handles feature propagation through DAG flows.

    The FeaturePropagator is the core engine for tracking data features as they
    flow through a pipeline of operators. It uses operator metadata to automatically
    determine which features are available at each node, enabling validation of
    feature dependencies and requirements.

    Key Responsibilities:
        - Track features through the pipeline (input → operator → output)
        - Merge input features with operator-defined output features
        - Apply operator-specific feature transformation logic
        - Validate mandatory feature preservation
        - Track feature metadata (description, tags, availability flags)
        - Propagate global parameters (e.g., embeddings_model_id)

    Feature Propagation Model:
        For most operators:
            output_features = input_features UNION operator_defined_features

        Special cases (Extract, SQLFilter, Merge):
            - Extract: Conditionally adds/removes entity features
            - SQLFilter: Removes features not in SELECT clause
            - Merge: Combines features from multiple parents

    Operator Metadata Integration:
        The propagator loads operator metadata once during initialization,
        providing O(1) lookup of operator capabilities during propagation.
        Metadata includes:
            - Output features defined by each operator
            - Feature descriptions and tags
            - Availability flags (for_filter, for_vector_db)
            - Feature types (string, list, etc.)

    Thread Safety:
        FeaturePropagator instances are thread-safe for read operations
        (propagate_features) but should not be shared across concurrent
        write operations (metadata updates).

    Example:
        ```python
        propagator = FeaturePropagator()

        # Propagate features through a node
        result = propagator.propagate_features(
            node_id="extract-1",
            operator_short_name="extract_operator",
            operator_config={"entity_extraction": {"provider": "litellm"}},
            input_features={"id": {...}, "content": {...}},
            global_config={},
            parent_results=[]
        )

        # Check output features
        print(f"Available features: {list(result.feature_metadata.keys())}")
        # Output: ['id', 'content', 'text', 'entities', 'document_type']
        ```

    Architecture:
        FeaturePropagator
            ↓ uses
        OperatorMetadata (operator capabilities)
            ↓ produces
        FeaturePropagationResult (per-node feature state)

    See Also:
        - FeaturePropagationResult: Container for propagation results
        - FeatureMetadata: Feature metadata model
        - OperatorMetadata: Operator capability information
        - FlowValidator: Uses propagator for validation
    """

    def __init__(self):
        """Initialize the feature propagator.

        Loads operator metadata once during initialization for efficient
        feature lookups during propagation. Metadata loading failures for
        operators requiring external services are logged but don't prevent
        propagator initialization.
        """
        self.operator_metadata = OperatorMetadata()
        # Load operator metadata once during initialization
        self.operator_metadata.get_operator_metadata(internal_features=True)

    def propagate_features(
        self,
        *,
        node_id: str,
        operator_short_name: str,
        operator_config: dict[str, Any],
        input_features: dict[str, Any],
        global_config: dict[str, Any],
        parent_results: list[FeaturePropagationResult] | None = None,
    ) -> FeaturePropagationResult:
        """Generic feature propagation using operator metadata.

        This is the main entry point for feature propagation. It handles all
        operators using a consistent algorithm with special case handling for
        operators that transform features (Extract, SQLFilter, Merge).

        Propagation Algorithm:
            1. Store input features explicitly (for debugging/inspection)
            2. Initialize result with input features and their metadata
            3. Load operator metadata to get operator-defined output features
            4. Merge operator features with input features
            5. Apply special case logic (Extract/SQLFilter/Merge)
            6. Propagate global parameters (e.g., embeddings_model_id)
            7. Compute and store output features (new features only)

        Feature Merging Rules:
            - Input features are preserved unless explicitly dropped
            - Operator-defined features override input features (same name)
            - Feature metadata is preserved from upstream or operator definition
            - Availability flags (for_filter, for_vector_db) can be overridden

        Special Case Operators:
            - Extract: Adds/removes entity features based on entity_extraction.provider
            - SQLFilter: Removes features not in SELECT clause
            - Merge: Combines features from multiple parent nodes
            - VectorDB: Produces no output features (terminal operator)

        Args:
            node_id: Unique identifier for this operator node. Used for tracking
                feature origins and scoping feature names.
            operator_short_name: Operator short name (e.g., 'extract_operator',
                'chunker', 'vectordb'). Must match registered operator name.
            operator_config: Operator-specific configuration dict. Used for:
                - Extract: entity_extraction.provider
                - SQLFilter: sql_query
                - Merge: merge_type, column_option, features_to_drop
                - Embeddings: model_id
            input_features: Features available from parent operators. Dict mapping
                feature names to feature definition dicts containing:
                - description: str
                - tags: list[str]
                - available_for_filter: bool
                - available_for_vector_db: bool
                - type: str
                - source_node_id: str (optional)
            global_config: Global flow configuration. Used for operator behavior
                and validation settings.
            parent_results: List of FeaturePropagationResult from parent nodes.
                Required for Merge operator to combine features from multiple inputs.

        Returns:
            FeaturePropagationResult containing:
                - feature_metadata: Dict[feature_name, FeatureMetadata] - All available features
                - input_features: Dict[node_id, Dict[feature_name, feature_def]] - Input features
                - output_features: Dict[node_id, Dict[feature_name, feature_def]] - New features
                - global_params: Dict[param_name, param_value] - Global parameters
                - output_features_to_drop: Dict[node_id, OutputFeaturesToDrop] - Dropped features

        Example:
            ```python
            # Propagate through Extract operator
            result = propagator.propagate_features(
                node_id="extract-1",
                operator_short_name="extract_operator",
                operator_config={
                    "entity_extraction": {
                        "provider": "litellm",
                        "provider_config": {
                            "model_id": "openai/llama3.2"
                        }
                    }
                },
                input_features={
                    "id": {
                        "description": "Document ID",
                        "tags": ["mandatory"],
                        "available_for_filter": True,
                        "available_for_vector_db": False,
                        "type": "string"
                    },
                    "content": {
                        "description": "Document content",
                        "tags": ["mandatory"],
                        "available_for_filter": False,
                        "available_for_vector_db": False,
                        "type": "string"
                    }
                },
                global_config={},
                parent_results=[]
            )

            # Check output features
            output_features = result.get_output_features(node_id="extract-1")
            print(f"New features: {list(output_features.keys())}")
            # Output: ['text', 'entities', 'document_type']
            ```

        Performance:
            - O(1) operator metadata lookup (cached during init)
            - O(n) feature merging where n = number of input features
            - O(m) operator feature addition where m = operator-defined features
            - Special case logic adds minimal overhead

        Thread Safety:
            This method is thread-safe for concurrent calls on the same
            FeaturePropagator instance as it only reads operator metadata.

        See Also:
            - _apply_special_case_logic: Handles Extract/SQLFilter/Merge
            - _propagate_global_params: Tracks global parameters
            - FeaturePropagationResult: Result container
            - OperatorMetadata.get_features: Operator feature lookup
        """
        result = FeaturePropagationResult()
        parent_results = parent_results or []

        # Store input features explicitly
        result.set_input_features(node_id=node_id, features=input_features.copy())

        input_feature_names = set(input_features.keys())

        # Cache constant keys to avoid repeated attribute lookups
        available_for_filter_key = OperatorConstants.Config.AVAILABLE_FOR_FILTER
        available_for_vector_db_key = OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB

        # Start with input features in metadata, preserving upstream metadata shape
        for feature_name, feature_def in input_features.items():
            result.add_feature(
                feature_name=feature_name,
                node_id=feature_def.get("source_node_id", node_id),
                description=feature_def.get(OperatorConstants.Config.DESCRIPTION, ""),
                tags=feature_def.get("tags", []),
                available_for_filter=feature_def.get(available_for_filter_key, True),
                available_for_vector_db=feature_def.get(available_for_vector_db_key, False),
                type=feature_def.get("type", OperatorConstants.Types.TYPE_STRING),
            )

        # Get operator metadata
        operator_features = self.operator_metadata.get_features(short_name=operator_short_name)

        # Add operator-defined output features
        for feature_name, feature_def in operator_features.items():
            # Cache input feature lookup to avoid repeated dict access
            input_feature = input_features.get(feature_name, {})

            result.add_feature(
                feature_name=feature_name,
                node_id=node_id,
                description=feature_def.get(OperatorConstants.Config.DESCRIPTION, ""),
                tags=feature_def.get("tags", []),
                available_for_filter=feature_def.get(
                    available_for_filter_key,
                    input_feature.get(available_for_filter_key, True),
                ),
                available_for_vector_db=feature_def.get(
                    available_for_vector_db_key,
                    input_feature.get(available_for_vector_db_key, False),
                ),
                type=feature_def.get("type", input_feature.get("type", OperatorConstants.Types.TYPE_STRING)),
            )

        # Apply special case logic for specific operators
        result = self._apply_special_case_logic(
            operator_short_name=operator_short_name,
            operator_config=operator_config,
            result=result,
            node_id=node_id,
            global_config=global_config,
            parent_results=parent_results,
        )

        # Propagate global parameters
        self._propagate_global_params(
            operator_short_name=operator_short_name, operator_config=operator_config, result=result
        )

        # Compute output features efficiently
        if operator_short_name == OperatorConstants.Operators.VECTORDB:
            output_feature_names = set()
        else:
            output_feature_names = set(result.feature_metadata.keys()) - input_feature_names

        # Store post-propagation output features explicitly for debugging/inspection
        if output_feature_names:
            result.set_output_features(
                node_id=node_id,
                features={
                    feature_name: self._feature_metadata_to_dict(feature_meta=result.feature_metadata[feature_name])
                    for feature_name in output_feature_names
                },
            )
        else:
            result.set_output_features(node_id=node_id, features={})

        return result

    def _apply_special_case_logic(  # NOSONAR python:S3776
        self,
        *,
        operator_short_name: str,
        operator_config: dict[str, Any],
        result: FeaturePropagationResult,
        node_id: str,
        global_config: dict[str, Any],
        parent_results: list[FeaturePropagationResult],
    ) -> FeaturePropagationResult:
        """Apply operator-specific feature propagation logic.

        Only three operators need special handling:
        1. Extract: Adds/removes entity features based on entity_extraction.provider
        2. SQLFilter: Removes features based on SELECT clause
        3. Merge: Combines features from multiple inputs

        Args:
            operator_short_name: Operator short name
            operator_config: Operator configuration
            result: Current propagation result
            node_id: Node identifier
            global_config: Global configuration

        Returns:
            Updated FeaturePropagationResult
        """
        if operator_short_name == OperatorConstants.Operators.EXTRACT_OPERATOR:
            # Extract operator: Add/remove entity features based on entity extraction mode
            entity_mode = operator_config.get(
                OperatorConstants.Config.PROVIDER,
                OperatorConstants.ExtractionModes.ENTITY_MODE_NONE,
            )
            if entity_mode == OperatorConstants.ExtractionModes.ENTITY_MODE_NONE:
                # Remove entity features if not extracting entities
                if "entities" in result.feature_metadata:
                    del result.feature_metadata["entities"]
                if OperatorConstants.Columns.DOCUMENT_TYPE in result.feature_metadata:
                    del result.feature_metadata[OperatorConstants.Columns.DOCUMENT_TYPE]
            else:
                # Add entity-related features if not already present
                if "entities" not in result.feature_metadata:
                    result.add_feature(
                        feature_name="entities",
                        node_id=node_id,
                        description="Extracted entities from document",
                        tags=["entity"],
                        available_for_filter=False,
                        available_for_vector_db=False,
                        type="list",
                    )
                if OperatorConstants.Columns.DOCUMENT_TYPE not in result.feature_metadata:
                    result.add_feature(
                        feature_name=OperatorConstants.Columns.DOCUMENT_TYPE,
                        node_id=node_id,
                        description="Detected document type",
                        tags=["entity"],
                        available_for_filter=True,
                        available_for_vector_db=False,
                        type=OperatorConstants.Types.TYPE_STRING,
                    )

        elif operator_short_name == OperatorConstants.Operators.SQL_FILTER:
            # SQLFilter: Parse SELECT clause to determine output features
            sql_query = operator_config.get("sql_query", "")
            if sql_query:
                # Parse SELECT clause to get selected features
                selected_features = self._parse_sql_select(sql_query=sql_query)

                # If SELECT *, keep all features
                if not selected_features:
                    return result

                # Remove features not in SELECT (use set for O(1) lookup)
                selected_features_set = set(selected_features)
                features_to_drop = [f for f in result.feature_metadata.keys() if f not in selected_features_set]

                # Validate mandatory features aren't dropped
                mandatory_features = result.get_mandatory_features()
                dropped_mandatory = [f for f in features_to_drop if f in mandatory_features]
                if dropped_mandatory:
                    raise FlowValidationException(
                        errors=[
                            ValidationAlert(
                                ErrorCode.FLOW_VALIDATION_FAILED.value,
                                f"Cannot drop mandatory features: {dropped_mandatory} in SQLFilter operator",
                                message_code="MANDATORY_FEATURES_DROPPED",
                            )
                        ]
                    )

                # Drop features
                for feature in features_to_drop:
                    if feature in result.feature_metadata:
                        del result.feature_metadata[feature]

                # Track dropped features
                features_to_drop_obj = OutputFeaturesToDrop()
                features_to_drop_obj.add_features(features=features_to_drop)
                result.set_output_features_to_drop(node_id=node_id, features_to_drop=features_to_drop_obj)

        elif operator_short_name == OperatorConstants.Operators.MERGE:
            merge_type = operator_config.get(OperatorConstants.Merge.MERGE_TYPE, OperatorConstants.Merge.ROWS)
            column_option = None
            if merge_type == OperatorConstants.Merge.COLUMNS:
                column_option = operator_config.get(OperatorConstants.Merge.COLUMN_OPTION)

            if parent_results:
                merged_features = self.merge_features(
                    parent_results=parent_results,
                    merge_type=merge_type,
                    column_option=column_option,
                )

                result.feature_metadata = merged_features

            # Handle features_to_drop configuration
            features_to_drop = operator_config.get("features_to_drop", [])
            if features_to_drop:
                # Validate mandatory features aren't dropped
                mandatory_features = result.get_mandatory_features()
                dropped_mandatory = [f for f in features_to_drop if f in mandatory_features]
                if dropped_mandatory:
                    raise FlowValidationException(
                        errors=[
                            ValidationAlert(
                                ErrorCode.FLOW_VALIDATION_FAILED.value,
                                f"Cannot drop mandatory features: {dropped_mandatory} in Merge operator",
                                message_code="MANDATORY_FEATURES_DROPPED",
                            )
                        ]
                    )

                # Drop features
                for feature in features_to_drop:
                    if feature in result.feature_metadata:
                        del result.feature_metadata[feature]

                # Track dropped features
                features_to_drop_obj = OutputFeaturesToDrop()
                features_to_drop_obj.add_features(features=features_to_drop)
                result.set_output_features_to_drop(node_id=node_id, features_to_drop=features_to_drop_obj)

        return result

    def _feature_metadata_to_dict(self, *, feature_meta: FeatureMetadata) -> dict[str, Any]:
        """Convert feature metadata object to a debug-friendly dictionary."""
        feature_dict: dict[str, Any] = {
            OperatorConstants.Config.DESCRIPTION: feature_meta.description,
            "tags": feature_meta.tags,
            "type": feature_meta.type,
            OperatorConstants.Config.AVAILABLE_FOR_FILTER: feature_meta.available_for_filter,
            OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: feature_meta.available_for_vector_db,
        }

        if feature_meta.node_id:
            feature_dict["source_node_id"] = feature_meta.node_id

        return feature_dict

    def _propagate_global_params(
        self, *, operator_short_name: str, operator_config: dict[str, Any], result: FeaturePropagationResult
    ) -> None:
        """Propagate global parameters like embeddings_model_id.

        Args:
            operator_short_name: Operator short name
            operator_config: Operator configuration
            result: Feature propagation result to update
        """
        if operator_short_name == OperatorConstants.Operators.EMBEDDINGS:
            model_id = operator_config.get(OperatorConstants.Config.MODEL_ID)
            if model_id:
                result.global_params[OperatorConstants.Config.EMBEDDINGS_MODEL_ID] = model_id

    def _parse_sql_select(self, *, sql_query: str) -> list[str]:
        """Parse SQL SELECT clause to extract selected columns.

        Args:
            sql_query: SQL query string

        Returns:
            List of selected column names (empty list means SELECT *)
        """
        # Use pre-compiled module-level regex pattern for performance
        match = _SQL_SELECT_PATTERN.search(sql_query)
        if not match:
            return []

        select_clause = match.group(1).strip()

        # Handle SELECT *
        if select_clause == "*":
            return []  # Return empty to indicate all features

        # Split by comma and clean up, removing aliases in one pass
        cleaned_columns = []
        for col in select_clause.split(","):
            col = col.strip()
            # Remove aliases (e.g., "column AS alias" -> "column")
            if " AS " in col.upper():
                col = col.split(" AS ")[0].strip()
            cleaned_columns.append(col)

        return cleaned_columns

    def merge_features(  # NOSONAR python:S3776
        self,
        *,
        parent_results: list[FeaturePropagationResult],
        merge_type: str,
        column_option: str | None = None,
    ) -> dict[str, FeatureMetadata]:
        """Merge features from multiple parent results using runtime merge semantics.

        Implements feature merging logic for the Merge operator, which combines
        data from multiple parent nodes. The merge behavior depends on merge_type
        and column_option parameters.

        Merge Types:
            - ROWS: Union of all features from all parents (vertical concatenation)
            - COLUMNS: Join-based merge with column handling options (horizontal join)

        Column Options (for COLUMNS merge):
            - INNER_JOIN_DUPLICATE_COLUMN: Keep only common features across all parents
            - FULL_OUTER_JOIN: Keep all features, disambiguate duplicates with suffix

        Args:
            parent_results: List of FeaturePropagationResult from parent nodes.
                Must contain at least one result. Order matters for FULL_OUTER_JOIN
                disambiguation.
            merge_type: Merge strategy - "rows" or "columns"
            column_option: Column handling for COLUMNS merge:
                - "inner_join_duplicate_column": Intersection of features
                - "full_outer_join": Union with disambiguation
                - None: Defaults to union behavior

        Returns:
            Dict mapping feature names to FeatureMetadata objects. The returned
            features represent the merged feature set available after the merge.

        Merge Behavior Details:
            ROWS merge:
                - Combines all features from all parents
                - No disambiguation needed (vertical stack)
                - Result = parent1_features UNION parent2_features UNION ...

            COLUMNS + INNER_JOIN:
                - Keeps only features present in ALL parents
                - Join key (id) is always included
                - Result = parent1_features INTERSECT parent2_features INTERSECT ... UNION {id}

            COLUMNS + FULL_OUTER_JOIN:
                - Keeps all features from all parents
                - Duplicate feature names get suffix: feature_0, feature_1, etc.
                - Join key (id) is never duplicated
                - Result = all features with disambiguation

        Example (ROWS merge):
            ```python
            parent1_features = {"id": meta1, "content": meta2}
            parent2_features = {"id": meta3, "metadata": meta4}

            result = propagator.merge_features(
                parent_results=[result1, result2],
                merge_type="rows",
                column_option=None
            )
            # Result: {"id": meta1, "content": meta2, "metadata": meta4}
            ```

        Example (COLUMNS + INNER_JOIN):
            ```python
            parent1_features = {"id": meta1, "content": meta2, "title": meta3}
            parent2_features = {"id": meta4, "content": meta5, "author": meta6}

            result = propagator.merge_features(
                parent_results=[result1, result2],
                merge_type="columns",
                column_option="inner_join_duplicate_column"
            )
            # Result: {"id": meta1, "content": meta2}  # Only common features
            ```

        Example (COLUMNS + FULL_OUTER_JOIN):
            ```python
            parent1_features = {"id": meta1, "content": meta2}
            parent2_features = {"id": meta3, "content": meta4}

            result = propagator.merge_features(
                parent_results=[result1, result2],
                merge_type="columns",
                column_option="full_outer_join"
            )
            # Result: {"id": meta1, "content_0": meta2, "content_1": meta4}
            ```

        Note:
            - The join key is always "id" (OperatorConstants.Columns.ID)
            - Empty parent_results returns empty dict
            - Feature metadata is taken from first parent containing the feature
            - Disambiguation suffixes are 0-indexed based on parent order

        See Also:
            - _apply_special_case_logic: Calls this method for Merge operator
            - OperatorConstants.Merge: Merge type and option constants
        """
        if not parent_results:
            return {}

        join_key = OperatorConstants.Columns.ID

        if merge_type == OperatorConstants.Merge.ROWS:
            # Merge all features from all parents
            merged_features: dict[str, FeatureMetadata] = {}
            for parent in parent_results:
                merged_features.update(parent.feature_metadata)
            return merged_features

        if merge_type == OperatorConstants.Merge.COLUMNS:
            if column_option == OperatorConstants.Columns.INNER_JOIN_DUPLICATE_COLUMN:
                # Find common features across all parents
                common_features = set(parent_results[0].feature_metadata.keys())
                for parent in parent_results[1:]:
                    common_features.intersection_update(parent.feature_metadata.keys())
                common_features.add(join_key)

                # Build intersected features dict
                intersected_features: dict[str, FeatureMetadata] = {}
                for feature in common_features:
                    for parent in parent_results:
                        if feature in parent.feature_metadata:
                            intersected_features[feature] = parent.feature_metadata[feature]
                            break
                return intersected_features

            if column_option == OperatorConstants.Merge.FULL_OUTER_JOIN:
                # Count feature occurrences across parents (excluding join key)
                feature_counts: dict[str, int] = {}
                for parent in parent_results:
                    for feature in parent.feature_metadata:
                        if feature != join_key:
                            feature_counts[feature] = feature_counts.get(feature, 0) + 1

                # Build merged features with disambiguation
                merged_outer_features: dict[str, FeatureMetadata] = {}
                for index, parent in enumerate(parent_results):
                    for feature, meta in parent.feature_metadata.items():
                        if feature == join_key:
                            merged_outer_features[feature] = meta
                        elif feature_counts[feature] > 1:
                            merged_outer_features[f"{feature}_{index}"] = meta
                        else:
                            merged_outer_features[feature] = meta

                return merged_outer_features

        # Fallback: merge all features
        fallback_merged_features: dict[str, FeatureMetadata] = {}
        for parent in parent_results:
            fallback_merged_features.update(parent.feature_metadata)
        return fallback_merged_features
