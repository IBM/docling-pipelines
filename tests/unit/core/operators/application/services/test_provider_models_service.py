"""Unit tests for ProviderModelsService.

Covers: provider name normalisation, Ollama model listing (object and dict SDK
response shapes, tag stripping, deduplication, empty-name skipping, missing SDK,
capabilities enrichment, embedding dimension probing),
and WatsonX model listing (description fallback chain, env-var API base resolution,
api_base URL validation, embedding_dimension, error propagation).
"""

from unittest.mock import MagicMock, patch

import pytest

from docpipe.core.operators.application.services.provider_models_service import (
    ProviderModelsService,
)
from docpipe.exceptions.docpipe_exceptions import ConfigurationError, DependencyError, ExternalServiceError

# get_available_foundation_models is imported via a deferred local import inside _list_watsonx_models,
# so it is never bound at module level. Patch the function at its definition in the source module.
_PATCH_GET_MODELS = "docpipe.integrations.watsonx.model_validator.get_available_foundation_models"


@pytest.fixture
def service() -> ProviderModelsService:
    return ProviderModelsService()


# ---------------------------------------------------------------------------
# Unsupported provider
# ---------------------------------------------------------------------------


class TestUnsupportedProvider:
    def test_raises_value_error_for_unknown_provider(self, service):
        """An unrecognised provider string raises ValueError with the provider name in the message."""
        with pytest.raises(ValueError, match="Unsupported provider 'huggingface'"):
            service.list_models(provider="huggingface")

    def test_error_message_lists_supported_providers(self, service):
        """The ValueError message includes the supported provider names so callers know valid values."""
        with pytest.raises(ValueError, match="ollama"):
            service.list_models(provider="unknown")

    def test_provider_name_is_normalised_to_lowercase(self, service):
        """'OLLAMA' must route to the Ollama handler, not raise ValueError."""
        mock_client = MagicMock()
        mock_client.list.return_value = MagicMock(models=[])
        with patch("ollama.Client", return_value=mock_client):
            result = service.list_models(provider="OLLAMA")
        assert result == []


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------


class TestOllamaModels:
    def _make_model(self, name: str) -> MagicMock:
        m = MagicMock()
        m.model = name
        return m

    def _make_show_resp(self, capabilities: list[str]) -> MagicMock:
        resp = MagicMock()
        resp.capabilities = capabilities
        return resp

    def _make_embed_resp(self, dim: int) -> MagicMock:
        resp = MagicMock()
        resp.embeddings = [[0.0] * dim]
        return resp

    def test_returns_model_list(self, service):
        """Happy path: two distinct models returned with correct model_id."""
        mock_response = MagicMock()
        mock_response.models = [
            self._make_model("granite4:latest"),
            self._make_model("nomic-embed-text:latest"),
        ]
        mock_client = MagicMock()
        mock_client.list.return_value = mock_response
        mock_client.show.side_effect = [
            self._make_show_resp(["completion"]),
            self._make_show_resp(["embedding"]),
        ]
        mock_client.embed.return_value = self._make_embed_resp(768)

        with patch("ollama.Client", return_value=mock_client):
            models = service.list_models(provider="ollama")

        assert len(models) == 2
        assert models[0].model_id == "granite4:latest"
        assert models[1].model_id == "nomic-embed-text:latest"

    def test_model_id_equals_full_tagged_name(self, service):
        """model_id must be the full tagged name so different tags are unambiguous."""
        mock_response = MagicMock()
        mock_response.models = [self._make_model("llama3.2:8b")]
        mock_client = MagicMock()
        mock_client.list.return_value = mock_response
        mock_client.show.return_value = self._make_show_resp(["completion"])

        with patch("ollama.Client", return_value=mock_client):
            models = service.list_models(provider="ollama")

        assert models[0].model_id == "llama3.2:8b"

    def test_returns_one_entry_per_tag_with_distinct_dimensions(self, service):
        """Two tags of the same base model get separate entries with their own dimensions."""
        mock_response = MagicMock()
        mock_response.models = [
            self._make_model("snowflake-arctic-embed:33m"),
            self._make_model("snowflake-arctic-embed:137m"),
        ]
        mock_client = MagicMock()
        mock_client.list.return_value = mock_response
        mock_client.show.return_value = self._make_show_resp(["embedding"])
        mock_client.embed.side_effect = [
            self._make_embed_resp(384),
            self._make_embed_resp(768),
        ]

        with patch("ollama.Client", return_value=mock_client):
            models = service.list_models(provider="ollama")

        assert len(models) == 2
        assert models[0].model_id == "snowflake-arctic-embed:33m"
        assert models[0].embedding_dimension == 384
        assert models[1].model_id == "snowflake-arctic-embed:137m"
        assert models[1].embedding_dimension == 768

    def test_uses_default_host_from_service_constants(self, service):
        """Ollama Client is initialised with DEFAULT_OLLAMA_HOST."""
        mock_client = MagicMock()
        mock_client.list.return_value = MagicMock(models=[])

        with patch("ollama.Client", return_value=mock_client) as mock_ollama_cls:
            service.list_models(provider="ollama")

        from docpipe.core.constants.constants import ServiceConstants

        mock_ollama_cls.assert_called_once_with(host=ServiceConstants.DEFAULT_OLLAMA_HOST, trust_env=False)

    def test_raises_external_service_error_on_connection_failure(self, service):
        """Any exception from ollama.Client.list() is wrapped in ExternalServiceError."""
        mock_client = MagicMock()
        mock_client.list.side_effect = Exception("connection refused")
        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(ExternalServiceError, match="not reachable"):
                service.list_models(provider="ollama")

    def test_raises_dependency_error_when_sdk_not_installed(self, service):
        """ImportError on 'import ollama' raises DependencyError, not ExternalServiceError."""
        with patch.dict("sys.modules", {"ollama": None}):
            with pytest.raises(DependencyError, match="ollama package is not installed"):
                service.list_models(provider="ollama")

    def test_empty_model_list_returns_empty(self, service):
        """An Ollama server with no models pulled returns an empty list — not an error."""
        mock_client = MagicMock()
        mock_client.list.return_value = MagicMock(models=[])

        with patch("ollama.Client", return_value=mock_client):
            models = service.list_models(provider="ollama")

        assert models == []

    def test_handles_dict_response_format(self, service):
        """ollama.Client.list() can return a dict on older SDK versions."""
        mock_client = MagicMock()
        mock_client.list.return_value = {"models": [{"name": "granite4:latest"}]}
        mock_client.show.return_value = self._make_show_resp(["completion"])

        with patch("ollama.Client", return_value=mock_client):
            models = service.list_models(provider="ollama")

        assert models[0].model_id == "granite4:latest"

    def test_skips_entries_with_empty_name(self, service):
        """Entries with no name attribute/key are silently skipped."""
        mock_response = MagicMock()
        mock_response.models = [
            self._make_model("granite4:latest"),
            self._make_model(""),  # empty name — must be skipped
        ]
        mock_client = MagicMock()
        mock_client.list.return_value = mock_response
        mock_client.show.return_value = self._make_show_resp(["completion"])

        with patch("ollama.Client", return_value=mock_client):
            models = service.list_models(provider="ollama")

        assert len(models) == 1
        assert models[0].model_id == "granite4:latest"

    def test_model_without_version_tag(self, service):
        """Model name with no ':' tag is used as-is for model_id."""
        mock_response = MagicMock()
        mock_response.models = [self._make_model("granite4")]
        mock_client = MagicMock()
        mock_client.list.return_value = mock_response
        mock_client.show.return_value = self._make_show_resp(["completion"])

        with patch("ollama.Client", return_value=mock_client):
            models = service.list_models(provider="ollama")

        assert models[0].model_id == "granite4"

    def test_functions_populated_from_show_capabilities(self, service):
        """capabilities from show() are exposed as ModelInfo.functions."""
        mock_response = MagicMock()
        mock_response.models = [self._make_model("granite4:latest")]
        mock_client = MagicMock()
        mock_client.list.return_value = mock_response
        mock_client.show.return_value = self._make_show_resp(["completion", "tools"])

        with patch("ollama.Client", return_value=mock_client):
            models = service.list_models(provider="ollama")

        assert models[0].functions == ["completion", "tools"]

    def test_embedding_dimension_populated_for_embedding_model(self, service):
        """embedding_dimension is probed via embed() for models with 'embedding' capability."""
        mock_response = MagicMock()
        mock_response.models = [self._make_model("nomic-embed-text:latest")]
        mock_client = MagicMock()
        mock_client.list.return_value = mock_response
        mock_client.show.return_value = self._make_show_resp(["embedding"])
        mock_client.embed.return_value = self._make_embed_resp(768)

        with patch("ollama.Client", return_value=mock_client):
            models = service.list_models(provider="ollama")

        assert models[0].model_id == "nomic-embed-text:latest"
        assert models[0].embedding_dimension == 768
        assert not hasattr(models[0], "name")
        mock_client.embed.assert_called_once_with(model="nomic-embed-text:latest", input="probe")

    def test_embedding_dimension_is_none_for_non_embedding_model(self, service):
        """embed() must NOT be called and embedding_dimension must be None for non-embedding models."""
        mock_response = MagicMock()
        mock_response.models = [self._make_model("granite4:latest")]
        mock_client = MagicMock()
        mock_client.list.return_value = mock_response
        mock_client.show.return_value = self._make_show_resp(["completion", "tools"])

        with patch("ollama.Client", return_value=mock_client):
            models = service.list_models(provider="ollama")

        assert models[0].embedding_dimension is None
        mock_client.embed.assert_not_called()

    def test_show_failure_leaves_functions_empty_and_does_not_raise(self, service):
        """show() failure is non-fatal — model is returned with empty functions and no dimension."""
        mock_response = MagicMock()
        mock_response.models = [self._make_model("granite4:latest")]
        mock_client = MagicMock()
        mock_client.list.return_value = mock_response
        mock_client.show.side_effect = Exception("show failed")

        with patch("ollama.Client", return_value=mock_client):
            models = service.list_models(provider="ollama")

        assert models[0].functions == []
        assert models[0].embedding_dimension is None

    def test_embed_probe_failure_leaves_dimension_none_and_does_not_raise(self, service):
        """embed() probe failure is non-fatal — model is returned with embedding_dimension=None."""
        mock_response = MagicMock()
        mock_response.models = [self._make_model("nomic-embed-text:latest")]
        mock_client = MagicMock()
        mock_client.list.return_value = mock_response
        mock_client.show.return_value = self._make_show_resp(["embedding"])
        mock_client.embed.side_effect = Exception("embed failed")

        with patch("ollama.Client", return_value=mock_client):
            models = service.list_models(provider="ollama")

        assert models[0].functions == ["embedding"]
        assert models[0].embedding_dimension is None

    def test_show_called_once_per_model(self, service):
        """show() is called exactly once per entry from list()."""
        mock_response = MagicMock()
        mock_response.models = [
            self._make_model("granite4:latest"),
            self._make_model("nomic-embed-text:latest"),
        ]
        mock_client = MagicMock()
        mock_client.list.return_value = mock_response
        mock_client.show.return_value = self._make_show_resp(["completion"])

        with patch("ollama.Client", return_value=mock_client):
            service.list_models(provider="ollama")

        assert mock_client.show.call_count == 2
        mock_client.show.assert_any_call(model="granite4:latest")
        mock_client.show.assert_any_call(model="nomic-embed-text:latest")


# ---------------------------------------------------------------------------
# WatsonX
# ---------------------------------------------------------------------------


class TestWatsonxModels:
    def test_returns_model_list(self, service, monkeypatch):
        """Happy path: model_id, name, description, and functions are all populated correctly."""
        monkeypatch.setenv("WATSONX_API_BASE_URL", "https://us-south.ml.cloud.ibm.com")
        specs = [
            {
                "model_id": "ibm/granite-3-8b-instruct",
                "label": "Granite 3 8B",
                "functions": [{"id": "text_generation"}, {"id": "text_chat"}],
            },
            {
                "model_id": "ibm/slate-125m-english-rtrvr",
                "label": "SLATE 125M",
                "functions": [{"id": "embedding"}],
                "embedding_dimension": 768,
            },
        ]
        with patch(_PATCH_GET_MODELS, return_value=specs):
            models = service.list_models(
                provider="watsonx",
            )

        assert len(models) == 2
        assert models[0].model_id == "ibm/granite-3-8b-instruct"
        assert models[0].description == "Granite 3 8B"
        assert models[0].functions == ["text_generation", "text_chat"]
        assert models[0].embedding_dimension is None
        assert models[1].functions == ["embedding"]
        assert models[1].embedding_dimension == 768

    def test_functions_is_empty_when_not_present_in_spec(self, service, monkeypatch):
        """A spec with no 'functions' key produces an empty functions list."""
        monkeypatch.setenv("WATSONX_API_BASE_URL", "https://us-south.ml.cloud.ibm.com")
        specs = [{"model_id": "ibm/granite-3-8b-instruct", "label": "Granite 3 8B"}]
        with patch(_PATCH_GET_MODELS, return_value=specs):
            models = service.list_models(provider="watsonx")

        assert models[0].functions == []

    def test_functions_skips_entries_without_id(self, service, monkeypatch):
        """Function entries missing the 'id' key are silently skipped."""
        monkeypatch.setenv("WATSONX_API_BASE_URL", "https://us-south.ml.cloud.ibm.com")
        specs = [
            {
                "model_id": "ibm/granite-3-8b-instruct",
                "functions": [{"id": "text_generation"}, {"no_id": "bad_entry"}],
            }
        ]
        with patch(_PATCH_GET_MODELS, return_value=specs):
            models = service.list_models(provider="watsonx")

        assert models[0].functions == ["text_generation"]

    def test_description_falls_back_to_short_description(self, service, monkeypatch):
        """When 'label' is absent, description is populated from 'short_description'."""
        monkeypatch.setenv("WATSONX_API_BASE_URL", "https://us-south.ml.cloud.ibm.com")
        specs = [{"model_id": "ibm/granite-3-8b-instruct", "short_description": "Granite short"}]
        with patch(_PATCH_GET_MODELS, return_value=specs):
            models = service.list_models(provider="watsonx")

        assert models[0].description == "Granite short"

    def test_description_is_none_when_no_label_or_short_description(self, service, monkeypatch):
        """When neither 'label' nor 'short_description' is present, description is None."""
        monkeypatch.setenv("WATSONX_API_BASE_URL", "https://us-south.ml.cloud.ibm.com")
        specs = [{"model_id": "ibm/granite-3-8b-instruct"}]
        with patch(_PATCH_GET_MODELS, return_value=specs):
            models = service.list_models(provider="watsonx")

        assert models[0].description is None

    def test_raises_configuration_error_when_env_var_missing(self, service, monkeypatch):
        """ConfigurationError is raised when WATSONX_API_BASE_URL env var is not set."""
        monkeypatch.delenv("WATSONX_API_BASE_URL", raising=False)
        with pytest.raises(ConfigurationError, match="WATSONX_API_BASE_URL"):
            service.list_models(provider="watsonx")

    def test_calls_get_models_with_env_var_url(self, service, monkeypatch):
        """The resolved URL from WATSONX_API_BASE_URL is forwarded to get_available_foundation_models."""
        monkeypatch.setenv("WATSONX_API_BASE_URL", "https://us-south.ml.cloud.ibm.com")

        with patch(_PATCH_GET_MODELS, return_value=[]) as mock_fn:
            service.list_models(provider="watsonx")

        mock_fn.assert_called_once_with(
            api_key="",
            url="https://us-south.ml.cloud.ibm.com",
        )

    def test_falls_back_to_env_var_api_base(self, service, monkeypatch):
        """When WATSONX_API_BASE_URL is set, its value is used as the API base URL."""
        monkeypatch.setenv("WATSONX_API_BASE_URL", "https://eu-de.ml.cloud.ibm.com")

        with patch(_PATCH_GET_MODELS, return_value=[]) as mock_fn:
            service.list_models(provider="watsonx")

        mock_fn.assert_called_once_with(
            api_key="",
            url="https://eu-de.ml.cloud.ibm.com",
        )

    def test_propagates_external_service_error(self, service, monkeypatch):
        """ExternalServiceError from get_available_foundation_models propagates unchanged."""
        monkeypatch.setenv("WATSONX_API_BASE_URL", "https://us-south.ml.cloud.ibm.com")
        with patch(_PATCH_GET_MODELS, side_effect=ExternalServiceError("API call failed")):
            with pytest.raises(ExternalServiceError):
                service.list_models(provider="watsonx")

    def test_skips_specs_without_model_id(self, service, monkeypatch):
        """Foundation model specs that lack a 'model_id' key are silently filtered out."""
        monkeypatch.setenv("WATSONX_API_BASE_URL", "https://us-south.ml.cloud.ibm.com")
        specs = [
            {"model_id": "ibm/granite-3-8b-instruct"},
            {"label": "no model_id here"},
        ]
        with patch(_PATCH_GET_MODELS, return_value=specs):
            models = service.list_models(provider="watsonx")

        assert len(models) == 1

    def test_empty_model_list_returns_empty(self, service, monkeypatch):
        """A WatsonX deployment with no models returns an empty list — not an error."""
        monkeypatch.setenv("WATSONX_API_BASE_URL", "https://us-south.ml.cloud.ibm.com")
        with patch(_PATCH_GET_MODELS, return_value=[]):
            models = service.list_models(provider="watsonx")

        assert models == []

    def test_embedding_dimension_is_none_for_non_embedding_model(self, service, monkeypatch):
        """Specs without embedding_dimension produce None on the domain object."""
        monkeypatch.setenv("WATSONX_API_BASE_URL", "https://us-south.ml.cloud.ibm.com")
        specs = [{"model_id": "ibm/granite-3-8b-instruct", "label": "Granite 3 8B"}]
        with patch(_PATCH_GET_MODELS, return_value=specs):
            models = service.list_models(provider="watsonx")

        assert models[0].embedding_dimension is None

    # ------------------------------------------------------------------
    # api_base URL validation
    # ------------------------------------------------------------------

    def test_caller_supplied_valid_api_base_is_used(self, service, monkeypatch):
        """A caller-supplied valid HTTPS api_base is used instead of the env var."""
        monkeypatch.delenv("WATSONX_API_BASE_URL", raising=False)
        with patch(_PATCH_GET_MODELS, return_value=[]) as mock_fn:
            service.list_models(provider="watsonx", api_base="https://eu-de.ml.cloud.ibm.com")

        mock_fn.assert_called_once_with(api_key="", url="https://eu-de.ml.cloud.ibm.com")

    def test_caller_supplied_api_base_with_trailing_slash_is_normalised(self, service, monkeypatch):
        """Trailing slash on caller-supplied api_base is stripped before validation and use."""
        monkeypatch.delenv("WATSONX_API_BASE_URL", raising=False)
        with patch(_PATCH_GET_MODELS, return_value=[]) as mock_fn:
            service.list_models(provider="watsonx", api_base="https://eu-de.ml.cloud.ibm.com/")

        mock_fn.assert_called_once_with(api_key="", url="https://eu-de.ml.cloud.ibm.com")

    def test_caller_supplied_api_base_http_raises_value_error(self, service):
        """api_base with http scheme raises ValueError — must be HTTPS."""
        with pytest.raises(ValueError, match="not a valid WatsonX API base URL"):
            service.list_models(provider="watsonx", api_base="http://internal.host/")

    def test_caller_supplied_api_base_no_scheme_raises_value_error(self, service):
        """api_base with no scheme raises ValueError."""
        with pytest.raises(ValueError, match="not a valid WatsonX API base URL"):
            service.list_models(provider="watsonx", api_base="internal.host")

    def test_caller_supplied_api_base_overrides_env_var(self, service, monkeypatch):
        """When api_base is supplied, the WATSONX_API_BASE_URL env var is ignored."""
        monkeypatch.setenv("WATSONX_API_BASE_URL", "https://us-south.ml.cloud.ibm.com")
        with patch(_PATCH_GET_MODELS, return_value=[]) as mock_fn:
            service.list_models(provider="watsonx", api_base="https://eu-de.ml.cloud.ibm.com")

        mock_fn.assert_called_once_with(api_key="", url="https://eu-de.ml.cloud.ibm.com")

    def test_env_var_path_not_validated_allows_internal_url(self, service, monkeypatch):
        """Server-supplied WATSONX_API_BASE_URL is used directly without validation."""
        monkeypatch.setenv("WATSONX_API_BASE_URL", "https://cp4d.internal.company.com")
        with patch(_PATCH_GET_MODELS, return_value=[]) as mock_fn:
            service.list_models(provider="watsonx")

        mock_fn.assert_called_once_with(api_key="", url="https://cp4d.internal.company.com")
