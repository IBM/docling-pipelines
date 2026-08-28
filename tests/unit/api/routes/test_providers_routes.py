"""Unit tests for Provider model API routes.

Tests the router layer for GET /providers/{provider}/models, verifying:
- HTTP status codes and response structure
- Dependency injection and service delegation
- Exception-to-HTTPException translation for all error paths
- OpenAPI schema correctness (api_base is a query param; provider is a path param)
- Provider normalisation in responses
- embedding_dimension serialisation
- api_base forwarding and invalid_api_base error code
"""

from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from docpipe.api.middleware.error_handler import (
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from docpipe.api.routes.providers import get_provider_models_service, providers_router
from docpipe.core.operators.application.services.provider_models_service import ProviderModelsService
from docpipe.core.operators.models.model_info import ModelInfo
from docpipe.exceptions.docpipe_exceptions import ConfigurationError, DependencyError, ExternalServiceError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    """Minimal FastAPI app with providers router and the same error handlers as main.py."""
    _app = FastAPI()
    _app.include_router(providers_router)
    _app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    _app.add_exception_handler(RequestValidationError, validation_exception_handler)
    _app.add_exception_handler(Exception, generic_exception_handler)
    return _app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def mock_service() -> Mock:
    return Mock(spec=ProviderModelsService)


@pytest.fixture
def override_service(app: FastAPI, mock_service: Mock):
    app.dependency_overrides[get_provider_models_service] = lambda: mock_service
    yield mock_service
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetProviderModels:
    def test_returns_200_with_model_list(self, client, override_service):
        """Happy path: service returns two models, response serialises correctly."""
        override_service.list_models.return_value = [
            ModelInfo(model_id="granite4:latest", functions=[]),
            ModelInfo(model_id="nomic-embed-text:latest", functions=[]),
        ]
        response = client.get("/providers/ollama/models")
        assert response.status_code == 200
        body = response.json()
        assert body["provider"] == "ollama"
        assert len(body["models"]) == 2
        assert body["models"][0]["model_id"] == "granite4:latest"
        assert "name" not in body["models"][0]

    def test_passes_provider_path_to_service(self, client, override_service):
        """Provider path segment and api_base are forwarded to service.list_models."""
        override_service.list_models.return_value = []
        client.get("/providers/ollama/models")
        override_service.list_models.assert_called_once_with(provider="ollama", api_base=None)

    def test_passes_api_base_query_param_to_service(self, client, override_service):
        """api_base query param is forwarded to service.list_models when provided."""
        override_service.list_models.return_value = []
        client.get("/providers/watsonx/models?api_base=https://eu-de.ml.cloud.ibm.com")
        override_service.list_models.assert_called_once_with(
            provider="watsonx", api_base="https://eu-de.ml.cloud.ibm.com"
        )

    def test_returns_400_on_non_https_api_base(self, client, override_service):
        """api_base that does not match the HTTPS pattern is rejected at the framework level (400).

        The pattern constraint on the Query parameter enforces that api_base must start with
        https://, so non-HTTPS values are caught before reaching the service layer and the
        validation_exception_handler converts the RequestValidationError to a 400.
        """
        response = client.get("/providers/watsonx/models?api_base=http://internal")
        assert response.status_code == 400
        body = response.json()
        assert body["errors"][0]["code"] == "validation_error"
        assert "api_base" in body["errors"][0]["message"]
        override_service.list_models.assert_not_called()

    def test_returns_400_on_invalid_api_base_from_service(self, client, override_service):
        """ValueError with invalid api_base propagated by service -> 400 with the rejection message.

        This covers the case where api_base passes schema validation (valid HTTPS URL) but
        is rejected by the service for a business-logic reason (e.g. not an allowed WatsonX region).
        """
        override_service.list_models.side_effect = ValueError(
            "'https://unknown.example.com' is not a valid WatsonX API base URL. Please provide a valid HTTPS URL."
        )
        response = client.get("/providers/watsonx/models?api_base=https://unknown.example.com")
        assert response.status_code == 400
        body = response.json()
        assert "not a valid WatsonX API base URL" in body["errors"][0]["message"]

    def test_returns_empty_model_list_as_200(self, client, override_service):
        """Empty model list is a valid 200 — not a 404 or 503."""
        override_service.list_models.return_value = []
        response = client.get("/providers/ollama/models")
        assert response.status_code == 200
        assert response.json()["models"] == []

    def test_provider_echoed_in_response(self, client, override_service):
        """Provider value is echoed back in the response envelope."""
        override_service.list_models.return_value = []
        response = client.get("/providers/ollama/models")
        assert response.status_code == 200
        assert response.json()["provider"] == "ollama"

    def test_returns_400_on_unsupported_provider(self, client, override_service):
        """Unknown provider is rejected at the framework level (400 validation_error).

        ProviderName is a StrEnum — FastAPI rejects values not in the enum before
        the route handler runs, so the service is never called.
        """
        response = client.get("/providers/huggingface/models")
        assert response.status_code == 400
        body = response.json()
        assert body["errors"][0]["code"] == "validation_error"
        override_service.list_models.assert_not_called()

    def test_returns_400_on_configuration_error(self, client, override_service):
        """ConfigurationError (missing env var) -> 400 with env var name in message."""
        override_service.list_models.side_effect = ConfigurationError(
            "WATSONX_API_BASE_URL environment variable is required for the watsonx provider."
        )
        response = client.get("/providers/watsonx/models")
        assert response.status_code == 400
        body = response.json()
        assert "errors" in body
        assert "WATSONX_API_BASE_URL" in body["errors"][0]["message"]

    def test_returns_503_on_dependency_error(self, client, override_service):
        """DependencyError (SDK not installed) -> 503."""
        override_service.list_models.side_effect = DependencyError(
            "ollama package is not installed. Install with: uv sync --extra ollama"
        )
        response = client.get("/providers/ollama/models")
        assert response.status_code == 503
        body = response.json()
        assert "errors" in body
        assert "ollama package is not installed" in body["errors"][0]["message"]

    def test_returns_503_on_external_service_error(self, client, override_service):
        """ExternalServiceError -> 503 with upstream error detail in message."""
        override_service.list_models.side_effect = ExternalServiceError(
            "Ollama server at http://localhost:11434 is not reachable: connection refused"
        )
        response = client.get("/providers/ollama/models")
        assert response.status_code == 503
        body = response.json()
        assert "errors" in body
        assert "not reachable" in body["errors"][0]["message"]

    def test_api_base_in_openapi_schema_as_query_param(self, app):
        """api_base must appear as an optional query parameter in the OpenAPI schema."""
        schema = app.openapi()
        route_params = (
            schema.get("paths", {}).get("/providers/{provider}/models", {}).get("get", {}).get("parameters", [])
        )
        param_names = {p["name"]: p for p in route_params}
        assert "api_base" in param_names
        assert param_names["api_base"]["in"] == "query"
        assert param_names["api_base"].get("required", False) is False

    def test_provider_and_api_base_params_in_schema(self, app):
        """Schema exposes exactly two parameters: provider (path) and api_base (query)."""
        schema = app.openapi()
        route_params = (
            schema.get("paths", {}).get("/providers/{provider}/models", {}).get("get", {}).get("parameters", [])
        )
        param_map = {p["name"]: p["in"] for p in route_params}
        assert param_map.get("provider") == "path"
        assert param_map.get("api_base") == "query"
        assert len(route_params) == 2

    def test_embedding_dimension_included_in_response(self, client, override_service):
        """embedding_dimension is serialised into the response for embedding models."""
        override_service.list_models.return_value = [
            ModelInfo(
                model_id="ibm/slate-125m-english-rtrvr",
                functions=["embedding"],
                embedding_dimension=768,
            )
        ]
        response = client.get("/providers/watsonx/models")
        assert response.status_code == 200
        model = response.json()["models"][0]
        assert model["embedding_dimension"] == 768

    def test_embedding_dimension_is_null_when_not_set(self, client, override_service):
        """embedding_dimension is null in the response when the model does not expose it."""
        override_service.list_models.return_value = [ModelInfo(model_id="granite4:latest", functions=[])]
        response = client.get("/providers/ollama/models")
        assert response.json()["models"][0]["embedding_dimension"] is None
