"""Unit tests for Milvus client."""

import os
from unittest.mock import Mock, patch

import pytest

from docpipe.core.operators.vectordb.adapters.outbound.milvus.client import MilvusClient
from docpipe.exceptions.docpipe_exceptions import DocpipeException


class TestMilvusClient:
    """Test cases for MilvusClient."""

    def test_init_with_host(self):
        """Test initialization with host and port."""
        client = MilvusClient(host="localhost", port=19530, auth_type="standalone")
        assert client.host == "localhost"
        assert client.port == 19530
        assert client.uri is None

    def test_init_with_uri(self):
        """Test initialization with URI."""
        client = MilvusClient(uri="http://localhost:19530", auth_type="uri")
        assert client.uri == "http://localhost:19530"
        assert client.host is None

    def test_validate_parameters_no_host_or_uri(self):
        """Test validation fails when neither host nor URI is provided."""
        client = MilvusClient(host=None, uri=None, auth_type="standalone")
        with pytest.raises(DocpipeException) as exc_info:
            client._validate_parameters()
        assert "'host' is required for standalone auth_type" in str(exc_info.value)

    def test_validate_parameters_invalid_port(self):
        """Test validation fails with invalid port."""
        client = MilvusClient(host="localhost", port=70000, auth_type="standalone")
        with pytest.raises(DocpipeException) as exc_info:
            client._validate_parameters()
        assert "'port' must be an integer between 1 and 65535" in str(exc_info.value)

    def test_validate_parameters_token_and_password(self):
        """Test validation that token auth doesn't require username/password."""
        # Token auth requires host, not URI
        client = MilvusClient(
            host="localhost",
            port=19530,
            token="test-token",
            username="user",
            password=os.environ.get("TEST_MILVUS_PASSWORD", "test-milvus-pw"),
            auth_type="token",
        )
        client._validate_parameters()

    @patch("docpipe.core.operators.vectordb.adapters.outbound.milvus.client.PyMilvusClient")
    def test_connect_with_host(self, mock_pymilvus_client):
        """Test connection with host-based configuration (standalone).
        PyMilvusClient only accepts uri, not host/port — client constructs uri from host/port.
        """
        mock_client_instance = Mock()
        mock_client_instance.list_collections.return_value = []
        mock_pymilvus_client.return_value = mock_client_instance

        client = MilvusClient(host="localhost", port=19530, auth_type="standalone")
        result = client.connect()

        assert result == mock_client_instance
        mock_pymilvus_client.assert_called_once()
        call_kwargs = mock_pymilvus_client.call_args[1]
        assert "host" not in call_kwargs
        assert "port" not in call_kwargs
        assert call_kwargs["uri"] == "http://localhost:19530"
        assert "token" not in call_kwargs

    @patch("docpipe.core.operators.vectordb.adapters.outbound.milvus.client.PyMilvusClient")
    def test_connect_with_uri(self, mock_pymilvus_client):
        """Test connection with pre-constructed URI configuration."""
        mock_client_instance = Mock()
        mock_client_instance.list_collections.return_value = []
        mock_pymilvus_client.return_value = mock_client_instance

        client = MilvusClient(uri="http://localhost:19530", auth_type="uri")
        result = client.connect()

        assert result == mock_client_instance
        mock_pymilvus_client.assert_called_once()
        call_kwargs = mock_pymilvus_client.call_args[1]
        assert call_kwargs["uri"] == "http://localhost:19530"
        assert "token" not in call_kwargs

    @patch("docpipe.core.operators.vectordb.adapters.outbound.milvus.client.PyMilvusClient")
    def test_connect_failure(self, mock_pymilvus_client):
        """Test connection failure handling."""
        mock_pymilvus_client.side_effect = Exception("Connection failed")

        client = MilvusClient(host="localhost", auth_type="standalone")
        with pytest.raises(DocpipeException) as exc_info:
            client.connect()
        assert "MilvusDB Error: Failed to connect" in str(exc_info.value)

    @patch("docpipe.core.operators.vectordb.adapters.outbound.milvus.client.PyMilvusClient")
    def test_get_client_creates_if_none(self, mock_pymilvus_client):
        """Test get_client creates client if not exists."""
        mock_client_instance = Mock()
        mock_client_instance.list_collections.return_value = []
        mock_pymilvus_client.return_value = mock_client_instance

        client = MilvusClient(host="localhost", auth_type="standalone")
        result = client.get_client()

        assert result == mock_client_instance
        assert client._client == mock_client_instance

    @patch("docpipe.core.operators.vectordb.adapters.outbound.milvus.client.PyMilvusClient")
    def test_get_client_returns_existing(self, mock_pymilvus_client):
        """Test get_client returns existing client."""
        mock_client_instance = Mock()
        mock_client_instance.list_collections.return_value = []
        mock_pymilvus_client.return_value = mock_client_instance

        client = MilvusClient(host="localhost", auth_type="standalone")
        client._client = mock_client_instance
        result = client.get_client()

        assert result == mock_client_instance
        # Should not create a new client
        mock_pymilvus_client.assert_not_called()

    @patch("docpipe.core.operators.vectordb.adapters.outbound.milvus.client.PyMilvusClient")
    def test_test_connection_success(self, mock_pymilvus_client):
        """Test successful connection test."""
        mock_client_instance = Mock()
        mock_client_instance.list_collections.return_value = []
        mock_pymilvus_client.return_value = mock_client_instance

        client = MilvusClient(host="localhost", auth_type="standalone")
        result = client.test_connection()

        assert result is True

    @patch("docpipe.core.operators.vectordb.adapters.outbound.milvus.client.PyMilvusClient")
    def test_test_connection_failure(self, mock_pymilvus_client):
        """Test failed connection test."""
        mock_client_instance = Mock()
        mock_client_instance.list_collections.side_effect = Exception("Connection error")
        mock_pymilvus_client.return_value = mock_client_instance

        client = MilvusClient(host="localhost", auth_type="standalone")
        result = client.test_connection()

        assert result is False

    def test_close(self):
        """Test closing the client connection."""
        mock_client_instance = Mock()
        client = MilvusClient(host="localhost")
        client._client = mock_client_instance

        client.close()

        mock_client_instance.close.assert_called_once()
        assert client._client is None

    def test_close_with_error(self):
        """Test closing with error doesn't raise exception."""
        mock_client_instance = Mock()
        mock_client_instance.close.side_effect = Exception("Close error")
        client = MilvusClient(host="localhost")
        client._client = mock_client_instance

        # Should not raise exception
        client.close()
        assert client._client is None
