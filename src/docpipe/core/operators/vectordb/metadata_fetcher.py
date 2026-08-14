"""Fetches live metadata from VectorDB connections for flow enrichment.

Used by FlowEnrichmentService to populate available_resources,
selected_resource_schema, feature_mappings, is_docpipe_supported_resource,
and stored_resource_metadata on vectordb operator nodes during flow enrichment.

All adapter-specific logic lives in the adapter layer:
  - OpenSearch: adapters/outbound/opensearch/resource_metadata.py
"""

from __future__ import annotations

from typing import Any

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


def compute_default_feature_mappings(available_features: dict[str, Any]) -> dict[str, str]:
    """Compute default feature-to-column mappings when none are provided by the user.

    Returns a dict[str, str] in execution format {feature_name: mapped_column_name},
    which is what VectorDBOperator and the index_manager consume.

    Mirrors enterprise get_default_feature_mappings_for_new_index() /
    get_default_feature_mappings_for_any_new_store():

      1. Feature with is_primary=True OR tagged "primary"  → "pk"
      2. "id"                                              → "document_id"   (hardcoded)
      3. "name"                                            → "document_name" (hardcoded)
      4. First feature with type="vector"                  → "vector_embeddings"
      5. Remaining available_for_vector_db=True features   → identity mapping

    The primary check handles two formats:
    - Flow JSON config: ``"is_primary": True`` (set directly on the feature dict)
    - Propagator snapshot: ``"primary"`` tag in the ``"tags"`` list
    """
    result: dict[str, str] = {}
    covered: set[str] = set()

    # Rule 1 — primary feature → "pk"
    for name, meta in available_features.items():
        is_primary = meta.get(OperatorConstants.Misc.IS_PRIMARY, False) or (
            OperatorConstants.Misc.PRIMARY in meta.get(OperatorConstants.Misc.TAGS, [])
        )
        if is_primary:
            result[name] = "pk"
            covered.add(name)
            break

    # Rule 2 — "id" → "document_id"
    if OperatorConstants.Columns.ID in available_features and OperatorConstants.Columns.ID not in covered:
        result[OperatorConstants.Columns.ID] = "document_id"
        covered.add(OperatorConstants.Columns.ID)

    # Rule 3 — "name" → "document_name"
    if OperatorConstants.Columns.NAME in available_features and OperatorConstants.Columns.NAME not in covered:
        result[OperatorConstants.Columns.NAME] = "document_name"
        covered.add(OperatorConstants.Columns.NAME)

    # Rule 4 — first feature with type=vector → "vector_embeddings"
    for name, meta in available_features.items():
        if name not in covered and meta.get(OperatorConstants.Misc.TYPE) == OperatorConstants.Types.TYPE_VECTOR:
            result[name] = "vector_embeddings"
            covered.add(name)
            break

    # Rule 5 — remaining available_for_vector_db=True → identity mapping
    for name, meta in available_features.items():
        if name not in covered and meta.get(OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB, False):
            result[name] = name
            covered.add(name)

    return result


class VectorDBMetadataFetcher:
    """Thin router — dispatches metadata fetch requests to adapter-specific fetchers.

    Each adapter's read-only metadata logic lives in its own module:
      - opensearch: adapters/outbound/opensearch/resource_metadata.OpenSearchResourceMetadata

    This class owns only the shared helpers (_normalise_feature_mappings,
    _default_feature_mappings_from_features, _empty_result) and injects them
    into each adapter fetcher so the normalisation logic stays in one place.

    Never raises. All connection failures are caught by the adapter fetcher and
    return the empty-value fallback dict (five keys, all empty/None).
    """

    def fetch_metadata(
        self,
        *,
        adapter_name: str,
        operator_config: dict[str, Any],
        available_features: dict[str, Any],
    ) -> dict[str, Any]:
        """Fetch all VectorDB metadata for one operator node.

        Args:
            adapter_name: Value of operator_config["provider"] — e.g. "opensearch".
            operator_config: Full operator config dict from the DAG snapshot.
                Connection parameters are in operator_config["provider_config"].
                Resource name (index_name) is at the top level.
            available_features: Propagated feature map from the DAG snapshot.
                Used as the Source 4 fallback for feature_mappings derivation.

        Returns:
            Dict with five normalised keys. Never raises — returns empty-value
            defaults on any connection failure or unknown adapter.
        """
        provider_config = operator_config.get(OperatorConstants.Config.PROVIDER_CONFIG, {})

        if adapter_name == OperatorConstants.VectorDB.OPENSEARCH:
            from docpipe.core.operators.vectordb.adapters.outbound.opensearch.resource_metadata import (
                OpenSearchResourceMetadata,
            )

            return OpenSearchResourceMetadata().fetch(
                provider_config=provider_config,
                operator_config=operator_config,
                available_features=available_features,
                normalise_feature_mappings=self._normalise_feature_mappings,
                default_feature_mappings_from_features=self._default_feature_mappings_from_features,
                empty_result=self._empty_result,
            )

        if adapter_name == OperatorConstants.VectorDB.MILVUS:
            from docpipe.core.operators.vectordb.adapters.outbound.milvus.resource_metadata import (
                MilvusResourceMetadata,
            )

            return MilvusResourceMetadata().fetch(
                provider_config=provider_config,
                operator_config=operator_config,
                available_features=available_features,
                normalise_feature_mappings=self._normalise_feature_mappings,
                default_feature_mappings_from_features=self._default_feature_mappings_from_features,
                empty_result=self._empty_result,
            )

        logger.warning("No metadata fetcher for VectorDB adapter: %s", adapter_name)
        return self._empty_result()

    # ------------------------------------------------------------------
    # Shared helpers — injected into adapter fetchers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_feature_mappings(raw: Any) -> list[dict[str, str]]:
        """Normalise feature mappings to list-of-dicts format.

        Handles three input formats:
          Old list-of-lists: [["feature_name", "col_name"], ...]
          New list-of-dicts: [{"feature_name": "...", "mapped_column_name": "..."}, ...]
          Dict (stored in _meta): {"feature_name": "col_name", ...}
        """
        if isinstance(raw, dict):
            return [{"feature_name": k, "mapped_column_name": v} for k, v in raw.items()]
        if isinstance(raw, list):
            normalised = []
            for item in raw:
                if isinstance(item, dict) and "feature_name" in item:
                    normalised.append(item)
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    normalised.append({"feature_name": item[0], "mapped_column_name": item[1]})
            return normalised
        return []

    @staticmethod
    def _default_feature_mappings_from_features(
        available_features: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Derive default feature mappings in list[dict] format for the API/UI response.

        Delegates to compute_default_feature_mappings() and converts dict→list.
        """
        return [
            {"feature_name": k, "mapped_column_name": v}
            for k, v in compute_default_feature_mappings(available_features).items()
        ]

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        """Return safe empty-value defaults for all five metadata keys."""
        return {
            OperatorConstants.VectorDB.AVAILABLE_RESOURCES: [],
            OperatorConstants.VectorDB.SELECTED_RESOURCE_SCHEMA: {},
            OperatorConstants.VectorDB.FEATURE_MAPPINGS_RESPONSE: [],
            OperatorConstants.VectorDB.IS_DOCPIPE_SUPPORTED_RESOURCE: {},
            OperatorConstants.VectorDB.STORED_RESOURCE_METADATA: {
                "vector_similarity": None,
                "dimension_size": None,
            },
        }
