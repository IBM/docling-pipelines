"""Tests for EntityExtractionAdapterFactory — registry routing, build_adapter_config,
create_adapter, and get_supported_modes.

These are factory-level tests; per-class extraction behaviour is tested in
test_llm_entity_adapter.py and test_docling_entity_adapter.py.
"""

from unittest.mock import MagicMock, patch

import pytest

import docpipe.core.operators.extract.adapters.outbound.entity_extraction  # noqa: F401  (triggers registration)
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.extract.adapters.outbound.entity_extraction.docling_entity_adapter import (
    DoclingEntityAdapter,
)
from docpipe.core.operators.extract.adapters.outbound.entity_extraction.litellm_entity_adapter import (
    LiteLLMEntityAdapter,
)
from docpipe.core.operators.extract.adapters.outbound.entity_extraction.llm_entity_adapter import LLMEntityAdapter
from docpipe.core.operators.extract.adapters.outbound.entity_extraction.watsonx_entity_adapter import (
    WatsonxEntityAdapter,
)
from docpipe.core.operators.extract.adapters.outbound.factories.entity_extraction_adapter_factory import (
    EntityExtractionAdapterFactory,
)
from docpipe.core.operators.extract.domain import EntityExtractionMode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entity_cfg(provider_config: dict | None = None) -> dict:
    return {
        OperatorConstants.Config.PROVIDER_CONFIG: provider_config or {},
        OperatorConstants.Columns.OUTPUT_COLUMN: "entities",
        OperatorConstants.Config.EXPAND_EXTRACTED_DATA: False,
    }


# ---------------------------------------------------------------------------
# Registry state
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_registry_contains_exactly_three_adapters(self):
        assert set(EntityExtractionAdapterFactory._registry.keys()) == {"litellm", "watsonx", "docling"}

    def test_litellm_maps_to_litellm_entity_adapter(self):
        assert EntityExtractionAdapterFactory._registry["litellm"] is LiteLLMEntityAdapter

    def test_watsonx_maps_to_watsonx_entity_adapter(self):
        assert EntityExtractionAdapterFactory._registry["watsonx"] is WatsonxEntityAdapter

    def test_docling_maps_to_docling_entity_adapter(self):
        assert EntityExtractionAdapterFactory._registry["docling"] is DoclingEntityAdapter

    def test_none_is_absent_from_registry(self):
        assert "none" not in EntityExtractionAdapterFactory._registry

    def test_llm_entity_adapter_base_is_not_registered(self):
        """LLMEntityAdapter is a pure base — must not occupy any registry slot."""
        assert LLMEntityAdapter not in EntityExtractionAdapterFactory._registry.values()


# ---------------------------------------------------------------------------
# get_supported_modes
# ---------------------------------------------------------------------------


class TestGetSupportedModes:
    def test_includes_all_registered_adapters(self):
        modes = EntityExtractionAdapterFactory.get_supported_modes()
        assert "litellm" in modes
        assert "watsonx" in modes
        assert "docling" in modes

    def test_includes_none(self):
        assert "none" in EntityExtractionAdapterFactory.get_supported_modes()

    def test_none_not_duplicated(self):
        modes = EntityExtractionAdapterFactory.get_supported_modes()
        assert modes.count("none") == 1


# ---------------------------------------------------------------------------
# build_provider_config (per-adapter)
# ---------------------------------------------------------------------------


class TestBuildProviderConfig:
    def test_litellm_sets_provider_litellm(self):
        cfg = _entity_cfg({"model_id": "openai/gpt-4o", "temperature": 0.1})
        result = LiteLLMEntityAdapter.build_provider_config(entity_extraction_config=cfg, doc_column="content")
        assert result[OperatorConstants.Config.PROVIDER] == OperatorConstants.ExtractionModes.ENTITY_MODE_LITELLM
        assert result[OperatorConstants.Config.MODEL_NAME] == "openai/gpt-4o"

    def test_watsonx_sets_provider_watsonx(self):
        cfg = _entity_cfg({"model_id": "ibm/granite-13b-chat-v2"})
        result = WatsonxEntityAdapter.build_provider_config(entity_extraction_config=cfg, doc_column="content")
        assert result[OperatorConstants.Config.PROVIDER] == OperatorConstants.ExtractionModes.ENTITY_MODE_WATSONX

    def test_watsonx_provider_is_not_litellm(self):
        """Guard: WatsonxEntityAdapter must produce provider='watsonx', not 'litellm'."""
        cfg = _entity_cfg({"model_id": "ibm/granite-13b-chat-v2"})
        result = WatsonxEntityAdapter.build_provider_config(entity_extraction_config=cfg, doc_column="content")
        assert result[OperatorConstants.Config.PROVIDER] != OperatorConstants.ExtractionModes.ENTITY_MODE_LITELLM

    def test_docling_passes_through_vlm_pipeline(self):
        vlm_cfg = {"vlm_pipeline": {"preset": "granite_docling"}}
        cfg = _entity_cfg(vlm_cfg)
        result = DoclingEntityAdapter.build_provider_config(entity_extraction_config=cfg, doc_column="content")
        assert "vlm_pipeline" in result
        assert result["vlm_pipeline"] == {"preset": "granite_docling"}

    def test_docling_without_vlm_pipeline_omits_key(self):
        result = DoclingEntityAdapter.build_provider_config(
            entity_extraction_config=_entity_cfg(), doc_column="content"
        )
        assert "vlm_pipeline" not in result


# ---------------------------------------------------------------------------
# create_adapter
# ---------------------------------------------------------------------------


class TestCreateAdapter:
    def _litellm_entity_cfg(self) -> dict:
        return {
            OperatorConstants.Config.PROVIDER_CONFIG: {
                "model_id": "openai/granite4:latest",
                "api_base": "http://localhost:11434/v1",
                "api_key": "test",  # pragma: allowlist secret
            }
        }

    def _watsonx_entity_cfg(self) -> dict:
        return {
            OperatorConstants.Config.PROVIDER_CONFIG: {
                "model_id": "ibm/granite-13b-chat-v2",
                "url": "https://us-south.ml.cloud.ibm.com",
                "api_key": "test",  # pragma: allowlist secret
                "project_id": "test-project",
            }
        }

    def test_none_mode_returns_none(self):
        result = EntityExtractionAdapterFactory.create_adapter(
            mode=EntityExtractionMode.NONE,
            entity_extraction_config={},
            global_config={},
            doc_column="content",
        )
        assert result is None

    def test_litellm_mode_returns_litellm_entity_adapter(self):
        with patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_inference_adapter") as mock_f:
            mock_f.return_value = MagicMock()
            adapter = EntityExtractionAdapterFactory.create_adapter(
                mode=EntityExtractionMode.LITELLM,
                entity_extraction_config=self._litellm_entity_cfg(),
                global_config={},
                doc_column="content",
            )
        assert isinstance(adapter, LiteLLMEntityAdapter)
        assert adapter.provider == "litellm"

    def test_watsonx_mode_returns_watsonx_entity_adapter(self):
        with patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_inference_adapter") as mock_f:
            mock_f.return_value = MagicMock()
            adapter = EntityExtractionAdapterFactory.create_adapter(
                mode=EntityExtractionMode.WATSONX,
                entity_extraction_config=self._watsonx_entity_cfg(),
                global_config={},
                doc_column="content",
            )
        assert isinstance(adapter, WatsonxEntityAdapter)
        assert adapter.provider == "watsonx"

    def test_unknown_mode_raises_value_error_mentioning_none(self):
        class _FakeMode:
            value = "unknown_provider"

        with pytest.raises(ValueError, match=r"Supported modes:.*none"):
            EntityExtractionAdapterFactory.create_adapter(
                mode=_FakeMode(),  # type: ignore[arg-type]
                entity_extraction_config={},
                global_config={},
                doc_column="content",
            )
