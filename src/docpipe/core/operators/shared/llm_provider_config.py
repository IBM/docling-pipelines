"""Shared Pydantic config models for LLM-based providers."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LLMProviderConfig(BaseModel):
    """User-facing provider_config for LiteLLM-backed providers.

    Describes the fields the user writes inside ``provider_config`` when
    selecting the ``litellm`` provider in EmbeddingsOperator or
    DocumentClassifierOperator.
    """

    model_config = ConfigDict(extra="ignore")

    model_id: str | None = Field(
        default=None,
        description="Model identifier in LiteLLM format (e.g., 'openai/text-embedding-3-small', 'ollama/llama3.2').",
    )
    api_base: str | None = Field(
        default=None,
        description="Custom API endpoint URL (e.g., 'http://localhost:11434/v1').",
    )
    api_key: str | None = Field(
        default=None,
        description="API key for authentication. Supports $ENV_VAR references.",
    )


class WatsonxProviderConfig(LLMProviderConfig):
    """User-facing provider_config for IBM watsonx-backed providers.

    Extends LLMProviderConfig with watsonx-specific fields. Used when selecting
    the ``watsonx`` provider in EmbeddingsOperator or DocumentClassifierOperator.
    """

    model_config = ConfigDict(extra="ignore")

    url: str | None = Field(
        default=None,
        description="Watsonx.ai API endpoint URL. Accepts either 'url' or 'api_base'.",
    )
    container_kind: Literal["project", "space"] = Field(
        default="project",
        description="Container type: 'project' or 'space'.",
    )
    container_id: str | None = Field(
        default=None,
        description="Container ID (project_id or space_id). Can be set via WATSONX_CONTAINER_ID env var.",
    )
