"""Unit tests for OpenSearchService."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from docpipe.api.services.opensearch_service import (
    OpenSearchConfig,
    OpenSearchService,
    get_opensearch_service,
)


class TestOpenSearchConfig:
    """Test OpenSearchConfig validation and settings."""

    def test_config_with_valid_credentials(self):
        """Test configuration with valid credentials."""
        config = OpenSearchConfig(
            opensearch_username="admin",
            opensearch_password="admin123",
            opensearch_host="localhost",
            opensearch_port=9200,
        )
        assert config.opensearch_username == "admin"
        assert config.opensearch_password == "admin123"
        assert config.opensearch_host == "localhost"
        assert config.opensearch_port == 9200

    def test_config_rejects_empty_username(self):
        """Test configuration rejects empty username."""
        with pytest.raises(ValidationError, match="OpenSearch credentials must be provided"):
            OpenSearchConfig(
                opensearch_username="",
                opensearch_password="admin123",
            )

    def test_config_rejects_empty_password(self):
        """Test configuration rejects empty password."""
        with pytest.raises(ValidationError, match="OpenSearch credentials must be provided"):
            OpenSearchConfig(
                opensearch_username="admin",
                opensearch_password="",
            )

    def test_config_rejects_missing_credentials(self):
        """Test configuration rejects missing credentials."""
        with pytest.raises(ValidationError, match="OpenSearch credentials must be provided"):
            OpenSearchConfig()

    def test_config_default_values(self):
        """Test configuration default values."""
        config = OpenSearchConfig(
            opensearch_username="admin",
            opensearch_password="admin123",
        )
        assert config.opensearch_host == "localhost"
        assert config.opensearch_port == 9200
        assert config.opensearch_use_ssl is False
        assert config.opensearch_verify_certs is False
        assert config.opensearch_default_index == "documents"
        assert config.opensearch_timeout == 30
        assert config.opensearch_max_retries == 3

    def test_config_custom_values(self):
        """Test configuration with custom values."""
        config = OpenSearchConfig(
            opensearch_username="admin",
            opensearch_password="admin123",
            opensearch_host="opensearch.example.com",
            opensearch_port=9300,
            opensearch_use_ssl=True,
            opensearch_verify_certs=True,
            opensearch_default_index="custom_index",
            opensearch_timeout=60,
            opensearch_max_retries=5,
        )
        assert config.opensearch_host == "opensearch.example.com"
        assert config.opensearch_port == 9300
        assert config.opensearch_use_ssl is True
        assert config.opensearch_verify_certs is True
        assert config.opensearch_default_index == "custom_index"
        assert config.opensearch_timeout == 60
        assert config.opensearch_max_retries == 5


class TestOpenSearchService:
    """Test OpenSearchService operations."""

    @pytest.fixture
    def valid_config(self):
        """Create valid OpenSearchConfig for testing."""
        return OpenSearchConfig(
            opensearch_username="admin",
            opensearch_password="admin123",
            opensearch_host="localhost",
            opensearch_port=9200,
        )

    @pytest.fixture
    def service(self, *, valid_config):
        """Create OpenSearchService with valid config."""
        return OpenSearchService(config=valid_config)

    def test_service_initialization_with_config(self, *, valid_config):
        """Test service initialization with provided config."""
        service = OpenSearchService(config=valid_config)
        assert service.config == valid_config
        assert service._client is None

    @patch("docpipe.api.services.opensearch_service.OpenSearchConfig")
    def test_service_initialization_without_config(self, *, mock_config_class):
        """Test service initialization loads config from environment."""
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        service = OpenSearchService()

        assert service.config == mock_config
        mock_config_class.assert_called_once()

    @patch("docpipe.api.services.opensearch_service.OpenSearch")
    def test_get_client_creates_new_client(self, *, mock_opensearch_class, service):
        """Test get_client creates new OpenSearch client."""
        mock_client = MagicMock()
        mock_opensearch_class.return_value = mock_client

        client = service.get_client()

        assert client == mock_client
        assert service._client == mock_client
        mock_opensearch_class.assert_called_once_with(
            hosts=[
                {
                    "host": "localhost",
                    "port": 9200,
                }
            ],
            http_auth=("admin", "admin123"),
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30,
            max_retries=3,
            retry_on_timeout=True,
        )

    @patch("docpipe.api.services.opensearch_service.OpenSearch")
    def test_get_client_reuses_existing_client(self, *, mock_opensearch_class, service):
        """Test get_client reuses existing client (connection pooling)."""
        mock_client = MagicMock()
        mock_opensearch_class.return_value = mock_client

        # First call creates client
        client1 = service.get_client()
        # Second call reuses client
        client2 = service.get_client()

        assert client1 == client2
        assert client1 == mock_client
        # OpenSearch constructor called only once
        mock_opensearch_class.assert_called_once()

    @patch("docpipe.api.services.opensearch_service.OpenSearch")
    def test_get_client_raises_on_connection_failure(self, *, mock_opensearch_class, service):
        """Test get_client raises exception on connection failure."""
        mock_opensearch_class.side_effect = Exception("Connection refused")

        with pytest.raises(Exception, match="Connection refused"):
            service.get_client()

    @patch("docpipe.api.services.opensearch_service.OpenSearch")
    def test_health_check_returns_true_for_green_status(self, *, mock_opensearch_class, service):
        """Test health_check returns True for green cluster status."""
        mock_client = MagicMock()
        mock_client.cluster.health.return_value = {"status": "green"}
        mock_opensearch_class.return_value = mock_client

        result = service.health_check()

        assert result is True
        mock_client.cluster.health.assert_called_once()

    @patch("docpipe.api.services.opensearch_service.OpenSearch")
    def test_health_check_returns_true_for_yellow_status(self, *, mock_opensearch_class, service):
        """Test health_check returns True for yellow cluster status."""
        mock_client = MagicMock()
        mock_client.cluster.health.return_value = {"status": "yellow"}
        mock_opensearch_class.return_value = mock_client

        result = service.health_check()

        assert result is True

    @patch("docpipe.api.services.opensearch_service.OpenSearch")
    def test_health_check_returns_false_for_red_status(self, *, mock_opensearch_class, service):
        """Test health_check returns False for red cluster status."""
        mock_client = MagicMock()
        mock_client.cluster.health.return_value = {"status": "red"}
        mock_opensearch_class.return_value = mock_client

        result = service.health_check()

        assert result is False

    @patch("docpipe.api.services.opensearch_service.OpenSearch")
    def test_health_check_returns_false_on_exception(self, *, mock_opensearch_class, service):
        """Test health_check returns False when exception occurs."""
        mock_client = MagicMock()
        mock_client.cluster.health.side_effect = Exception("Connection timeout")
        mock_opensearch_class.return_value = mock_client

        result = service.health_check()

        assert result is False

    @patch("docpipe.api.services.opensearch_service.OpenSearch")
    def test_index_exists_returns_true_when_index_exists(self, *, mock_opensearch_class, service):
        """Test index_exists returns True when index exists."""
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = True
        mock_opensearch_class.return_value = mock_client

        result = service.index_exists(index_name="test_index")

        assert result is True
        mock_client.indices.exists.assert_called_once_with(index="test_index")

    @patch("docpipe.api.services.opensearch_service.OpenSearch")
    def test_index_exists_returns_false_when_index_missing(self, *, mock_opensearch_class, service):
        """Test index_exists returns False when index does not exist."""
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False
        mock_opensearch_class.return_value = mock_client

        result = service.index_exists(index_name="missing_index")

        assert result is False

    @patch("docpipe.api.services.opensearch_service.OpenSearch")
    def test_index_exists_returns_false_on_exception(self, *, mock_opensearch_class, service):
        """Test index_exists returns False when exception occurs."""
        mock_client = MagicMock()
        mock_client.indices.exists.side_effect = Exception("Index check failed")
        mock_opensearch_class.return_value = mock_client

        result = service.index_exists(index_name="test_index")

        assert result is False

    @patch("docpipe.api.services.opensearch_service.OpenSearch")
    def test_close_closes_existing_client(self, *, mock_opensearch_class, service):
        """Test close method closes existing client connection."""
        mock_client = MagicMock()
        mock_opensearch_class.return_value = mock_client

        # Create client first
        service.get_client()
        assert service._client is not None

        # Close it
        service.close()

        mock_client.close.assert_called_once()
        assert service._client is None

    def test_close_does_nothing_when_no_client(self, *, service):
        """Test close method does nothing when no client exists."""
        assert service._client is None

        # Should not raise exception
        service.close()

        assert service._client is None

    @patch("docpipe.api.services.opensearch_service.OpenSearch")
    def test_close_handles_exception_gracefully(self, *, mock_opensearch_class, service):
        """Test close handles exception and still clears client reference."""
        mock_client = MagicMock()
        mock_client.close.side_effect = Exception("Close failed")
        mock_opensearch_class.return_value = mock_client

        service.get_client()
        service.close()

        # Client reference should be cleared even on exception
        assert service._client is None

    def test_get_opensearch_service_dependency(self):
        """Test FastAPI dependency function returns service instance."""
        service = get_opensearch_service()

        assert isinstance(service, OpenSearchService)
        assert service.config is not None
