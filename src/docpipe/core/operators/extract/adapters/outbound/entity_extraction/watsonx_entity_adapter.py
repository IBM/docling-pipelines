"""Watsonx entity extraction adapter.

Thin subclass of LLMEntityAdapter that declares the "watsonx" provider identity,
owns the WatsonxEntityConfig schema, and self-registers with EntityExtractionAdapterFactory.
All extraction logic is inherited from LLMEntityAdapter.
"""

from pydantic import BaseModel

from docpipe.core.constants import OperatorConstants
from docpipe.core.operators.extract.adapters.outbound.entity_extraction.llm_entity_adapter import LLMEntityAdapter
from docpipe.core.operators.extract.adapters.outbound.factories.entity_extraction_adapter_factory import (
    register_entity_extraction_adapter,
)


@register_entity_extraction_adapter
class WatsonxEntityAdapter(LLMEntityAdapter):
    """Watsonx entity extraction adapter.

    Inherits all extraction logic from LLMEntityAdapter. Declares the "watsonx"
    ADAPTER_NAME so the factory can route to this class via the registry.
    ``build_provider_config`` is inherited from LLMEntityAdapter.

    Attributes:
        ADAPTER_NAME: Registry key "watsonx"
        ADAPTER_DISPLAY_NAME: Display name "watsonx"
    """

    ADAPTER_NAME = OperatorConstants.ExtractionModes.ENTITY_MODE_WATSONX
    ADAPTER_DISPLAY_NAME = "watsonx"

    @staticmethod
    def get_config_schema() -> type[BaseModel]:
        """Return the Pydantic config model class for this adapter."""
        from docpipe.core.operators.extract.adapters.outbound.entity_extraction.llm_entity_config import (
            WatsonxEntityConfig,
        )

        return WatsonxEntityConfig
