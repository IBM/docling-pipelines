"""Watsonx.ai integration for docpipe."""

from docpipe.integrations.watsonx.client import WatsonXClient
from docpipe.integrations.watsonx.model_validator import (
    get_available_foundation_models,
    validate_model_id,
)

__all__ = ["WatsonXClient", "get_available_foundation_models", "validate_model_id"]
