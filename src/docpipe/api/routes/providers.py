"""Provider API routes.

Provides REST endpoints for querying LLM/embedding provider capabilities —
specifically, listing the models available on a given provider. Follows the
standard router -> service -> domain layering.

Architecture:
    Router Layer (this file)
        |
    Service Layer (ProviderModelsService)
        |
    Domain / Integration Layer

Error Handling Strategy:
    - GET /{provider}/models: catches ValueError, ConfigurationError, DependencyError,
      and ExternalServiceError and converts each to a structured HTTPException (400 or
      503) so the middleware wraps the detail into the standard ErrorResponse envelope.

Endpoints:
    GET /api/v1/providers/{provider}/models - List available models for a given provider

Security:
    Provider API base URLs are resolved server-side from environment variables
    (OLLAMA_HOST, WATSONX_API_BASE_URL). Caller-supplied api_base values are
    validated against a known set of IBM Cloud WatsonX endpoints.

Dependencies:
    - ProviderModelsService: singleton via get_provider_models_service()
"""

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from docpipe.api.dto.error_dto import ErrorResponse
from docpipe.api.dto.models_dto import ModelInfo, ModelsResponse, ProviderName
from docpipe.core.operators.application.services.provider_models_service import ProviderModelsService
from docpipe.exceptions.docpipe_exceptions import ConfigurationError, DependencyError, ExternalServiceError
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)

providers_router = APIRouter(prefix="/providers", tags=["Providers"])


@lru_cache(maxsize=1)
def get_provider_models_service() -> ProviderModelsService:
    """Dependency provider for ProviderModelsService.

    Uses @lru_cache to create a singleton — the service is stateless and
    safe to share across requests.

    Returns:
        ProviderModelsService: Cached service instance for API use.
    """
    return ProviderModelsService()


ProviderModelsServiceDep = Annotated[ProviderModelsService, Depends(get_provider_models_service)]


@providers_router.get(
    "/{provider}/models",
    response_model=ModelsResponse,
    operation_id="list_provider_models",
    summary="List available models for a provider",
    description=(
        "Returns the models available for a given LLM/embedding provider. "
        "Currently supports: ollama, watsonx. "
        "For WatsonX, an optional api_base query parameter may be supplied to target "
        "a specific deployment. When omitted, the server-side "
        "WATSONX_API_BASE_URL environment variable is used."
    ),
    responses={
        200: {"description": "Models retrieved successfully", "model": ModelsResponse},
        400: {
            "description": "Unsupported provider, invalid api_base URL, or missing server configuration",
            "model": ErrorResponse,
        },
        503: {"description": "Provider unreachable or required SDK not installed", "model": ErrorResponse},
    },
)
def get_provider_models(
    service: ProviderModelsServiceDep,
    provider: ProviderName = Path(  # noqa: B008
        description="Provider name.",
    ),
    api_base: str | None = Query(
        default=None,
        min_length=1,
        max_length=2048,
        pattern=r"^https://[^\s]{1,2000}$",
        description=(
            "WatsonX only. Target a specific deployment. "
            "Must be a valid HTTPS URL. "
            "When omitted, the server-side WATSONX_API_BASE_URL environment variable is used."
        ),
        examples=["https://us-south.ml.cloud.ibm.com", "https://eu-de.ml.cloud.ibm.com"],
    ),
) -> ModelsResponse:
    """List models available for the given LLM/embedding provider.

    Translates service-layer exceptions into structured HTTP error responses so the
    error_handler middleware receives an ``HTTPException`` with a ``detail`` dict that
    it can wrap into the standard ``ErrorResponse`` envelope.

    For WatsonX, ``api_base`` may be supplied to target a specific public production
    region. When omitted, the ``WATSONX_API_BASE_URL`` environment variable is used.
    Ollama always resolves its host from the ``OLLAMA_HOST`` environment variable;
    ``api_base`` is ignored for Ollama.

    Args:
        service: Injected ProviderModelsService singleton (via dependency injection).
        provider: Provider name in the URL path. Must be one of the ``ProviderName``
            enum values: ``"ollama"`` or ``"watsonx"``.
        api_base: Optional WatsonX API base URL. Must be a known IBM Cloud WatsonX
            endpoint when provided.

    Returns:
        ``ModelsResponse`` containing the normalised provider name and the list of
        ``ModelInfo`` objects. An empty ``models`` list is a valid 200 response —
        it means the provider is reachable but has no models configured.

    Raises:
        HTTPException(400, code="unsupported_provider"):
            ``provider`` is not in the supported set (``ollama``, ``watsonx``).
        HTTPException(400, code="invalid_api_base"):
            ``api_base`` was supplied but is not in the allowed WatsonX endpoints.
        HTTPException(400, code="missing_configuration"):
            WatsonX ``api_base`` was not supplied and ``WATSONX_API_BASE_URL`` is not set.
        HTTPException(503, code="provider_sdk_missing"):
            The required SDK package (``ollama`` or ``ibm-watsonx-ai``) is not installed.
        HTTPException(503, code="provider_unavailable"):
            The upstream provider is unreachable or returned an error.
    """
    try:
        domain_models = service.list_models(provider=provider.value, api_base=api_base)
        # ProviderName is already lowercase (StrEnum values from ProviderConstants)
        logger.info("Listed %d models for provider '%s'", len(domain_models), provider)
        return ModelsResponse(
            provider=provider,
            models=[
                ModelInfo(
                    model_id=m.model_id,
                    description=m.description,
                    functions=m.functions,
                    embedding_dimension=m.embedding_dimension,
                )
                for m in domain_models
            ],
        )

    except ValueError as exc:
        # Two distinct ValueError cases: unsupported provider vs disallowed api_base.
        # Distinguish by inspecting the message so each gets its own error code.
        is_api_base_error = api_base is not None and "not a valid WatsonX API base URL" in str(exc)
        error_code = "invalid_api_base" if is_api_base_error else "unsupported_provider"
        target_param = "api_base" if is_api_base_error else "provider"
        raise HTTPException(
            status_code=400,
            detail={
                "errors": [
                    {
                        "code": error_code,
                        "message": str(exc),
                        "target": {"type": "parameter", "name": target_param},
                    }
                ]
            },
        ) from exc

    except ConfigurationError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "errors": [
                    {
                        "code": "missing_configuration",
                        "message": str(exc),
                        "target": {"type": "parameter", "name": "provider"},
                    }
                ]
            },
        ) from exc

    except DependencyError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "errors": [
                    {
                        "code": "provider_sdk_missing",
                        "message": str(exc),
                        "target": {"type": "parameter", "name": "provider"},
                    }
                ]
            },
        ) from exc

    except ExternalServiceError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "errors": [
                    {
                        "code": "provider_unavailable",
                        "message": str(exc),
                        "target": {"type": "parameter", "name": "provider"},
                    }
                ]
            },
        ) from exc
