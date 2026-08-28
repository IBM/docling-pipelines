"""Provider models API response Data Transfer Objects (DTOs).

Pydantic models for the GET /api/v1/providers/{provider}/models endpoint.
The route layer maps ``ModelInfo`` domain objects from ``ProviderModelsService``
into these DTOs before returning them to callers.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from docpipe.core.constants.constants import ProviderConstants


class ProviderName(StrEnum):
    """Supported LLM/embedding provider names.

    Used as the ``{provider}`` path parameter type so FastAPI renders a
    dropdown in Swagger UI and rejects unknown values at the framework level.
    """

    OLLAMA = ProviderConstants.OLLAMA
    WATSONX = ProviderConstants.WATSONX


class ModelInfo(BaseModel):
    """API representation of a single model available from a provider.

    Maps from the ``ModelInfo`` domain dataclass. Carries OpenAPI field
    descriptions and examples used for schema generation.

    Attributes:
        model_id: Canonical identifier used in operator configuration and as
            the unique key for this model. For Ollama, the full tagged name
            (e.g. ``"granite4:latest"``). For WatsonX, the model identifier
            string (e.g. ``"ibm/granite-3-8b-instruct"``).
        description: Optional human-readable model label.
        functions: Capability identifiers reported by the provider.
            For Ollama, sourced from ``client.show()`` capabilities
            (e.g. ``["completion", "tools"]``, ``["embedding"]``).
            For WatsonX, sourced from the Foundation Models API
            (e.g. ``["text_generation", "text_chat"]``).
        embedding_dimension: Vector size for embedding models. For Ollama,
            probed via ``client.embed()`` for models with the ``"embedding"``
            capability; ``None`` for all others. For WatsonX, sourced from
            the Foundation Models API spec.
    """

    model_id: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^[\x20-\x7E]{1,256}$",
        description=(
            "Canonical model identifier used in operator configuration. "
            "For Ollama, the full tagged name (e.g. 'granite4:latest'). "
            "For WatsonX, the model identifier string (e.g. 'ibm/granite-3-8b-instruct')."
        ),
        examples=["granite4:latest", "ibm/granite-3-8b-instruct"],
    )
    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=512,
        pattern=r"^[\x20-\x7E]{1,512}$",
        description="Optional human-readable model label.",
        examples=["Granite 3 8B Instruct"],
    )
    functions: list[str] = Field(
        min_length=0,
        max_length=50,
        description=(
            "Capability identifiers for this model. "
            "For Ollama, sourced from client.show() capabilities. "
            "For WatsonX, sourced from the Foundation Models API."
        ),
        examples=[
            ["completion", "tools"],  # Ollama chat model
            ["embedding"],  # Ollama embedding model
            ["text_generation", "text_chat"],  # WatsonX chat model
            ["text_embeddings"],  # WatsonX embedding model
            [],  # no capabilities available
        ],
        json_schema_extra={
            "items": {
                "type": "string",
                "minLength": 1,
                "maxLength": 128,
                "pattern": r"^[a-z0-9_]{1,128}$",
            }
        },
    )
    embedding_dimension: int | None = Field(
        default=None,
        ge=1,
        le=65536,
        description=(
            "Vector size for embedding models. "
            "For Ollama, probed via client.embed() for models with the 'embedding' capability; "
            "None for non-embedding models. "
            "For WatsonX, sourced from the Foundation Models API spec."
        ),
        examples=[768, 1024],
        json_schema_extra={"format": "int32"},
    )


class ModelsResponse(BaseModel):
    """Response envelope for GET /api/v1/providers/{provider}/models.

    Returned when the upstream provider call succeeds. An empty ``models`` list
    is valid — it means the provider is reachable but has no models configured
    (e.g. a fresh Ollama install with nothing pulled).

    Attributes:
        provider: The provider name echoed from the path, normalised to lowercase.
        models: Available models for the provider. Empty list when none are found.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "provider": "ollama",
                    "models": [
                        {
                            "model_id": "granite4:latest",
                            "description": "Granite 4 (latest)",
                            "functions": ["completion", "tools"],
                            "embedding_dimension": None,
                        },
                        {
                            "model_id": "nomic-embed-text:latest",
                            "description": "Nomic Embed Text",
                            "functions": ["embedding"],
                            "embedding_dimension": 768,
                        },
                    ],
                },
                {
                    "provider": "watsonx",
                    "models": [
                        {
                            "model_id": "ibm/granite-3-8b-instruct",
                            "description": "IBM Granite 3 8B Instruct",
                            "functions": ["text_generation", "text_chat"],
                            "embedding_dimension": None,
                        }
                    ],
                },
                {
                    "provider": "ollama",
                    "models": [],
                },
            ]
        }
    )

    provider: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9_-]{1,64}$",
        description="Provider name that was queried (normalised to lowercase).",
        examples=["ollama", "watsonx"],
    )
    models: list[ModelInfo] = Field(
        min_length=0,
        max_length=1000,
        description="Available models for the provider. Empty list when none are configured.",
    )
