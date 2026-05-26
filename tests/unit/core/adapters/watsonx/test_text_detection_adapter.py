"""Tests for WatsonX text detection adapter."""

from unittest.mock import Mock, patch

import pytest

from datasift.core.adapters.watsonx.text_detection_adapter import WatsonXTextDetectionAdapter
from datasift.core.ports.text_detection_port import TextDetectionPort


class TestWatsonXTextDetectionAdapter:
    """Test suite for WatsonXTextDetectionAdapter."""

    @pytest.fixture
    def valid_config(self):
        """Provide valid WatsonX configuration."""
        return {
            "api_key": "watsonx-test-credential",  # pragma: allowlist secret
            "project_id": "test-project-id",
            "url": "https://us-south.ml.cloud.ibm.com",
            "max_tokens": 2000,
            "temperature": 0.0,
        }

    @pytest.fixture
    def mock_watsonx_client(self):
        """Create a mock WatsonX client."""
        with patch("datasift.core.adapters.watsonx.text_detection_adapter.WatsonXClient") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def adapter(self, valid_config, mock_watsonx_client):
        """Create a WatsonX text detection adapter instance."""
        return WatsonXTextDetectionAdapter(
            model_id="test-model",
            provider_config=valid_config,
        )

    def test_implements_text_detection_port(self, adapter):
        """Test that adapter implements TextDetectionPort interface."""
        assert isinstance(adapter, TextDetectionPort)

    def test_initialization_success(self, valid_config, mock_watsonx_client):
        """Test successful adapter initialization."""
        adapter = WatsonXTextDetectionAdapter(
            model_id="granite-guardian",
            provider_config=valid_config,
        )

        assert adapter.model_id == "granite-guardian"
        assert adapter.provider_config == valid_config
        assert adapter.max_tokens == 2000
        assert adapter.temperature == pytest.approx(0.0)
        assert adapter.client == mock_watsonx_client

    def test_initialization_with_defaults(self, mock_watsonx_client):
        """Test initialization with default parameters."""
        config = {
            "api_key": "watsonx-test-credential",  # pragma: allowlist secret
            "project_id": "test-project-id",
            "url": "https://test.com",
        }

        adapter = WatsonXTextDetectionAdapter(
            model_id="test-model",
            provider_config=config,
        )

        assert adapter.max_tokens == 2000  # Default
        assert adapter.temperature == pytest.approx(0.0)  # Default

    def test_initialization_missing_api_key(self):
        """Test initialization fails with missing API key."""
        config = {
            "project_id": "project",
            "url": "https://test.com",
        }

        with pytest.raises(ValueError, match=r"Missing required WatsonX configuration.*api_key"):
            WatsonXTextDetectionAdapter(
                model_id="test-model",
                provider_config=config,
            )

    def test_initialization_missing_project_id(self):
        """Test initialization fails with missing project ID."""
        config = {
            "api_key": "key",  # pragma: allowlist secret
            "url": "https://test.com",
        }

        with pytest.raises(ValueError, match=r"Missing required WatsonX configuration.*project_id"):
            WatsonXTextDetectionAdapter(
                model_id="test-model",
                provider_config=config,
            )

    def test_initialization_missing_url(self):
        """Test initialization fails with missing URL."""
        config = {
            "api_key": "key",  # pragma: allowlist secret
            "project_id": "project",
        }

        with pytest.raises(ValueError, match=r"Missing required WatsonX configuration.*url"):
            WatsonXTextDetectionAdapter(
                model_id="test-model",
                provider_config=config,
            )

    def test_initialization_missing_multiple_keys(self):
        """Test initialization fails with multiple missing keys."""
        config = {}

        with pytest.raises(ValueError, match="Missing required WatsonX configuration"):
            WatsonXTextDetectionAdapter(
                model_id="test-model",
                provider_config=config,
            )

    def test_client_initialization_parameters(self, valid_config):
        """Test that WatsonX client is initialized with correct parameters."""
        with patch("datasift.core.adapters.watsonx.text_detection_adapter.WatsonXClient") as mock_client_class:
            WatsonXTextDetectionAdapter(
                model_id="test-model",
                provider_config=valid_config,
            )

            mock_client_class.assert_called_once_with(
                model_name="test-model",
                api_key=valid_config["api_key"],
                container_id=valid_config["project_id"],
                api_base=valid_config["url"],
            )

    def test_detect_method_exists(self, adapter):
        """Test that detect method exists."""
        assert hasattr(adapter, "detect")
        assert callable(adapter.detect)

    def test_custom_max_tokens(self, mock_watsonx_client):
        """Test initialization with custom max_tokens."""
        config = {
            "api_key": "api-key",  # pragma: allowlist secret
            "project_id": "project",
            "url": "https://test.com",
            "max_tokens": 5000,
        }

        adapter = WatsonXTextDetectionAdapter(
            model_id="test-model",
            provider_config=config,
        )

        assert adapter.max_tokens == 5000

    def test_custom_temperature(self, mock_watsonx_client):
        """Test initialization with custom temperature."""
        config = {
            "api_key": "api-key",  # pragma: allowlist secret
            "project_id": "project",
            "url": "https://test.com",
            "temperature": 0.7,
        }

        adapter = WatsonXTextDetectionAdapter(
            model_id="test-model",
            provider_config=config,
        )

        assert adapter.temperature == pytest.approx(0.7)

    def test_adapter_preserves_model_id(self, adapter):
        """Test that adapter preserves the model ID."""
        assert adapter.model_id == "test-model"

    def test_adapter_preserves_config(self, adapter, valid_config):
        """Test that adapter preserves the provider config."""
        assert adapter.provider_config == valid_config

    @pytest.mark.parametrize(
        "config_key,config_value",
        [
            ("max_tokens", 1000),
            ("max_tokens", 10000),
            ("temperature", 0.0),
            ("temperature", 1.0),
            ("temperature", 0.5),
        ],
    )
    def test_various_config_values(self, mock_watsonx_client, config_key, config_value):
        """Test initialization with various configuration values."""
        config = {
            "api_key": "api-key",  # pragma: allowlist secret
            "project_id": "project",
            "url": "https://test.com",
            config_key: config_value,
        }

        adapter = WatsonXTextDetectionAdapter(
            model_id="test-model",
            provider_config=config,
        )

        assert getattr(adapter, config_key) == config_value

    def test_initialization_with_extra_config_keys(self, mock_watsonx_client):
        """Test initialization ignores extra configuration keys."""
        config = {
            "api_key": "api-key",  # pragma: allowlist secret
            "project_id": "project",
            "url": "https://test.com",
            "extra_key": "extra_value",
            "another_key": 123,
        }

        adapter = WatsonXTextDetectionAdapter(
            model_id="test-model",
            provider_config=config,
        )

        assert adapter.provider_config == config
        assert "extra_key" in adapter.provider_config
        assert "another_key" in adapter.provider_config

    def test_multiple_adapter_instances(self, valid_config):
        """Test creating multiple adapter instances."""
        with patch("datasift.core.adapters.watsonx.text_detection_adapter.WatsonXClient") as mock_client_class:
            client1 = Mock()
            client2 = Mock()
            mock_client_class.side_effect = [client1, client2]

            adapter1 = WatsonXTextDetectionAdapter(
                model_id="model1",
                provider_config=valid_config,
            )
            adapter2 = WatsonXTextDetectionAdapter(
                model_id="model2",
                provider_config=valid_config,
            )

        assert adapter1.model_id == "model1"
        assert adapter2.model_id == "model2"
        assert adapter1.client is client1
        assert adapter2.client is client2
        assert adapter1.client is not adapter2.client

    @pytest.mark.parametrize(
        "model_id",
        [
            "granite-guardian-3.0-8b",
            "granite-guardian-3.0-2b",
            "custom-model-v1",
            "test-model-123",
        ],
    )
    def test_various_model_ids(self, valid_config, mock_watsonx_client, model_id):
        """Test initialization with various model IDs."""
        adapter = WatsonXTextDetectionAdapter(
            model_id=model_id,
            provider_config=valid_config,
        )

        assert adapter.model_id == model_id
