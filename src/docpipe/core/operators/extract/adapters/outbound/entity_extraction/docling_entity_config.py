"""Pydantic config model for the Docling-based entity extraction adapter."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

ADAPTER_NAME = "docling"


class DoclingEntityConfig(BaseModel):
    """User-facing provider_config for the Docling entity extraction provider.

    Describes the fields the user writes inside ``entity_extraction.provider_config``
    when selecting the ``docling`` provider in an Extract operator node.
    """

    model_config = ConfigDict(extra="ignore")

    vlm_pipeline: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Custom VLM model configuration for Docling entity extraction. "
            "Requires 'model_type': 'inline' and 'inline_model' with 'repo_id' (HuggingFace model). "
            "Note: Only inline models are supported; API models are not supported by DocumentExtractor."
        ),
    )
