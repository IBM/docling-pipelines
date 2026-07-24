"""Tests for Watsonx model validator."""

from unittest.mock import patch

import pytest

from docpipe.exceptions.docpipe_exceptions import DependencyError, ExternalServiceError
from docpipe.integrations.watsonx.model_validator import (
    get_available_foundation_models,
    get_model_dimension,
    validate_model_id,
)

pytestmark = pytest.mark.requires_watsonx


class TestGetAvailableFoundationModels:
    """Test get_available_foundation_models function."""

    def test_get_available_models_success(self):
        """Test successful retrieval of foundation models."""
        with patch("ibm_watsonx_ai.foundation_models.utils.get_model_specs") as mock_get_specs:
            mock_get_specs.return_value = {
                "resources": [
                    {"model_id": "ibm/granite-13b-chat-v2", "embedding_dimension": 768},
                    {"model_id": "meta-llama/llama-2-70b-chat", "embedding_dimension": 4096},
                ]
            }

            # Clear cache first
            get_available_foundation_models.cache_clear()

            models = get_available_foundation_models(api_key="test-key", url="https://test.com")

            assert len(models) == 2
            assert models[0]["model_id"] == "ibm/granite-13b-chat-v2"
            assert models[1]["model_id"] == "meta-llama/llama-2-70b-chat"

    def test_get_available_models_caching(self):
        """Test that results are cached."""
        with patch("ibm_watsonx_ai.foundation_models.utils.get_model_specs") as mock_get_specs:
            mock_get_specs.return_value = {"resources": [{"model_id": "test-model", "embedding_dimension": 768}]}

            # Clear cache first
            get_available_foundation_models.cache_clear()

            # First call
            models1 = get_available_foundation_models(api_key="test-key", url="https://test.com")
            # Second call with same params should use cache
            models2 = get_available_foundation_models(api_key="test-key", url="https://test.com")

            # Should only call API once due to caching
            assert mock_get_specs.call_count == 1
            assert models1 == models2

    def test_get_available_models_import_error(self):
        """Test when ibm-watsonx-ai package is not installed."""
        # Clear cache first
        get_available_foundation_models.cache_clear()

        with patch.dict(
            "sys.modules",
            {
                "ibm_watsonx_ai": None,
                "ibm_watsonx_ai.foundation_models": None,
                "ibm_watsonx_ai.foundation_models.utils": None,
            },
        ):
            with pytest.raises(DependencyError) as exc_info:
                get_available_foundation_models(api_key="test-key", url="https://test.com")  # pragma: allowlist secret

            assert "ibm-watsonx-ai package not installed" in str(exc_info.value)

    def test_get_available_models_invalid_response_type(self):
        """Test when API returns unexpected response type."""
        with patch("ibm_watsonx_ai.foundation_models.utils.get_model_specs") as mock_get_specs:
            mock_get_specs.return_value = "invalid response"

            # Clear cache
            get_available_foundation_models.cache_clear()

            with pytest.raises(ExternalServiceError) as exc_info:
                get_available_foundation_models(api_key="test-key", url="https://test.com")  # pragma: allowlist secret

            assert "Unexpected API response type" in str(exc_info.value)

    def test_get_available_models_missing_resources(self):
        """Test when API response is missing 'resources' field."""
        with patch("ibm_watsonx_ai.foundation_models.utils.get_model_specs") as mock_get_specs:
            mock_get_specs.return_value = {"data": []}

            # Clear cache
            get_available_foundation_models.cache_clear()

            with pytest.raises(ExternalServiceError) as exc_info:
                get_available_foundation_models(api_key="test-key", url="https://test.com")  # pragma: allowlist secret

            assert "missing 'resources' field" in str(exc_info.value)

    def test_get_available_models_invalid_resources_type(self):
        """Test when 'resources' is not a list."""
        with patch("ibm_watsonx_ai.foundation_models.utils.get_model_specs") as mock_get_specs:
            mock_get_specs.return_value = {"resources": "not a list"}

            # Clear cache
            get_available_foundation_models.cache_clear()

            with pytest.raises(ExternalServiceError) as exc_info:
                get_available_foundation_models(api_key="test-key", url="https://test.com")  # pragma: allowlist secret

            assert "Unexpected 'resources' type" in str(exc_info.value)

    def test_get_available_models_empty_list(self):
        """Test when no models are available."""
        with patch("ibm_watsonx_ai.foundation_models.utils.get_model_specs") as mock_get_specs:
            mock_get_specs.return_value = {"resources": []}

            # Clear cache
            get_available_foundation_models.cache_clear()

            models = get_available_foundation_models(api_key="test-key", url="https://test.com")

            assert len(models) == 0

    def test_get_available_models_filters_invalid_specs(self):
        """Test that invalid model specs are filtered out."""
        with patch("ibm_watsonx_ai.foundation_models.utils.get_model_specs") as mock_get_specs:
            mock_get_specs.return_value = {
                "resources": [
                    {"model_id": "valid-model", "embedding_dimension": 768},
                    {"no_model_id": "invalid"},  # Missing model_id
                    "not a dict",  # Not a dict
                    {"model_id": "another-valid", "embedding_dimension": 1024},
                ]
            }

            # Clear cache
            get_available_foundation_models.cache_clear()

            models = get_available_foundation_models(api_key="test-key", url="https://test.com")

            assert len(models) == 2
            assert models[0]["model_id"] == "valid-model"
            assert models[1]["model_id"] == "another-valid"

    def test_get_available_models_api_error(self):
        """Test when API call fails."""
        with patch("ibm_watsonx_ai.foundation_models.utils.get_model_specs") as mock_get_specs:
            mock_get_specs.side_effect = Exception("API error")

            # Clear cache
            get_available_foundation_models.cache_clear()

            with pytest.raises(ExternalServiceError) as exc_info:
                get_available_foundation_models(api_key="test-key", url="https://test.com")  # pragma: allowlist secret

            assert "Failed to fetch foundation models" in str(exc_info.value)


class TestGetModelDimension:
    """Test get_model_dimension function."""

    @patch("docpipe.integrations.watsonx.model_validator.get_available_foundation_models")
    def test_get_model_dimension_success(self, mock_get_models):
        """Test successful retrieval of model dimension."""
        mock_get_models.return_value = [
            {"model_id": "test-model", "embedding_dimension": 768},
            {"model_id": "another-model", "embedding_dimension": 1024},
        ]

        dimension = get_model_dimension(model_id="test-model", api_key="test-key", url="https://test.com")

        assert dimension == 768

    @patch("docpipe.integrations.watsonx.model_validator.get_available_foundation_models")
    def test_get_model_dimension_model_not_found(self, mock_get_models):
        """Test when model is not found."""
        mock_get_models.return_value = [{"model_id": "other-model", "embedding_dimension": 768}]

        dimension = get_model_dimension(model_id="nonexistent", api_key="test-key", url="https://test.com")

        assert dimension == 0

    @patch("docpipe.integrations.watsonx.model_validator.get_available_foundation_models")
    def test_get_model_dimension_missing_dimension(self, mock_get_models):
        """Test when model exists but dimension is missing."""
        mock_get_models.return_value = [
            {"model_id": "test-model"}  # No embedding_dimension
        ]

        dimension = get_model_dimension(model_id="test-model", api_key="test-key", url="https://test.com")

        assert dimension == 0

    @patch("docpipe.integrations.watsonx.model_validator.get_available_foundation_models")
    def test_get_model_dimension_zero_dimension(self, mock_get_models):
        """Test when model has zero dimension."""
        mock_get_models.return_value = [{"model_id": "test-model", "embedding_dimension": 0}]

        dimension = get_model_dimension(model_id="test-model", api_key="test-key", url="https://test.com")

        assert dimension == 0

    @patch("docpipe.integrations.watsonx.model_validator.get_available_foundation_models")
    def test_get_model_dimension_exception(self, mock_get_models):
        """Test when exception occurs during lookup."""
        mock_get_models.side_effect = Exception("API error")

        dimension = get_model_dimension(model_id="test-model", api_key="test-key", url="https://test.com")

        assert dimension == 0

    @patch("docpipe.integrations.watsonx.model_validator.get_available_foundation_models")
    def test_get_model_dimension_multiple_models(self, mock_get_models):
        """Test dimension lookup with multiple models."""
        mock_get_models.return_value = [
            {"model_id": "model-1", "embedding_dimension": 512},
            {"model_id": "model-2", "embedding_dimension": 768},
            {"model_id": "model-3", "embedding_dimension": 1024},
        ]

        dim1 = get_model_dimension(model_id="model-1", api_key="test-key", url="https://test.com")
        dim2 = get_model_dimension(model_id="model-2", api_key="test-key", url="https://test.com")
        dim3 = get_model_dimension(model_id="model-3", api_key="test-key", url="https://test.com")

        assert dim1 == 512
        assert dim2 == 768
        assert dim3 == 1024


class TestValidateModelId:
    """Test validate_model_id function."""

    @patch("docpipe.integrations.watsonx.model_validator.get_available_foundation_models")
    def test_validate_model_id_valid(self, mock_get_models):
        """Test validation of valid model ID."""
        mock_get_models.return_value = [
            {"model_id": "valid-model", "embedding_dimension": 768},
            {"model_id": "another-model", "embedding_dimension": 1024},
        ]

        is_valid = validate_model_id(model_id="valid-model", api_key="test-key", url="https://test.com")

        assert is_valid is True

    @patch("docpipe.integrations.watsonx.model_validator.get_available_foundation_models")
    def test_validate_model_id_invalid(self, mock_get_models):
        """Test validation of invalid model ID."""
        mock_get_models.return_value = [{"model_id": "valid-model", "embedding_dimension": 768}]

        is_valid = validate_model_id(model_id="nonexistent", api_key="test-key", url="https://test.com")

        assert is_valid is False

    @patch("docpipe.integrations.watsonx.model_validator.get_available_foundation_models")
    def test_validate_model_id_empty_list(self, mock_get_models):
        """Test validation when no models are available."""
        mock_get_models.return_value = []

        is_valid = validate_model_id(model_id="any-model", api_key="test-key", url="https://test.com")

        assert is_valid is False

    @patch("docpipe.integrations.watsonx.model_validator.get_available_foundation_models")
    def test_validate_model_id_filters_none_ids(self, mock_get_models):
        """Test that None model IDs are filtered out."""
        mock_get_models.return_value = [
            {"model_id": "valid-model", "embedding_dimension": 768},
            {"model_id": None},  # Should be filtered
            {"embedding_dimension": 1024},  # No model_id
        ]

        is_valid = validate_model_id(model_id="valid-model", api_key="test-key", url="https://test.com")

        assert is_valid is True

    @patch("docpipe.integrations.watsonx.model_validator.get_available_foundation_models")
    def test_validate_model_id_case_sensitive(self, mock_get_models):
        """Test that validation is case-sensitive."""
        mock_get_models.return_value = [{"model_id": "Valid-Model", "embedding_dimension": 768}]

        is_valid_exact = validate_model_id(model_id="Valid-Model", api_key="test-key", url="https://test.com")
        is_valid_lower = validate_model_id(model_id="valid-model", api_key="test-key", url="https://test.com")

        assert is_valid_exact is True
        assert is_valid_lower is False

    @patch("docpipe.integrations.watsonx.model_validator.get_available_foundation_models")
    def test_validate_model_id_multiple_checks(self, mock_get_models):
        """Test multiple validation checks."""
        mock_get_models.return_value = [
            {"model_id": "model-1", "embedding_dimension": 512},
            {"model_id": "model-2", "embedding_dimension": 768},
            {"model_id": "model-3", "embedding_dimension": 1024},
        ]

        assert validate_model_id(model_id="model-1", api_key="test-key", url="https://test.com") is True
        assert validate_model_id(model_id="model-2", api_key="test-key", url="https://test.com") is True
        assert validate_model_id(model_id="model-3", api_key="test-key", url="https://test.com") is True
        assert validate_model_id(model_id="model-4", api_key="test-key", url="https://test.com") is False


class TestCacheBehavior:
    """Test caching behavior of get_available_foundation_models."""

    def test_cache_clear(self):
        """Test that cache can be cleared."""
        with patch("ibm_watsonx_ai.foundation_models.utils.get_model_specs") as mock_get_specs:
            mock_get_specs.return_value = {"resources": [{"model_id": "test", "embedding_dimension": 768}]}

            # Clear cache
            get_available_foundation_models.cache_clear()

            # First call
            get_available_foundation_models(api_key="key1", url="url1")  # pragma: allowlist secret
            assert mock_get_specs.call_count == 1

            # Second call with same params (should use cache)
            get_available_foundation_models(api_key="key1", url="url1")  # pragma: allowlist secret
            assert mock_get_specs.call_count == 1

            # Clear cache
            get_available_foundation_models.cache_clear()

            # Third call (should hit API again)
            get_available_foundation_models(api_key="key1", url="url1")  # pragma: allowlist secret
            assert mock_get_specs.call_count == 2

    def test_cache_different_params(self):
        """Test that different parameters result in different cache entries."""
        # Clear cache before test to ensure clean state
        get_available_foundation_models.cache_clear()

        with patch("ibm_watsonx_ai.foundation_models.utils.get_model_specs") as mock_get_specs:
            mock_get_specs.return_value = {"resources": [{"model_id": "test", "embedding_dimension": 768}]}

            # Call with first set of params
            result1 = get_available_foundation_models(api_key="key1", url="url1")

            # Call with different params (should hit API again)
            result2 = get_available_foundation_models(api_key="key2", url="url2")

            # Verify both calls were made (different params = different cache entries)
            assert mock_get_specs.call_count >= 2, "Different params should trigger separate API calls"

            # Verify results are valid
            assert len(result1) == 1
            assert len(result2) == 1
