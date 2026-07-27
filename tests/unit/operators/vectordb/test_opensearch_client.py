#!/usr/bin/env python3
"""
Unit tests for OpenSearchClient
"""

import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.credentials import Credentials

from docpipe.core.operators.vectordb.adapters.outbound.opensearch.client import OpenSearchClient
from docpipe.exceptions.docpipe_exceptions import DocpipeException


class TestOpenSearchClientInitialization:
    """Test client initialization and parameter validation"""

    def test_basic_initialization(self):
        """Test basic client initialization with default parameters"""
        client = OpenSearchClient(host="localhost", port=9200)

        assert client.host == "localhost"
        assert client.port == 9200
        assert client.use_ssl is True
        assert client.verify_certs is True
        assert client.aws_auth is False
        assert client.timeout == 60
        assert client._client is None
        assert client._version is None

    def test_initialization_with_custom_parameters(self):
        """Test initialization with custom parameters"""
        client = OpenSearchClient(
            host="opensearch.example.com",
            port=443,
            username="admin",
            password=os.environ.get("TEST_OPENSEARCH_PASSWORD", "test-os-pw"),
            use_ssl=True,
            verify_certs=False,
            timeout=120,
        )

        assert client.host == "opensearch.example.com"
        assert client.port == 443
        assert client.username == "admin"
        assert client.password == os.environ.get("TEST_OPENSEARCH_PASSWORD", "test-os-pw")
        assert client.use_ssl is True
        assert client.verify_certs is False
        assert client.timeout == 120

    def test_initialization_with_aws_auth(self):
        """Test initialization with AWS authentication"""
        client = OpenSearchClient(
            host="search-domain.us-east-1.es.amazonaws.com",
            port=443,
            aws_auth=True,
            aws_region="us-east-1",
        )

        assert client.aws_auth is True
        assert client.aws_region == "us-east-1"


class TestParameterValidation:
    """Test connection parameter validation"""

    def test_missing_host_raises_error(self):
        """Test that missing host raises DocpipeException"""
        client = OpenSearchClient(host="", port=9200)

        with pytest.raises(DocpipeException, match="host is required"):
            client.connect()

    def test_none_host_raises_error(self):
        """Test that None host raises DocpipeException"""
        client = OpenSearchClient(host=None, port=9200)

        with pytest.raises(DocpipeException, match="host is required"):
            client.connect()

    def test_invalid_port_type_raises_error(self):
        """Test that non-integer port raises DocpipeException"""
        client = OpenSearchClient(host="localhost", port="9200")

        with pytest.raises(DocpipeException, match="port must be an integer"):
            client.connect()

    def test_port_below_range_raises_error(self):
        """Test that port below valid range raises DocpipeException"""
        client = OpenSearchClient(host="localhost", port=0)

        with pytest.raises(DocpipeException, match="port must be between 1 and 65535"):
            client.connect()

    def test_port_above_range_raises_error(self):
        """Test that port above valid range raises DocpipeException"""
        client = OpenSearchClient(host="localhost", port=65536)

        with pytest.raises(DocpipeException, match="port must be between 1 and 65535"):
            client.connect()

    def test_aws_auth_without_region_raises_error(self):
        """Test that AWS auth without region raises DocpipeException"""
        client = OpenSearchClient(
            host="localhost",
            port=9200,
            aws_auth=True,
            aws_region=None,
        )

        with pytest.raises(DocpipeException, match="aws_region is required when aws_auth is enabled"):
            client.connect()


class TestConnectionSetup:
    """Test connection setup with different authentication methods"""

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_connect_with_basic_auth(self, mock_opensearch):
        """Test connection with username/password authentication"""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(
            host="localhost",
            port=9200,
            username="admin",
            password=os.environ.get("TEST_OPENSEARCH_PASSWORD", "test-os-pw"),
            use_ssl=False,
            verify_certs=False,
        )

        result = client.connect()

        assert result == mock_client
        mock_opensearch.assert_called_once()
        call_kwargs = mock_opensearch.call_args[1]
        assert call_kwargs["http_auth"] == ("admin", os.environ.get("TEST_OPENSEARCH_PASSWORD", "test-os-pw"))
        assert call_kwargs["use_ssl"] is False
        assert call_kwargs["verify_certs"] is False

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.boto3.Session")
    def test_connect_with_aws_auth(self, mock_session, mock_opensearch):
        """Test connection with AWS IAM authentication"""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        # Mock AWS credentials
        mock_credentials = Mock(spec=Credentials)
        mock_session.return_value.get_credentials.return_value = mock_credentials

        client = OpenSearchClient(
            host="search-domain.us-east-1.es.amazonaws.com",
            port=443,
            aws_auth=True,
            aws_region="us-east-1",
        )

        result = client.connect()

        assert result == mock_client
        mock_opensearch.assert_called_once()
        call_kwargs = mock_opensearch.call_args[1]
        assert "http_auth" in call_kwargs
        assert call_kwargs["use_ssl"] is True

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_connect_without_auth(self, mock_opensearch):
        """Test connection without authentication"""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(host="localhost", port=9200, use_ssl=False)

        result = client.connect()

        assert result == mock_client
        mock_opensearch.assert_called_once()
        call_kwargs = mock_opensearch.call_args[1]
        assert "http_auth" not in call_kwargs

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_connect_with_ssl_settings(self, mock_opensearch):
        """Test connection with SSL settings"""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(
            host="localhost",
            port=9200,
            use_ssl=True,
            verify_certs=True,
        )

        client.connect()

        call_kwargs = mock_opensearch.call_args[1]
        assert call_kwargs["use_ssl"] is True
        assert call_kwargs["verify_certs"] is True

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_connect_with_custom_timeout(self, mock_opensearch):
        """Test connection with custom timeout"""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(host="localhost", port=9200, timeout=120)

        client.connect()

        call_kwargs = mock_opensearch.call_args[1]
        assert call_kwargs["timeout"] == 120


class TestClientLifecycle:
    """Test client lifecycle management"""

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_get_client_creates_if_none(self, mock_opensearch):
        """Test get_client creates client if not exists"""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(host="localhost", port=9200)

        result = client.get_client()

        assert result == mock_client
        assert client._client == mock_client

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_get_client_reuses_existing(self, mock_opensearch):
        """Test get_client reuses existing client"""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(host="localhost", port=9200)

        # First call creates client
        result1 = client.get_client()
        # Second call should reuse
        result2 = client.get_client()

        assert result1 == result2
        mock_opensearch.assert_called_once()

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_close_client(self, mock_opensearch):
        """Test closing client connection"""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(host="localhost", port=9200)
        client.connect()

        client.close()

        mock_client.close.assert_called_once()
        assert client._client is None
        assert client._version is None

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_close_handles_errors(self, mock_opensearch):
        """Test close handles errors gracefully"""
        mock_client = MagicMock()
        mock_client.close.side_effect = Exception("Close error")
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(host="localhost", port=9200)
        client.connect()

        # Should not raise exception
        client.close()

        assert client._client is None


class TestVersionDetection:
    """Test OpenSearch version detection"""

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_get_version_success(self, mock_opensearch):
        """Test successful version detection"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(host="localhost", port=9200)

        version = client.get_version()

        assert version == (2, 11, 0)
        assert client._version == (2, 11, 0)

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_get_version_caches_result(self, mock_opensearch):
        """Test version is cached after first call"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(host="localhost", port=9200)

        version1 = client.get_version()
        version2 = client.get_version()

        assert version1 == version2
        mock_client.info.assert_called_once()

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_get_version_handles_missing_info(self, mock_opensearch):
        """Test version detection with missing version info"""
        mock_client = MagicMock()
        mock_client.info.return_value = {}
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(host="localhost", port=9200)

        version = client.get_version()

        assert version == (0, 0, 0)

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_get_version_handles_error(self, mock_opensearch):
        """Test version detection handles errors"""
        mock_client = MagicMock()
        mock_client.info.side_effect = Exception("Connection error")
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(host="localhost", port=9200)

        version = client.get_version()

        assert version == (0, 0, 0)

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_get_version_parses_different_formats(self, mock_opensearch):
        """Test version parsing with different version formats"""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(host="localhost", port=9200)

        # Test with patch version
        mock_client.info.return_value = {"version": {"number": "2.11.1"}}
        assert client.get_version() == (2, 11, 1)

        # Reset cache
        client._version = None

        # Test with major.minor.patch format
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        version = client.get_version()
        assert version == (2, 11, 0)


class TestConnectionTesting:
    """Test connection testing functionality"""

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_connection_test_success(self, mock_opensearch):
        """Test successful connection test"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(host="localhost", port=9200)

        result = client.test_connection()

        assert result is True
        mock_client.info.assert_called_once()

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_connection_test_failure(self, mock_opensearch):
        """Test connection test failure"""
        mock_client = MagicMock()
        mock_client.info.side_effect = Exception("Connection refused")
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(host="localhost", port=9200)

        result = client.test_connection()

        assert result is False

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_connection_test_network_error(self, mock_opensearch):
        """Test connection test with network error"""
        mock_client = MagicMock()
        mock_client.info.side_effect = ConnectionError("Network unreachable")
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(host="localhost", port=9200)

        result = client.test_connection()

        assert result is False


class TestEdgeCases:
    """Test edge cases and error scenarios"""

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_whitespace_only_host(self, mock_opensearch):
        """Test that whitespace-only host is rejected"""
        client = OpenSearchClient(host="   ", port=9200)

        with pytest.raises(DocpipeException, match="host must be a non-empty string"):
            client.connect()

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_reconnect_after_close(self, mock_opensearch):
        """Test reconnecting after closing connection"""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        client = OpenSearchClient(host="localhost", port=9200)

        # Connect, close, then reconnect
        client.connect()
        client.close()
        result = client.get_client()

        assert result == mock_client
        assert mock_opensearch.call_count == 2

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.boto3.Session")
    def test_aws_auth_with_none_credentials(self, mock_session, mock_opensearch):
        """Test AWS auth when credentials are None raises error"""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client
        mock_session.return_value.get_credentials.return_value = None

        client = OpenSearchClient(
            host="localhost",
            port=9200,
            aws_auth=True,
            aws_region="us-east-1",
        )

        # Should raise DocpipeException when credentials are None
        with pytest.raises(DocpipeException, match="Credentials cannot be empty"):
            client.connect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
