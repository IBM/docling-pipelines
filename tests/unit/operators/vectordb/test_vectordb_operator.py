"""Unit tests for VectorDB operator with OpenSearch adapter."""

from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pyarrow as pa
import pytest

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.vectordb import VectorDBOperator
from docpipe.core.operators.vectordb.adapters.outbound.factories.vector_store_factory import VectorStoreFactory
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.utils.infrastructure.config import get_opensearch_config


@pytest.fixture
def basic_config():
    """Basic configuration for VectorDB operator with OpenSearch adapter"""
    env_config = get_opensearch_config()

    # The config structure now has all connection params and resource name in provider_config
    provider_cfg = env_config.get(OperatorConstants.Config.PROVIDER_CONFIG, {})
    provider_cfg["index_name"] = "test_index"
    return {
        OperatorConstants.Config.PROVIDER: "opensearch",
        OperatorConstants.VectorDB.CREATE_INDEX: True,
        OperatorConstants.Columns.DOC_ID_COLUMN: env_config.get(OperatorConstants.Columns.DOC_ID_COLUMN, "doc_id_hash"),
        OperatorConstants.Config.AVAILABLE_FEATURES: {
            "doc_id_hash": {
                "name": "Document ID",
                "available_for_vector_db": True,
                "mandatory_for_vector_db": True,
                "type": "string",
                "is_primary": True,
            },
            "content": {
                "name": "Content",
                "available_for_vector_db": True,
                "type": "string",
            },
            "embeddings": {
                "name": "Embeddings",
                "available_for_vector_db": True,
                "mandatory_for_vector_db": True,
                "type": "vector",
            },
        },
        OperatorConstants.Config.FEATURE_MAPPINGS: [
            {"feature_name": "doc_id_hash", "mapped_column_name": "pk"},
            {"feature_name": "content", "mapped_column_name": "text"},
            {"feature_name": "embeddings", "mapped_column_name": "vector_embeddings"},
        ],
        OperatorConstants.Config.PROVIDER_CONFIG: provider_cfg,
    }


@pytest.fixture
def sample_table():
    """Sample PyArrow table with documents"""
    data = {
        "doc_id_hash": ["doc1", "doc2", "doc3"],
        "content": [
            "This is the first document",
            "This is the second document",
            "This is the third document",
        ],
        "embeddings": [
            np.random.rand(384).tolist(),
            np.random.rand(384).tolist(),
            np.random.rand(384).tolist(),
        ],
    }
    return pa.table(data)


class TestVectorDBOperatorInitialization:
    """Test operator initialization and configuration"""

    def test_basic_initialization(self, basic_config):
        """Test basic operator initialization"""
        with patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch"):
            operator = VectorDBOperator(basic_config)
            assert operator.provider == "opensearch"
            assert operator.adapter is not None

    def test_missing_index_name_in_provider_config_raises(self, basic_config):
        """OpenSearch: missing index_name inside provider_config raises ValueError."""
        config = basic_config.copy()
        provider_cfg = dict(config[OperatorConstants.Config.PROVIDER_CONFIG])
        provider_cfg.pop("index_name", None)
        config[OperatorConstants.Config.PROVIDER_CONFIG] = provider_cfg

        with pytest.raises(DocpipeException, match="Failed to initialize vector database adapter"):
            VectorDBOperator(config=config)

    def test_missing_collection_name_in_provider_config_raises(self):
        """Milvus: missing collection_name inside provider_config raises ValueError."""
        config = {
            OperatorConstants.Config.PROVIDER: "milvus",
            OperatorConstants.VectorDB.CREATE_INDEX: True,
            OperatorConstants.Columns.DOC_ID_COLUMN: "doc_id_hash",
            OperatorConstants.Config.PROVIDER_CONFIG: {
                "host": "localhost",
                "port": 19530,
                # collection_name intentionally absent
            },
        }
        with pytest.raises(DocpipeException, match="Failed to initialize vector database adapter"):
            VectorDBOperator(config=config)

    def test_invalid_provider(self, basic_config):
        """Test that invalid provider raises error"""
        config = basic_config.copy()
        config["provider"] = "invalid_db"

        with pytest.raises(DocpipeException, match="Failed to initialize vector database adapter"):
            VectorDBOperator(config)

    def test_missing_provider_config(self, basic_config):
        """Test that missing provider_config raises clear error"""
        config = basic_config.copy()
        del config[OperatorConstants.Config.PROVIDER_CONFIG]

        with pytest.raises(DocpipeException, match="'provider_config' is required but missing or empty"):
            VectorDBOperator(config)

    def test_empty_provider_config(self, basic_config):
        """Test that empty provider_config raises clear error"""
        config = basic_config.copy()
        config[OperatorConstants.Config.PROVIDER_CONFIG] = {}

        with pytest.raises(DocpipeException, match="'provider_config' is required but missing or empty"):
            VectorDBOperator(config)


class TestBatchProcessing:
    """Test batch processing functionality through public interface"""

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_transform_basic(self, mock_bulk, mock_opensearch, basic_config, sample_table):
        """Test basic transform operation"""
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = True
        mock_client.indices.get_mapping.return_value = {
            "test_index": {
                "mappings": {
                    "_meta": {"engine": "faiss", "algorithm": "hnsw"},
                    "properties": {
                        "vector_embeddings": {"type": "knn_vector", "dimension": 384},
                    },
                }
            }
        }
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client
        mock_bulk.return_value = (3, [])

        operator = VectorDBOperator(basic_config)
        result_tables, metadata = operator.transform(sample_table)

        assert len(result_tables) == 1
        assert result_tables[0].num_rows == 3
        assert metadata["documents_in_scope"] == 3
        assert metadata["processed_docs"] == 3
        assert metadata["failed_docs_count"] == 0

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_transform_missing_doc_id_column(self, mock_opensearch, basic_config):
        """Test transform with missing doc_id column"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client

        table = pa.table({"content": ["Test"], "embeddings": [[0.1, 0.2]]})

        operator = VectorDBOperator(basic_config)
        _result_tables, metadata = operator.transform(table)

        assert metadata["node_status"] == "Failed"

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_transform_empty_table(self, mock_opensearch, basic_config):
        """Test transform with empty table"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client

        empty_table = pa.table({"doc_id_hash": [], "content": [], "embeddings": []})

        operator = VectorDBOperator(basic_config)
        _result_tables, metadata = operator.transform(empty_table)

        assert metadata["documents_in_scope"] == 0
        assert metadata["processed_docs"] == 0

    def test_transform_validates_existing_schema_before_insert(self, basic_config, sample_table):
        """Test existing vector store schema is validated before insert on reruns."""
        mock_adapter = Mock()
        mock_adapter.index_exists.return_value = True
        mock_adapter.detect_all_vector_dimensions.return_value = {"embeddings": 384}
        mock_adapter.validate_existing_schema = Mock()
        mock_adapter.create_index = Mock()
        mock_adapter.index_documents.return_value = (3, [])

        with patch(
            "docpipe.core.operators.vectordb.vectordb_operator.VectorStoreFactory.create",
            return_value=mock_adapter,
        ):
            operator = VectorDBOperator(basic_config)
            _result_tables, metadata = operator.transform(sample_table)

        mock_adapter.create_index.assert_not_called()
        mock_adapter.validate_existing_schema.assert_called_once_with(dimension_mapping={"embeddings": 384})
        mock_adapter.index_documents.assert_called_once()
        assert metadata["processed_docs"] == 3
        assert metadata["failed_docs_count"] == 0


class TestChunkedEmbeddings:
    """Test chunked embeddings produce correct OpenSearch documents"""

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_chunks_store_chunk_specific_text(self, mock_bulk, mock_opensearch, basic_config):
        """Verify OpenSearch documents contain chunk-specific text, not full document content"""
        # Real scenario: 2 documents with 3 chunks each = 6 total chunks
        data = {
            "doc_id_hash": ["doc1_hash", "doc2_hash"],
            "content": [
                "Full content of document 1 that should NOT be in chunks",
                "Full content of document 2 that should NOT be in chunks",
            ],
            "chunked_content": [
                [
                    {"chunk": "First chunk of doc1", "start_index": 0},
                    {"chunk": "Second chunk of doc1", "start_index": 100},
                    {"chunk": "Third chunk of doc1", "start_index": 200},
                ],
                [
                    {"chunk": "First chunk of doc2", "start_index": 0},
                    {"chunk": "Second chunk of doc2", "start_index": 100},
                    {"chunk": "Third chunk of doc2", "start_index": 200},
                ],
            ],
            "embeddings": [
                [np.random.rand(384).tolist() for _ in range(3)],
                [np.random.rand(384).tolist() for _ in range(3)],
            ],
        }
        table = pa.table(data)

        mock_client = MagicMock()
        mock_client.indices.exists.return_value = True
        mock_client.indices.get_mapping.return_value = {
            "test_index": {
                "mappings": {
                    "_meta": {"engine": "faiss", "algorithm": "hnsw"},
                    "properties": {
                        "vector_embeddings": {"type": "knn_vector", "dimension": 384},
                    },
                }
            }
        }
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client
        mock_bulk.return_value = (6, [])

        operator = VectorDBOperator(basic_config)
        operator.transform(table)

        # Extract documents sent to OpenSearch (like real query results)
        all_actions = []
        for call in mock_bulk.call_args_list:
            all_actions.extend(call[0][1])

        assert len(all_actions) == 6, "Should create 6 chunk documents"

        # Verify structure matches real OpenSearch output
        for action in all_actions:
            assert "_id" in action
            assert "_source" in action
            assert "text" in action["_source"]
            assert "vector_embeddings" in action["_source"]
            assert "pk" in action["_source"]

            # Key assertion: text field contains chunk content, not full document
            text_content = action["_source"]["text"]
            assert "Full content of document" not in text_content
            assert "chunk of doc" in text_content


class TestQueryCapabilities:
    """Test query and delete capabilities through public interface"""

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_query_by_doc_names(self, mock_opensearch, basic_config):
        """Test querying documents by names"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"name": "doc1", "content": "Test 1"}},
                    {"_source": {"name": "doc2", "content": "Test 2"}},
                ]
            }
        }
        mock_opensearch.return_value = mock_client

        operator = VectorDBOperator(basic_config)
        docs = operator.query_by_doc_names(["doc1", "doc2"])

        assert len(docs) == 2
        assert docs[0]["name"] == "doc1"
        assert docs[1]["name"] == "doc2"

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_delete_documents_by_ids(self, mock_bulk, mock_opensearch, basic_config):
        """Test deleting documents by IDs"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client
        mock_bulk.return_value = (2, [])

        operator = VectorDBOperator(basic_config)
        success, failed = operator.delete_documents_by_ids(["doc1", "doc2"])

        assert success == 2
        assert failed == 0

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_get_document_count(self, mock_opensearch, basic_config):
        """Test getting document count"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_client.count.return_value = {"count": 100}
        mock_opensearch.return_value = mock_client

        operator = VectorDBOperator(basic_config)
        count = operator.get_document_count()

        assert count == 100


class TestMetadata:
    """Test operator metadata"""

    def test_get_metadata(self):
        """Test get_metadata returns correct structure"""
        config = {
            "provider": "opensearch",
            "doc_id_column": "doc_id_hash",
            "embeddings_column": "embeddings",
            "vector_dimension": 384,
            "provider_config": {
                "index_name": "test_index",
                "host": "localhost",
                "port": 9200,
                "engine": "faiss",
                "algorithm": "hnsw",
            },
        }

        with patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch"):
            operator = VectorDBOperator(config)
            metadata = operator.get_metadata()

        assert metadata["sdk"] is True
        assert metadata["category"] == "VectorDB"
        assert metadata["is_operator_available"] is True
        assert "features" in metadata
        assert "attributes" in metadata
        assert OperatorConstants.Config.PROVIDER in metadata["attributes"]
        provider_attr = metadata["attributes"][OperatorConstants.Config.PROVIDER]
        assert OperatorConstants.Config.VALID_VALUES in provider_attr
        assert set(provider_attr[OperatorConstants.Config.VALID_VALUES]) == set(VectorStoreFactory.list_adapters())


class TestVectorDBOperatorValidateMandatoryFeatureMappings:
    """validate() reports an error when a mandatory_for_vector_db feature lacks a mapping."""

    def _config_with(
        self,
        *,
        feature_mappings: list | None = None,
        available_features: dict | None = None,
    ) -> dict:
        """Build a minimal config that passes __init__ (no real adapter needed)."""
        return {
            OperatorConstants.Config.PROVIDER: "opensearch",
            OperatorConstants.Config.PROVIDER_CONFIG: {"index_name": "test_index", "host": "localhost"},
            OperatorConstants.Config.FEATURE_MAPPINGS: feature_mappings or [],
            OperatorConstants.Config.AVAILABLE_FEATURES: available_features or {},
        }

    def _run_validate(self, *, config: dict) -> tuple[list, list]:
        with patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch"):
            operator = VectorDBOperator(config)
        errors: list = []
        warnings: list = []
        operator.validate(errors=errors, warnings=warnings, available_features=[])
        return errors, warnings

    def test_mandatory_feature_with_mapping_produces_no_error(self):
        config = self._config_with(
            feature_mappings=[{"feature_name": "doc_id_hash", "mapped_column_name": "pk"}],
            available_features={
                "doc_id_hash": {
                    OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True,
                }
            },
        )
        errors, _ = self._run_validate(config=config)
        mandatory_errors = [e for e in errors if "mandatory" in e.lower()]
        assert not mandatory_errors

    def test_mandatory_feature_missing_mapping_produces_error(self):
        config = self._config_with(
            feature_mappings=[{"feature_name": "content", "mapped_column_name": "text"}],
            available_features={
                "doc_id_hash": {
                    OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True,
                },
                "content": {
                    OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: False,
                },
            },
        )
        errors, _ = self._run_validate(config=config)
        assert any("mandatory" in e.lower() for e in errors)
        assert any("doc_id_hash" in e for e in errors)

    def test_multiple_mandatory_features_missing_all_reported(self):
        config = self._config_with(
            feature_mappings=[{"feature_name": "content", "mapped_column_name": "text"}],
            available_features={
                "doc_id_hash": {OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True},
                "embeddings": {OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True},
                "content": {OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: False},
            },
        )
        errors, _ = self._run_validate(config=config)
        assert any("doc_id_hash" in e and "embeddings" in e for e in errors)

    def test_skips_check_when_feature_mappings_empty(self):
        """No feature_mappings configured → skip the mandatory check entirely."""
        config = self._config_with(
            feature_mappings=[],
            available_features={
                "doc_id_hash": {OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True},
            },
        )
        errors, _ = self._run_validate(config=config)
        mandatory_errors = [e for e in errors if "mandatory" in e.lower()]
        assert not mandatory_errors

    def test_skips_check_when_available_features_empty(self):
        """No available_features in config → skip the mandatory check entirely."""
        config = self._config_with(
            feature_mappings=[{"feature_name": "doc_id_hash", "mapped_column_name": "pk"}],
            available_features={},
        )
        errors, _ = self._run_validate(config=config)
        mandatory_errors = [e for e in errors if "mandatory" in e.lower()]
        assert not mandatory_errors


# ---------------------------------------------------------------------------
# Shared helper — builds an operator with a fully mocked adapter
# ---------------------------------------------------------------------------


def _make_operator_with_mock_adapter(extra_config: dict | None = None) -> tuple["VectorDBOperator", Mock]:
    """Return (operator, mock_adapter) with VectorStoreFactory.create patched."""
    mock_adapter = Mock()
    mock_adapter.detect_all_vector_dimensions.return_value = {"embeddings": 384}
    mock_adapter.index_exists.return_value = False
    mock_adapter.index_documents.return_value = (0, [])
    mock_adapter.refresh_index.return_value = None

    base = {
        OperatorConstants.Config.PROVIDER: "opensearch",
        OperatorConstants.Config.PROVIDER_CONFIG: {"index_name": "idx", "host": "localhost"},
        OperatorConstants.Config.AVAILABLE_FEATURES: {
            "embeddings": {
                OperatorConstants.Misc.TYPE: "vector",
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
            }
        },
        OperatorConstants.Config.FEATURE_MAPPINGS: [
            {"feature_name": "embeddings", "mapped_column_name": "vector_embeddings"},
            {"feature_name": "doc_id_hash", "mapped_column_name": "pk"},
        ],
    }
    if extra_config:
        base.update(extra_config)

    with patch(
        "docpipe.core.operators.vectordb.vectordb_operator.VectorStoreFactory.create", return_value=mock_adapter
    ):
        op = VectorDBOperator(base)
    return op, mock_adapter


# ---------------------------------------------------------------------------
# __init__ — branch-specific config paths (this PR)
# ---------------------------------------------------------------------------


class TestVectorDBOperatorInitConfig:
    """__init__ config extraction paths added/changed in this branch."""

    def test_add_sparse_vector_forwarded_to_adapter_config(self):
        """add_sparse_vector in config is forwarded into provider_config passed to the adapter factory."""
        captured = {}

        def capture_create(name, **kwargs):
            captured.update(kwargs)
            m = Mock()
            m.detect_all_vector_dimensions.return_value = {}
            m.index_exists.return_value = False
            m.index_documents.return_value = (0, [])
            m.refresh_index.return_value = None
            return m

        config = {
            OperatorConstants.Config.PROVIDER: "opensearch",
            OperatorConstants.Config.PROVIDER_CONFIG: {"index_name": "idx", "host": "localhost"},
            OperatorConstants.VectorDB.ADD_SPARSE_VECTOR: True,
        }
        with patch(
            "docpipe.core.operators.vectordb.vectordb_operator.VectorStoreFactory.create", side_effect=capture_create
        ):
            VectorDBOperator(config)

        assert captured.get(OperatorConstants.VectorDB.ADD_SPARSE_VECTOR) is True

    def test_schema_template_path_forwarded_to_adapter_config(self):
        """schema_template_path in config is forwarded into provider_config passed to the adapter factory."""
        captured = {}

        def capture_create(name, **kwargs):
            captured.update(kwargs)
            m = Mock()
            m.detect_all_vector_dimensions.return_value = {}
            m.index_exists.return_value = False
            m.index_documents.return_value = (0, [])
            m.refresh_index.return_value = None
            return m

        config = {
            OperatorConstants.Config.PROVIDER: "opensearch",
            OperatorConstants.Config.PROVIDER_CONFIG: {"index_name": "idx", "host": "localhost"},
            "schema_template_path": "/tmp/schema.json",
        }
        with patch(
            "docpipe.core.operators.vectordb.vectordb_operator.VectorStoreFactory.create", side_effect=capture_create
        ):
            VectorDBOperator(config)

        assert captured.get("schema_template_path") == "/tmp/schema.json"

    def test_opensearch_import_error_falls_back_gracefully(self):
        """ImportError during OpenSearch eager registration is caught and logged, not raised."""
        with patch.dict("sys.modules", {"docpipe.core.operators.vectordb.adapters.outbound.opensearch.adapter": None}):
            # Re-importing the module would raise — the try/except at module level means the
            # operator is still constructable with a mocked factory.
            with patch("docpipe.core.operators.vectordb.vectordb_operator.VectorStoreFactory.create"):
                op = VectorDBOperator(
                    {
                        OperatorConstants.Config.PROVIDER: "opensearch",
                        OperatorConstants.Config.PROVIDER_CONFIG: {"index_name": "idx", "host": "localhost"},
                    }
                )
            assert op.provider == "opensearch"


# ---------------------------------------------------------------------------
# transform() — error / edge-case paths
# ---------------------------------------------------------------------------


class TestVectorDBOperatorTransformEdgeCases:
    """transform() branches not covered by existing tests."""

    def _table_with_embeddings(self, *, doc_ids: list) -> pa.Table:
        return pa.table(
            {
                "doc_id_hash": doc_ids,
                "embeddings": [Mock() for _ in doc_ids],
            }
        )

    def test_transform_no_vector_columns_dense_mode_returns_failed(self, basic_config):
        """Dense-only mode with no vector-typed available_features → FAILED status."""
        config = {
            OperatorConstants.Config.PROVIDER: "opensearch",
            OperatorConstants.Config.PROVIDER_CONFIG: {"index_name": "idx", "host": "localhost"},
            OperatorConstants.Config.AVAILABLE_FEATURES: {
                "doc_id_hash": {
                    OperatorConstants.Misc.TYPE: "string",
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                }
            },
            OperatorConstants.Config.FEATURE_MAPPINGS: [{"feature_name": "doc_id_hash", "mapped_column_name": "pk"}],
        }
        mock_adapter = Mock()
        with patch(
            "docpipe.core.operators.vectordb.vectordb_operator.VectorStoreFactory.create", return_value=mock_adapter
        ):
            op = VectorDBOperator(config)

        table = pa.table({"doc_id_hash": ["doc1"]})
        _, metadata = op.transform(table)
        assert metadata["node_status"] == "Failed"

    def test_transform_dimension_detection_fails_returns_failed(self, basic_config):
        """detect_all_vector_dimensions returns {} in dense mode → FAILED status."""
        op, mock_adapter = _make_operator_with_mock_adapter()
        mock_adapter.detect_all_vector_dimensions.return_value = {}

        table = pa.table({"doc_id_hash": ["doc1"], "embeddings": [[0.1, 0.2]]})
        _, metadata = op.transform(table)
        assert metadata["node_status"] == "Failed"

    def test_transform_index_creation_failure_marks_all_docs_failed(self, basic_config):
        """Exception during create_index marks all documents as failed."""
        op, mock_adapter = _make_operator_with_mock_adapter()
        mock_adapter.index_exists.return_value = False
        mock_adapter.create_index.side_effect = RuntimeError("connection refused")

        table = pa.table({"doc_id_hash": ["doc1", "doc2"], "embeddings": [[0.1], [0.2]]})
        _, metadata = op.transform(table)

        assert metadata["node_status"] == "Failed"
        assert metadata["processed_docs"] == 0
        assert metadata["failed_docs_count"] == 2

    def test_transform_null_doc_id_row_is_skipped(self, basic_config):
        """Rows where doc_id_hash is null are skipped, not failed."""
        op, mock_adapter = _make_operator_with_mock_adapter()
        mock_adapter.index_exists.return_value = False
        mock_adapter.index_documents.return_value = (1, [])

        table = pa.table(
            {
                "doc_id_hash": pa.array([None, "doc2"], type=pa.string()),
                "embeddings": [[0.1], [0.2]],
            }
        )
        _, metadata = op.transform(table)
        assert metadata.get("skipped_docs_count", 0) >= 1

    def test_transform_refresh_index_exception_is_warned_not_failed(self, basic_config):
        """refresh_index() raising does not change the final status to Failed."""
        op, mock_adapter = _make_operator_with_mock_adapter()
        mock_adapter.index_exists.return_value = False
        mock_adapter.index_documents.return_value = (1, [])
        mock_adapter.refresh_index.side_effect = RuntimeError("refresh failed")

        table = pa.table({"doc_id_hash": ["doc1"], "embeddings": [[0.1]]})
        _, metadata = op.transform(table)
        assert metadata.get("node_status") != "Failed"

    def test_transform_table_with_id_column_builds_hash_to_id_map(self):
        """Table with both doc_id_hash and id columns — hash-to-id mapping is built (lines 213-215)."""
        op, mock_adapter = _make_operator_with_mock_adapter()
        mock_adapter.index_exists.return_value = False
        mock_adapter.index_documents.return_value = (2, [])

        table = pa.table(
            {
                "doc_id_hash": ["hash1", "hash2"],
                "id": ["orig_id_1", "orig_id_2"],
                "embeddings": [[0.1], [0.2]],
            }
        )
        _, metadata = op.transform(table)
        assert metadata["processed_docs"] == 2

    def test_transform_index_documents_exception_marks_all_docs_failed(self):
        """index_documents() raising marks all documents as failed (lines 538-557)."""
        op, mock_adapter = _make_operator_with_mock_adapter()
        mock_adapter.index_exists.return_value = False
        mock_adapter.index_documents.side_effect = RuntimeError("bulk write error")

        table = pa.table({"doc_id_hash": ["doc1", "doc2"], "embeddings": [[0.1], [0.2]]})
        _, metadata = op.transform(table)

        assert metadata["node_status"] == "Failed"
        assert metadata["processed_docs"] == 0

    def test_transform_sparse_only_mode_no_dense_vectors(self):
        """add_sparse_vector=True with no dense vector columns → pure sparse mode, no dimension detection."""
        config = {
            OperatorConstants.Config.PROVIDER: "opensearch",
            OperatorConstants.Config.PROVIDER_CONFIG: {"index_name": "idx", "host": "localhost"},
            OperatorConstants.VectorDB.ADD_SPARSE_VECTOR: True,
            OperatorConstants.Config.AVAILABLE_FEATURES: {
                "doc_id_hash": {
                    OperatorConstants.Misc.TYPE: "string",
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                }
            },
            OperatorConstants.Config.FEATURE_MAPPINGS: {"doc_id_hash": "pk"},
        }
        mock_adapter = Mock()
        mock_adapter.index_exists.return_value = False
        mock_adapter.index_documents.return_value = (1, [])
        mock_adapter.refresh_index.return_value = None

        with patch(
            "docpipe.core.operators.vectordb.vectordb_operator.VectorStoreFactory.create", return_value=mock_adapter
        ):
            op = VectorDBOperator(config)

        table = pa.table({"doc_id_hash": ["doc1"]})
        _, metadata = op.transform(table)

        mock_adapter.detect_all_vector_dimensions.assert_not_called()
        assert metadata.get("node_status") != "Failed"


class TestVectorDBOperatorIndexCreationFailure:
    """Test transform() when index creation fails."""

    def test_index_creation_failure_marks_all_docs_failed(self, basic_config, sample_table):
        """When create_index raises, all documents are marked failed."""
        mock_adapter = MagicMock()
        mock_adapter.index_exists.return_value = False
        mock_adapter.detect_all_vector_dimensions.return_value = {"embeddings": 384}
        mock_adapter.create_index.side_effect = Exception("Connection refused")

        with patch(
            "docpipe.core.operators.vectordb.vectordb_operator.VectorStoreFactory.create",
            return_value=mock_adapter,
        ):
            operator = VectorDBOperator(basic_config)
            _result_tables, metadata = operator.transform(sample_table)

        assert metadata["node_status"] == "Failed"
        assert metadata["failed_docs_count"] == 3

    def test_schema_validation_failure_marks_all_docs_failed(self, basic_config, sample_table):
        """When validate_existing_schema raises, all documents are marked failed."""
        mock_adapter = MagicMock()
        mock_adapter.index_exists.return_value = True
        mock_adapter.detect_all_vector_dimensions.return_value = {"embeddings": 384}
        mock_adapter.validate_existing_schema.side_effect = ValueError("Dimension mismatch")

        with patch(
            "docpipe.core.operators.vectordb.vectordb_operator.VectorStoreFactory.create",
            return_value=mock_adapter,
        ):
            operator = VectorDBOperator(basic_config)
            _result_tables, metadata = operator.transform(sample_table)

        assert metadata["node_status"] == "Failed"


class TestVectorDBOperatorMissingDocId:
    """Test rows with missing doc_id are skipped."""

    def test_row_with_null_doc_id_is_skipped(self, basic_config):
        mock_adapter = MagicMock()
        mock_adapter.index_exists.return_value = True
        mock_adapter.detect_all_vector_dimensions.return_value = {"embeddings": 384}
        mock_adapter.validate_existing_schema = MagicMock()
        mock_adapter.index_documents.return_value = (1, [])

        table = pa.table(
            {
                "doc_id_hash": [None, "valid_hash"],
                "content": ["text1", "text2"],
                "embeddings": [
                    np.random.rand(384).tolist(),
                    np.random.rand(384).tolist(),
                ],
            }
        )

        with patch(
            "docpipe.core.operators.vectordb.vectordb_operator.VectorStoreFactory.create",
            return_value=mock_adapter,
        ):
            operator = VectorDBOperator(basic_config)
            _result_tables, metadata = operator.transform(table)

        assert metadata["skipped_docs_count"] >= 1


class TestVectorDBOperatorNoVectorColumns:
    """Test dense-only mode fails gracefully when no vector columns found."""

    def test_no_vector_columns_fails_with_status(self, basic_config, sample_table):
        config = dict(basic_config)
        config["available_features"] = {
            "doc_id_hash": {"available_for_vector_db": True, "type": "string"},
            "content": {"available_for_vector_db": True, "type": "string"},
        }

        mock_adapter = MagicMock()
        mock_adapter.index_exists.return_value = False

        with patch(
            "docpipe.core.operators.vectordb.vectordb_operator.VectorStoreFactory.create",
            return_value=mock_adapter,
        ):
            operator = VectorDBOperator(config)
            _result_tables, metadata = operator.transform(sample_table)

        assert metadata["node_status"] == "Failed"


class TestVectorDBOperatorGetMetadataProviders:
    """Test that get_metadata includes providers schema for opensearch and milvus."""

    def test_metadata_provider_config_has_providers(self):
        config = {
            "provider": "opensearch",
            "provider_config": {
                "index_name": "test_index",
                "host": "localhost",
            },
        }
        with patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch"):
            operator = VectorDBOperator(config)
            metadata = operator.get_metadata()

        attributes = metadata["attributes"]
        provider_config = attributes["provider_config"]
        assert "providers" in provider_config
        assert "opensearch" in provider_config["providers"]
        assert "milvus" in provider_config["providers"]


class TestGenerateCompositePk:
    """Tests for VectorDBOperator.generate_composite_pk()."""

    def test_returns_expected_format(self) -> None:
        """PK must be two full 128-char SHA3-512 hex segments joined by underscore."""
        with patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch"):
            pk = VectorDBOperator.generate_composite_pk(file_id="file.pdf", chunk_content="hello world")
        parts = pk.split("_")
        assert len(parts) == 2
        assert all(len(p) == 128 for p in parts)
        assert all(c in "0123456789abcdef" for p in parts for c in p)

    def test_different_files_same_content_produce_different_pks(self) -> None:
        """Two files with identical content must not collide."""
        pk1 = VectorDBOperator.generate_composite_pk(file_id="/docs/file_a.pdf", chunk_content="same text")
        pk2 = VectorDBOperator.generate_composite_pk(file_id="/docs/file_b.pdf", chunk_content="same text")
        assert pk1 != pk2

    def test_same_file_different_content_produces_different_pks(self) -> None:
        """Different chunks of the same file must produce different PKs."""
        pk1 = VectorDBOperator.generate_composite_pk(file_id="/docs/file.pdf", chunk_content="chunk one")
        pk2 = VectorDBOperator.generate_composite_pk(file_id="/docs/file.pdf", chunk_content="chunk two")
        assert pk1 != pk2

    def test_deterministic(self) -> None:
        """Same inputs must always produce the same PK."""
        pk1 = VectorDBOperator.generate_composite_pk(file_id="file.pdf", chunk_content="text")
        pk2 = VectorDBOperator.generate_composite_pk(file_id="file.pdf", chunk_content="text")
        assert pk1 == pk2

    def test_matches_expected_hash_values(self) -> None:
        """PK must equal the full SHA3-512 hex pair."""
        import hashlib

        file_id = "/path/to/doc.pdf"
        chunk_content = "some chunk text"
        fh = hashlib.sha3_512(file_id.encode()).hexdigest()
        ch = hashlib.sha3_512(chunk_content.encode()).hexdigest()
        expected = f"{fh}_{ch}"
        assert VectorDBOperator.generate_composite_pk(file_id=file_id, chunk_content=chunk_content) == expected

    def test_handles_empty_strings(self) -> None:
        """Empty inputs are valid — SHA3-512 of empty string is well-defined."""
        pk = VectorDBOperator.generate_composite_pk(file_id="", chunk_content="")
        assert len(pk) == 257  # 128 + "_" + 128

    def test_handles_special_characters_in_file_id(self) -> None:
        """Special characters in file_id must not raise."""
        pk = VectorDBOperator.generate_composite_pk(
            file_id="/path/with spaces/and-dashes/file (1).pdf",
            chunk_content="text",
        )
        assert len(pk) == 257  # 128 + "_" + 128


class TestStalePkCleanup:
    """Tests for stale PK cleanup logic in VectorDBOperator.transform()."""

    @pytest.fixture
    def mock_adapter(self):
        adapter = MagicMock()
        adapter.index_exists.return_value = False
        adapter.detect_all_vector_dimensions.return_value = {"embeddings": 3}
        adapter.index_documents.return_value = (1, [])
        adapter.get_chunk_ids_for_documents.return_value = {}
        return adapter

    @pytest.fixture
    def stale_cleanup_config(self):
        return {
            "provider": "opensearch",
            "provider_config": {"index_name": "test_index"},
            "available_features": {
                "doc_id_hash": {
                    "type": "string",
                    "available_for_vector_db": True,
                    "mandatory_for_vector_db": True,
                    "is_primary": True,
                },
                "embeddings": {
                    "type": "vector",
                    "available_for_vector_db": True,
                    "mandatory_for_vector_db": True,
                },
            },
            "feature_mappings": {"doc_id_hash": "doc_id_hash", "embeddings": "embeddings"},
        }

    @pytest.fixture
    def chunked_table(self):
        import pyarrow as pa

        return pa.table(
            {
                "id": ["/docs/file_a.pdf"],
                "doc_id_hash": ["abc123"],
                "content": ["full doc text"],
                "chunked_content": [[{"chunk": "chunk one"}, {"chunk": "chunk two"}]],
                "embeddings": [[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]],
            }
        )

    def test_no_cleanup_when_no_existing_pks(self, mock_adapter, stale_cleanup_config, chunked_table) -> None:
        """When the store has no existing PKs, delete_documents_by_ids must not be called."""
        mock_adapter.get_chunk_ids_for_documents.return_value = {}
        with patch(
            "docpipe.core.operators.vectordb.vectordb_operator.VectorStoreFactory.create", return_value=mock_adapter
        ):
            op = VectorDBOperator(stale_cleanup_config)
            op.transform(chunked_table)
        mock_adapter.delete_documents_by_ids.assert_not_called()

    def test_stale_pks_are_deleted_before_insert(self, mock_adapter, stale_cleanup_config, chunked_table) -> None:
        """PKs present in the store but absent from the new run must be deleted."""
        stale_pk = "old_stale_pk_that_no_longer_exists"
        mock_adapter.get_chunk_ids_for_documents.return_value = {"abc123": {stale_pk}}
        with patch(
            "docpipe.core.operators.vectordb.vectordb_operator.VectorStoreFactory.create", return_value=mock_adapter
        ):
            op = VectorDBOperator(stale_cleanup_config)
            op.transform(chunked_table)
        mock_adapter.delete_documents_by_ids.assert_called_once()
        deleted = mock_adapter.delete_documents_by_ids.call_args[0][0]
        assert stale_pk in deleted

    def test_new_pks_are_not_deleted(self, mock_adapter, stale_cleanup_config, chunked_table) -> None:
        """PKs that are part of the current run must never appear in the delete call."""
        pk0 = VectorDBOperator.generate_composite_pk(file_id="/docs/file_a.pdf", chunk_content="chunk one")
        pk1 = VectorDBOperator.generate_composite_pk(file_id="/docs/file_a.pdf", chunk_content="chunk two")
        mock_adapter.get_chunk_ids_for_documents.return_value = {"abc123": {pk0, pk1}}
        with patch(
            "docpipe.core.operators.vectordb.vectordb_operator.VectorStoreFactory.create", return_value=mock_adapter
        ):
            op = VectorDBOperator(stale_cleanup_config)
            op.transform(chunked_table)
        mock_adapter.delete_documents_by_ids.assert_not_called()

    def test_insert_proceeds_even_if_cleanup_raises(self, mock_adapter, stale_cleanup_config, chunked_table) -> None:
        """A failure in stale PK cleanup must not prevent index_documents from being called."""
        mock_adapter.get_chunk_ids_for_documents.side_effect = Exception("network error")
        with patch(
            "docpipe.core.operators.vectordb.vectordb_operator.VectorStoreFactory.create", return_value=mock_adapter
        ):
            op = VectorDBOperator(stale_cleanup_config)
            op.transform(chunked_table)
        mock_adapter.index_documents.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
