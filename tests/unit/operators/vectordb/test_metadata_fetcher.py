"""Unit tests for VectorDB metadata fetcher.

Covers:
- compute_default_feature_mappings() — all 5 enterprise mapping rules
- VectorDBMetadataFetcher._normalise_feature_mappings() — three input formats
- VectorDBMetadataFetcher._default_feature_mappings_from_features() — wraps compute_
- VectorDBMetadataFetcher._empty_result() — five-key fallback
- VectorDBMetadataFetcher.fetch_metadata() — routing: opensearch delegates, unknown warns
- OpenSearchResourceMetadata._is_supported() — four logic branches
- OpenSearchResourceMetadata._stored_metadata() — _meta priority chain
- OpenSearchResourceMetadata._resolve_feature_mappings() — four sources priority chain
"""

from unittest.mock import MagicMock, patch

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.vectordb.adapters.outbound.opensearch.resource_metadata import (
    OpenSearchResourceMetadata,
)
from docpipe.core.operators.vectordb.metadata_fetcher import (
    VectorDBMetadataFetcher,
    compute_default_feature_mappings,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _feature(
    *,
    available_for_vector_db: bool = True,
    is_primary: bool = False,
    tags: list[str] | None = None,
    type_: str = "string",
) -> dict:
    f: dict = {
        OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: available_for_vector_db,
        OperatorConstants.Misc.IS_PRIMARY: is_primary,
        OperatorConstants.Misc.TAGS: tags or [],
        OperatorConstants.Misc.TYPE: type_,
    }
    return f


# ---------------------------------------------------------------------------
# compute_default_feature_mappings — Rule 1: primary → "pk"
# ---------------------------------------------------------------------------


class TestComputeDefaultFeatureMappingsRule1Primary:
    """Rule 1: is_primary=True → "pk" (flow JSON format)."""

    def test_is_primary_true_maps_to_pk(self):
        feats = {"doc_hash": _feature(is_primary=True)}
        result = compute_default_feature_mappings(feats)
        assert result["doc_hash"] == "pk"

    def test_primary_tag_maps_to_pk(self):
        """Propagator snapshot format: 'primary' in tags list."""
        feats = {"doc_hash": _feature(tags=["primary"])}
        result = compute_default_feature_mappings(feats)
        assert result["doc_hash"] == "pk"

    def test_only_first_primary_is_mapped(self):
        """Only one feature should get the 'pk' mapping even if two are marked primary."""
        feats = {
            "a": _feature(is_primary=True),
            "b": _feature(is_primary=True),
        }
        pk_values = [v for v in compute_default_feature_mappings(feats).values() if v == "pk"]
        assert len(pk_values) == 1

    def test_non_primary_not_mapped_to_pk(self):
        feats = {"content": _feature()}
        result = compute_default_feature_mappings(feats)
        assert result.get("content") != "pk"


# ---------------------------------------------------------------------------
# compute_default_feature_mappings — Rule 2: "id" → "document_id"
# ---------------------------------------------------------------------------


class TestComputeDefaultFeatureMappingsRule2Id:
    """Rule 2: feature named 'id' → 'document_id'."""

    def test_id_feature_maps_to_document_id(self):
        feats = {OperatorConstants.Columns.ID: _feature()}
        result = compute_default_feature_mappings(feats)
        assert result[OperatorConstants.Columns.ID] == "document_id"

    def test_id_already_primary_skips_document_id(self):
        """If 'id' is also the primary feature, it is already consumed by Rule 1."""
        feats = {OperatorConstants.Columns.ID: _feature(is_primary=True)}
        result = compute_default_feature_mappings(feats)
        # Rule 1 maps it to "pk"; Rule 2 must NOT override to "document_id"
        assert result[OperatorConstants.Columns.ID] == "pk"


# ---------------------------------------------------------------------------
# compute_default_feature_mappings — Rule 3: "name" → "document_name"
# ---------------------------------------------------------------------------


class TestComputeDefaultFeatureMappingsRule3Name:
    """Rule 3: feature named 'name' → 'document_name'."""

    def test_name_feature_maps_to_document_name(self):
        feats = {OperatorConstants.Columns.NAME: _feature()}
        result = compute_default_feature_mappings(feats)
        assert result[OperatorConstants.Columns.NAME] == "document_name"

    def test_name_already_primary_skips_document_name(self):
        feats = {OperatorConstants.Columns.NAME: _feature(is_primary=True)}
        result = compute_default_feature_mappings(feats)
        assert result[OperatorConstants.Columns.NAME] == "pk"


# ---------------------------------------------------------------------------
# compute_default_feature_mappings — Rule 4: first vector → "vector_embeddings"
# ---------------------------------------------------------------------------


class TestComputeDefaultFeatureMappingsRule4Vector:
    """Rule 4: first feature with type=vector → 'vector_embeddings'."""

    def test_vector_feature_maps_to_vector_embeddings(self):
        feats = {"embeddings": _feature(type_=OperatorConstants.Types.TYPE_VECTOR)}
        result = compute_default_feature_mappings(feats)
        assert result["embeddings"] == "vector_embeddings"

    def test_only_first_vector_feature_gets_special_mapping(self):
        feats = {
            "vec1": _feature(type_=OperatorConstants.Types.TYPE_VECTOR),
            "vec2": _feature(type_=OperatorConstants.Types.TYPE_VECTOR),
        }
        result = compute_default_feature_mappings(feats)
        vec_embedding_values = [k for k, v in result.items() if v == "vector_embeddings"]
        assert len(vec_embedding_values) == 1

    def test_non_vector_type_not_mapped_to_vector_embeddings(self):
        feats = {"content": _feature(type_="string")}
        result = compute_default_feature_mappings(feats)
        assert result.get("content") != "vector_embeddings"


# ---------------------------------------------------------------------------
# compute_default_feature_mappings — Rule 5: remaining available → identity
# ---------------------------------------------------------------------------


class TestComputeDefaultFeatureMappingsRule5Identity:
    """Rule 5: remaining features with available_for_vector_db=True → identity mapping."""

    def test_available_feature_maps_to_itself(self):
        feats = {"title": _feature(available_for_vector_db=True)}
        result = compute_default_feature_mappings(feats)
        assert result.get("title") == "title"

    def test_unavailable_feature_excluded(self):
        feats = {"internal_flag": _feature(available_for_vector_db=False)}
        result = compute_default_feature_mappings(feats)
        assert "internal_flag" not in result

    def test_empty_features_returns_empty_dict(self):
        assert compute_default_feature_mappings({}) == {}


# ---------------------------------------------------------------------------
# compute_default_feature_mappings — combined scenarios
# ---------------------------------------------------------------------------


class TestComputeDefaultFeatureMappingsCombined:
    """Full enterprise feature set exercises all five rules at once."""

    def test_full_feature_set_all_rules_applied(self):
        feats = {
            "doc_hash": _feature(is_primary=True, available_for_vector_db=True),
            OperatorConstants.Columns.ID: _feature(available_for_vector_db=True),
            OperatorConstants.Columns.NAME: _feature(available_for_vector_db=True),
            "embeddings": _feature(type_=OperatorConstants.Types.TYPE_VECTOR, available_for_vector_db=True),
            "content": _feature(available_for_vector_db=True),
        }
        result = compute_default_feature_mappings(feats)

        assert result["doc_hash"] == "pk"
        assert result[OperatorConstants.Columns.ID] == "document_id"
        assert result[OperatorConstants.Columns.NAME] == "document_name"
        assert result["embeddings"] == "vector_embeddings"
        assert result["content"] == "content"


# ---------------------------------------------------------------------------
# VectorDBMetadataFetcher._normalise_feature_mappings
# ---------------------------------------------------------------------------


class TestNormaliseFeatureMappings:
    """_normalise_feature_mappings converts three raw formats to list[dict]."""

    def test_dict_input_converted_to_list_of_dicts(self):
        raw = {"feat_a": "col_a", "feat_b": "col_b"}
        result = VectorDBMetadataFetcher._normalise_feature_mappings(raw)
        assert {"feature_name": "feat_a", "mapped_column_name": "col_a"} in result
        assert {"feature_name": "feat_b", "mapped_column_name": "col_b"} in result
        assert len(result) == 2

    def test_list_of_dicts_with_feature_name_key_passed_through(self):
        raw = [{"feature_name": "feat_a", "mapped_column_name": "col_a"}]
        result = VectorDBMetadataFetcher._normalise_feature_mappings(raw)
        assert result == [{"feature_name": "feat_a", "mapped_column_name": "col_a"}]

    def test_list_of_lists_converted_to_list_of_dicts(self):
        raw = [["feat_a", "col_a"], ["feat_b", "col_b"]]
        result = VectorDBMetadataFetcher._normalise_feature_mappings(raw)
        assert {"feature_name": "feat_a", "mapped_column_name": "col_a"} in result
        assert {"feature_name": "feat_b", "mapped_column_name": "col_b"} in result

    def test_empty_dict_returns_empty_list(self):
        assert VectorDBMetadataFetcher._normalise_feature_mappings({}) == []

    def test_empty_list_returns_empty_list(self):
        assert VectorDBMetadataFetcher._normalise_feature_mappings([]) == []

    def test_none_returns_empty_list(self):
        assert VectorDBMetadataFetcher._normalise_feature_mappings(None) == []

    def test_list_of_tuples_converted_to_list_of_dicts(self):
        raw = [("feat_a", "col_a")]
        result = VectorDBMetadataFetcher._normalise_feature_mappings(raw)
        assert result == [{"feature_name": "feat_a", "mapped_column_name": "col_a"}]


# ---------------------------------------------------------------------------
# VectorDBMetadataFetcher._empty_result
# ---------------------------------------------------------------------------


class TestEmptyResult:
    """_empty_result returns five-key fallback dict."""

    def test_empty_result_has_all_five_keys(self):
        result = VectorDBMetadataFetcher._empty_result()
        assert OperatorConstants.VectorDB.AVAILABLE_RESOURCES in result
        assert OperatorConstants.VectorDB.SELECTED_RESOURCE_SCHEMA in result
        assert OperatorConstants.VectorDB.FEATURE_MAPPINGS_RESPONSE in result
        assert OperatorConstants.VectorDB.IS_DOCPIPE_SUPPORTED_RESOURCE in result
        assert OperatorConstants.VectorDB.STORED_RESOURCE_METADATA in result

    def test_empty_result_defaults_are_empty_or_none(self):
        result = VectorDBMetadataFetcher._empty_result()
        assert result[OperatorConstants.VectorDB.AVAILABLE_RESOURCES] == []
        assert result[OperatorConstants.VectorDB.SELECTED_RESOURCE_SCHEMA] == {}
        assert result[OperatorConstants.VectorDB.FEATURE_MAPPINGS_RESPONSE] == []
        assert result[OperatorConstants.VectorDB.IS_DOCPIPE_SUPPORTED_RESOURCE] == {}
        stored = result[OperatorConstants.VectorDB.STORED_RESOURCE_METADATA]
        assert stored["vector_similarity"] is None
        assert stored["dimension_size"] is None


# ---------------------------------------------------------------------------
# VectorDBMetadataFetcher.fetch_metadata — routing
# ---------------------------------------------------------------------------


class TestFetchMetadataRouting:
    """fetch_metadata delegates to the right adapter or falls back on unknown."""

    def test_unknown_adapter_returns_empty_result(self):
        fetcher = VectorDBMetadataFetcher()
        result = fetcher.fetch_metadata(
            adapter_name="unknown_db",
            operator_config={},
            available_features={},
        )
        assert result == VectorDBMetadataFetcher._empty_result()

    def test_opensearch_delegates_to_opensearch_resource_metadata(self):
        fetcher = VectorDBMetadataFetcher()
        expected = VectorDBMetadataFetcher._empty_result()

        # OpenSearchResourceMetadata is lazy-imported inside fetch_metadata; patch it
        # at its definition location (not the metadata_fetcher module).
        with patch(
            "docpipe.core.operators.vectordb.adapters.outbound.opensearch.resource_metadata.OpenSearchResourceMetadata"
        ) as mock_cls:
            mock_instance = MagicMock()
            mock_instance.fetch.return_value = expected
            mock_cls.return_value = mock_instance

            result = fetcher.fetch_metadata(
                adapter_name=OperatorConstants.VectorDB.OPENSEARCH,
                operator_config={OperatorConstants.Config.PROVIDER_CONFIG: {"host": "localhost"}},
                available_features={},
            )

        assert result is expected
        mock_instance.fetch.assert_called_once()

    def test_unknown_adapter_logs_warning(self):
        fetcher = VectorDBMetadataFetcher()
        with patch("docpipe.core.operators.vectordb.metadata_fetcher.logger") as mock_logger:
            fetcher.fetch_metadata(
                adapter_name="milvus",
                operator_config={},
                available_features={},
            )
        mock_logger.warning.assert_called_once()
        # logger.warning uses %s-style: args[0] is the format string, args[1:] are substitutions
        call_args = mock_logger.warning.call_args[0]
        assert any("milvus" in str(a) for a in call_args)


# ---------------------------------------------------------------------------
# OpenSearchResourceMetadata._is_supported
# ---------------------------------------------------------------------------


class TestIsSupported:
    """_is_supported mirrors enterprise is_datasift_supported_index logic."""

    def test_empty_index_name_is_supported(self):
        result = OpenSearchResourceMetadata._is_supported(index_name="", available_resources=[], client=MagicMock())
        assert result["supported"] is True

    def test_index_not_in_resources_is_supported(self):
        result = OpenSearchResourceMetadata._is_supported(
            index_name="new_index", available_resources=["other_index"], client=MagicMock()
        )
        assert result["supported"] is True
        assert result["index_name"] == "new_index"

    def test_existing_index_with_knn_vector_is_supported(self):
        mock_client = MagicMock()
        mock_client.indices.get_mapping.return_value = {
            "my_index": {
                "mappings": {
                    "properties": {"vector_embeddings": {"type": OperatorConstants.VectorDB.SCHEMA_KEY_KNN_VECTOR}}
                }
            }
        }
        result = OpenSearchResourceMetadata._is_supported(
            index_name="my_index", available_resources=["my_index"], client=mock_client
        )
        assert result["supported"] is True

    def test_existing_index_without_knn_vector_is_not_supported(self):
        mock_client = MagicMock()
        mock_client.indices.get_mapping.return_value = {
            "my_index": {"mappings": {"properties": {"title": {"type": "text"}}}}
        }
        result = OpenSearchResourceMetadata._is_supported(
            index_name="my_index", available_resources=["my_index"], client=mock_client
        )
        assert result["supported"] is False
        assert "reason" in result

    def test_mapping_exception_returns_unsupported(self):
        mock_client = MagicMock()
        mock_client.indices.get_mapping.side_effect = Exception("connection refused")
        result = OpenSearchResourceMetadata._is_supported(
            index_name="my_index", available_resources=["my_index"], client=mock_client
        )
        assert result["supported"] is False


# ---------------------------------------------------------------------------
# OpenSearchResourceMetadata._stored_metadata
# ---------------------------------------------------------------------------


class TestStoredMetadata:
    """_stored_metadata reads from _meta first, falls back to knn_vector field."""

    def test_reads_from_meta_block_when_present(self):
        mapping = {
            "idx": {
                "mappings": {
                    "_meta": {"vector_similarity": "cosine", "dimension_size": 768},
                    "properties": {},
                }
            }
        }
        result = OpenSearchResourceMetadata._stored_metadata(index_name="idx", mapping=mapping)
        assert result["vector_similarity"] == "cosine"
        assert result["dimension_size"] == 768

    def test_falls_back_to_knn_vector_field_when_meta_absent(self):
        mapping = {
            "idx": {
                "mappings": {
                    "properties": {
                        "vec": {
                            "type": OperatorConstants.VectorDB.SCHEMA_KEY_KNN_VECTOR,
                            "dimension": 512,
                            "method": {"space_type": "l2"},
                        }
                    }
                }
            }
        }
        result = OpenSearchResourceMetadata._stored_metadata(index_name="idx", mapping=mapping)
        assert result["vector_similarity"] == "l2"
        assert result["dimension_size"] == 512

    def test_returns_none_when_neither_source_present(self):
        mapping: dict = {"idx": {"mappings": {"properties": {}}}}
        result = OpenSearchResourceMetadata._stored_metadata(index_name="idx", mapping=mapping)
        assert result["vector_similarity"] is None
        assert result["dimension_size"] is None


# ---------------------------------------------------------------------------
# OpenSearchResourceMetadata._resolve_feature_mappings — priority chain
# ---------------------------------------------------------------------------


class TestResolveFeatureMappings:
    """_resolve_feature_mappings follows the four-source priority chain."""

    def _call(
        self,
        *,
        operator_config: dict | None = None,
        available_features: dict | None = None,
        index_name: str = "",
        available_resources: list | None = None,
        client: MagicMock | None = None,
    ) -> list:
        return OpenSearchResourceMetadata._resolve_feature_mappings(
            operator_config=operator_config or {},
            available_features=available_features or {},
            index_name=index_name,
            available_resources=available_resources or [],
            client=client or MagicMock(),
            normalise_feature_mappings=VectorDBMetadataFetcher._normalise_feature_mappings,
            default_feature_mappings_from_features=VectorDBMetadataFetcher._default_feature_mappings_from_features,
        )

    def test_source1_opensearch_feature_mappings_takes_priority(self):
        config = {
            OperatorConstants.VectorDB.OPENSEARCH_FEATURE_MAPPINGS: {"feat": "col"},
            OperatorConstants.Config.FEATURE_MAPPINGS: {"other": "other_col"},
        }
        result = self._call(operator_config=config)
        assert result == [{"feature_name": "feat", "mapped_column_name": "col"}]

    def test_source2_generic_feature_mappings_fallback(self):
        config = {OperatorConstants.Config.FEATURE_MAPPINGS: {"feat": "col"}}
        result = self._call(operator_config=config)
        assert result == [{"feature_name": "feat", "mapped_column_name": "col"}]

    def test_source3_meta_stored_mappings_used_when_index_exists(self):
        mock_client = MagicMock()
        mock_client.indices.get_mapping.return_value = {
            "my_index": {"mappings": {"_meta": {OperatorConstants.Config.FEATURE_MAPPINGS: {"feat": "col"}}}}
        }
        result = self._call(
            index_name="my_index",
            available_resources=["my_index"],
            client=mock_client,
        )
        assert result == [{"feature_name": "feat", "mapped_column_name": "col"}]

    def test_source4_defaults_from_available_features_when_no_saved(self):
        feats = {OperatorConstants.Columns.ID: _feature(available_for_vector_db=True)}
        result = self._call(available_features=feats)
        assert any(d["mapped_column_name"] == "document_id" for d in result)

    def test_empty_fallback_when_no_features_and_no_config(self):
        result = self._call()
        assert result == []
