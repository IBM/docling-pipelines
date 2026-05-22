#!/usr/bin/env python3
"""
Unit tests for MilvusIndexManager
"""

from unittest.mock import MagicMock

import numpy as np
import pyarrow as pa
import pytest

from datasift.core.operators.vectordb.adapters.outbound.milvus.index_manager import (
    INDEX_DEFAULT_PARAMETERS,
    MilvusIndexManager,
    MilvusIndexTypes,
    MilvusMetricTypes,
)
from datasift.exceptions.datasift_exceptions import DatasiftException


@pytest.fixture
def mock_client():
    """Mock Milvus client"""
    client = MagicMock()
    client.has_collection.return_value = False
    return client


@pytest.fixture
def basic_features():
    """Basic feature configuration"""
    return {
        "doc_id": {
            "name": "Document ID",
            "available_for_vector_db": True,
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
            "type": "vector",
        },
    }


@pytest.fixture
def feature_mappings():
    """Feature mappings"""
    return {
        "doc_id": "pk",
        "content": "text",
        "embeddings": "vector_embeddings",
    }


class TestIndexManagerInitialization:
    """Test index manager initialization"""

    def test_basic_initialization(self, mock_client):
        """Test basic initialization with default parameters"""
        manager = MilvusIndexManager(
            client=mock_client,
            collection_name="test_collection",
        )

        assert manager.client == mock_client
        assert manager.collection_name == "test_collection"
        assert manager.index_type == "HNSW"
        assert manager.metric_type == "L2"
        assert manager.vector_dimension == 384
        assert manager.primary_key_field == "pk"
        assert manager.auto_id is False

    def test_initialization_with_custom_parameters(self, mock_client):
        """Test initialization with custom parameters"""
        manager = MilvusIndexManager(
            client=mock_client,
            collection_name="custom_collection",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            vector_dimension=768,
            primary_key_field="id",
            auto_id=True,
        )

        assert manager.collection_name == "custom_collection"
        assert manager.index_type == "IVF_FLAT"
        assert manager.metric_type == "COSINE"
        assert manager.vector_dimension == 768
        assert manager.primary_key_field == "id"
        assert manager.auto_id is True

    def test_initialization_with_features(self, mock_client, basic_features, feature_mappings):
        """Test initialization with feature configuration"""
        manager = MilvusIndexManager(
            client=mock_client,
            collection_name="test_collection",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        assert manager.available_features == basic_features
        assert manager.feature_mappings == feature_mappings

    def test_initialization_with_custom_index_parameters(self, mock_client):
        """Test initialization with custom index parameters"""
        custom_params = {"M": 32, "efConstruction": 400}
        manager = MilvusIndexManager(
            client=mock_client,
            collection_name="test_collection",
            index_type="HNSW",
            index_parameters=custom_params,
        )

        assert manager.index_parameters == custom_params

    def test_invalid_index_type(self, mock_client):
        """Test initialization with invalid index type"""
        with pytest.raises(DatasiftException) as exc_info:
            MilvusIndexManager(
                client=mock_client,
                collection_name="test_collection",
                index_type="INVALID_TYPE",
            )

        assert "Invalid index type" in str(exc_info.value)
        assert "INVALID_TYPE" in str(exc_info.value)

    def test_invalid_metric_type(self, mock_client):
        """Test initialization with invalid metric type"""
        with pytest.raises(DatasiftException) as exc_info:
            MilvusIndexManager(
                client=mock_client,
                collection_name="test_collection",
                metric_type="INVALID_METRIC",
            )

        assert "Invalid metric type" in str(exc_info.value)
        assert "INVALID_METRIC" in str(exc_info.value)


class TestIndexParameters:
    """Test index parameter handling"""

    def test_get_default_hnsw_parameters(self, mock_client):
        """Test getting default HNSW parameters"""
        manager = MilvusIndexManager(
            client=mock_client,
            collection_name="test_collection",
            index_type="HNSW",
        )

        params = manager._get_index_parameters()
        assert params == {"M": 16, "efConstruction": 200}

    def test_get_default_ivf_flat_parameters(self, mock_client):
        """Test getting default IVF_FLAT parameters"""
        manager = MilvusIndexManager(
            client=mock_client,
            collection_name="test_collection",
            index_type="IVF_FLAT",
        )

        params = manager._get_index_parameters()
        assert params == {"nlist": 128}

    def test_get_default_flat_parameters(self, mock_client):
        """Test getting default FLAT parameters"""
        manager = MilvusIndexManager(
            client=mock_client,
            collection_name="test_collection",
            index_type="FLAT",
        )

        params = manager._get_index_parameters()
        assert params == {}

    def test_custom_parameters_override_defaults(self, mock_client):
        """Test that custom parameters override defaults"""
        custom_params = {"M": 32, "efConstruction": 400}
        manager = MilvusIndexManager(
            client=mock_client,
            collection_name="test_collection",
            index_type="HNSW",
            index_parameters=custom_params,
        )

        params = manager._get_index_parameters()
        assert params == {"M": 32, "efConstruction": 400}

    def test_partial_custom_parameters_merge(self, mock_client):
        """Test that partial custom parameters merge with defaults"""
        custom_params = {"M": 32}
        manager = MilvusIndexManager(
            client=mock_client,
            collection_name="test_collection",
            index_type="HNSW",
            index_parameters=custom_params,
        )

        params = manager._get_index_parameters()
        assert params == {"M": 32, "efConstruction": 200}


class TestCollectionValidation:
    """Test collection validation"""

    def test_collection_exists_check(self, mock_client):
        """Test checking if collection exists"""
        mock_client.has_collection.return_value = True
        manager = MilvusIndexManager(
            client=mock_client,
            collection_name="existing_collection",
        )

        exists = manager.collection_exists()
        assert exists is True
        mock_client.has_collection.assert_called_once_with(collection_name="existing_collection")

    def test_collection_not_exists(self, mock_client):
        """Test checking if collection does not exist"""
        mock_client.has_collection.return_value = False
        manager = MilvusIndexManager(
            client=mock_client,
            collection_name="new_collection",
        )

        exists = manager.collection_exists()
        assert exists is False


class TestVectorDimensionDetection:
    """Test vector dimension detection from PyArrow table"""

    def test_detect_dimension_from_table(self, mock_client):
        """Test detecting vector dimension from PyArrow table using shared utility"""
        from datasift.utils.operators.vectordb_utils import detect_vector_dimension

        # Create table with embeddings
        embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        table = pa.table({"embeddings": embeddings})

        dimension = detect_vector_dimension(table=table, embeddings_column="embeddings")
        assert dimension == 3

    def test_detect_dimension_with_numpy_arrays(self, mock_client):
        """Test detecting dimension with numpy arrays using shared utility"""
        from datasift.utils.operators.vectordb_utils import detect_vector_dimension

        embeddings = [np.array([0.1, 0.2, 0.3, 0.4]), np.array([0.5, 0.6, 0.7, 0.8])]
        table = pa.table({"embeddings": embeddings})

        dimension = detect_vector_dimension(table=table, embeddings_column="embeddings")
        assert dimension == 4

    def test_detect_dimension_missing_column(self, mock_client):
        """Test detecting dimension when embeddings column is missing using shared utility"""
        from datasift.utils.operators.vectordb_utils import detect_vector_dimension

        table = pa.table({"content": ["text1", "text2"]})

        # The method logs a warning and returns None when column is missing
        dimension = detect_vector_dimension(table=table, embeddings_column="embeddings")
        assert dimension is None


class TestMetricTypes:
    """Test metric type constants"""

    def test_all_metric_types_defined(self):
        """Test that all metric types are properly defined"""
        assert MilvusMetricTypes.L2 == "L2"
        assert MilvusMetricTypes.IP == "IP"
        assert MilvusMetricTypes.COSINE == "COSINE"
        assert MilvusMetricTypes.BM25 == "BM25"
        assert len(MilvusMetricTypes.ALL_TYPES) == 4


class TestIndexTypes:
    """Test index type constants"""

    def test_all_index_types_defined(self):
        """Test that all index types are properly defined"""
        assert MilvusIndexTypes.FLAT == "FLAT"
        assert MilvusIndexTypes.IVF_FLAT == "IVF_FLAT"
        assert MilvusIndexTypes.IVF_SQ8 == "IVF_SQ8"
        assert MilvusIndexTypes.IVF_PQ == "IVF_PQ"
        assert MilvusIndexTypes.HNSW == "HNSW"
        assert MilvusIndexTypes.DISKANN == "DISKANN"
        assert MilvusIndexTypes.AUTOINDEX == "AUTOINDEX"
        assert MilvusIndexTypes.SPARSE_INVERTED_INDEX == "SPARSE_INVERTED_INDEX"
        assert MilvusIndexTypes.SPARSE_WAND == "SPARSE_WAND"
        assert len(MilvusIndexTypes.ALL_TYPES) == 9

    def test_default_parameters_for_all_types(self):
        """Test that default parameters exist for all index types"""
        for index_type in MilvusIndexTypes.ALL_TYPES:
            assert index_type in INDEX_DEFAULT_PARAMETERS
