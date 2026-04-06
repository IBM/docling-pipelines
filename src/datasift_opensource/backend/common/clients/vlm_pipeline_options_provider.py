#!/usr/bin/env python3
"""
VLM Pipeline Options Providers
Base class and implementations for creating VLM pipeline options for different engines.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import requests

from common.constants import OperatorConstants
from common.util.infrastructure.logging import get_logger

logger: logging.Logger = get_logger()

IBM_CLOUD_IAM_TOKEN_URL = "https://iam.cloud.ibm.com/identity/token"
IAM_TOKEN_REQUEST_TIMEOUT = 30


class VlmPipelineOptionsProvider(ABC):
    """
    Abstract base class for VLM pipeline options providers.

    Each provider creates complete VlmPipelineOptions for a specific engine type,
    encapsulating all configuration including authentication, engine options, and
    remote services settings.
    """

    @abstractmethod
    def create_pipeline_options(self, *, preset: str, config: dict[str, Any]) -> Any:
        """
        Create complete VlmPipelineOptions for this provider.

        Args:
            preset: VLM preset name (e.g., "granite_docling", "qwen2_vl")
            config: Provider-specific configuration dictionary

        Returns:
            VlmPipelineOptions configured for this provider

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        pass

    @abstractmethod
    def validate_config(self, *, config: dict[str, Any]) -> None:
        """
        Validate provider-specific configuration.

        Args:
            config: Provider-specific configuration dictionary

        Raises:
            ValueError: If configuration is invalid or missing required fields
        """
        pass


class WatsonxPipelineOptionsProvider(VlmPipelineOptionsProvider):
    """
    Pipeline options provider for IBM watsonx.ai.

    Handles IAM token exchange and watsonx-specific configuration.
    """

    def create_pipeline_options(self, *, preset: str, config: dict[str, Any]) -> Any:
        """
        Create VlmPipelineOptions for watsonx.ai.

        Args:
            preset: VLM preset name
            config: Configuration containing:
                - vlm_api_key: IBM Cloud API key (required)
                - container_id: Watsonx container ID (required)
                - model_id: Watsonx model ID (required)
                - api_base_url: API base URL (optional)
                - container_kind: Container type, defaults to "project" (optional)
                - max_new_tokens: Maximum tokens to generate (optional)

        Returns:
            VlmPipelineOptions configured for watsonx.ai

        Raises:
            ValueError: If required configuration is missing
        """
        from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
        from docling.datamodel.vlm_engine_options import ApiVlmEngineOptions, VlmEngineType

        # Validate configuration
        self.validate_config(config=config)

        # Get IAM token
        vlm_api_key = config.get(OperatorConstants.Config.VLM_API_KEY)
        if not vlm_api_key:
            raise ValueError(f"{OperatorConstants.Config.VLM_API_KEY} is required for watsonx.ai")

        access_token = self._get_iam_access_token(api_key=vlm_api_key)
        logger.info("Successfully obtained IAM access token for watsonx.ai")

        # Prepare headers
        headers = {"Authorization": f"Bearer {access_token}"}

        # Prepare parameters
        container_kind = config.get(
            OperatorConstants.Config.VLM_WATSONX_CONTAINER_KIND, OperatorConstants.ContainerKinds.PROJECT
        )
        container_id = config.get(OperatorConstants.Config.VLM_WATSONX_CONTAINER_ID)
        vlm_model_name = config.get(OperatorConstants.Config.VLM_MODEL_NAME)
        max_new_tokens = config.get("max_new_tokens", 2048)

        if not container_id:
            raise ValueError(f"{OperatorConstants.Config.VLM_WATSONX_CONTAINER_ID} is required for watsonx.ai")
        if not vlm_model_name:
            raise ValueError(f"{OperatorConstants.Config.VLM_MODEL_NAME} is required for watsonx.ai")

        params = {
            f"{container_kind}_id": container_id,
            OperatorConstants.Config.MODEL_ID: vlm_model_name,
            OperatorConstants.Config.PARAMETERS: {
                "max_new_tokens": max_new_tokens,
                "temperature": 0.0,  # Deterministic output for document extraction
            },
        }

        # Get API base URL
        api_base_url = config.get(
            OperatorConstants.Config.VLM_API_BASE_URL,
            "https://us-south.ml.cloud.ibm.com/ml/v1/text/chat?version=2023-05-29",
        )

        logger.info(f"Using watsonx.ai model: {vlm_model_name} with {container_kind}_id: {container_id}")

        # Create engine options
        engine_options = ApiVlmEngineOptions(
            runtime_type=VlmEngineType.API,
            url=api_base_url,
            headers=headers,
            params=params,
            timeout=90,
        )

        # Create VLM options from preset
        vlm_options = VlmConvertOptions.from_preset(preset, engine_options=engine_options)

        # Ensure MARKDOWN format for API engines
        self._ensure_markdown_format(vlm_options=vlm_options, preset=preset)

        # Return complete pipeline options
        return VlmPipelineOptions(vlm_options=vlm_options, enable_remote_services=True)

    def validate_config(self, *, config: dict[str, Any]) -> None:
        """
        Validate watsonx.ai configuration.

        Args:
            config: Provider configuration to validate

        Raises:
            ValueError: If required configuration is missing
        """
        required = [
            OperatorConstants.Config.VLM_API_KEY,
            OperatorConstants.Config.VLM_WATSONX_CONTAINER_ID,
            OperatorConstants.Config.VLM_MODEL_NAME,
        ]
        missing = [k for k in required if k not in config or not config[k]]

        if missing:
            raise ValueError(
                f"Watsonx configuration missing required fields: {missing}. "
                f"Required: {OperatorConstants.Config.VLM_API_KEY} (IBM Cloud API key), "
                f"{OperatorConstants.Config.VLM_WATSONX_CONTAINER_ID} (UUID), "
                f"{OperatorConstants.Config.VLM_MODEL_NAME} (model name)"
            )

        # Validate api_base_url if provided
        api_base_url = config.get(OperatorConstants.Config.VLM_API_BASE_URL)
        if api_base_url and not api_base_url.startswith("https://"):
            raise ValueError(f"{OperatorConstants.Config.VLM_API_BASE_URL} must use HTTPS for watsonx.ai")

    @staticmethod
    def _get_iam_access_token(*, api_key: str) -> str:
        """
        Exchange IBM Cloud API key for IAM access token.

        Args:
            api_key: IBM Cloud API key

        Returns:
            IAM access token

        Raises:
            ValueError: If token exchange fails
        """
        try:
            res = requests.post(
                url=IBM_CLOUD_IAM_TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key},
                timeout=IAM_TOKEN_REQUEST_TIMEOUT,
            )
            res.raise_for_status()
            token_data = res.json()
            if "access_token" not in token_data:
                raise ValueError("Invalid IAM token response")
            return token_data["access_token"]
        except Exception as e:
            logger.error("IAM token exchange failed - authentication error occurred")
            raise ValueError(f"Failed to authenticate with watsonx: {e}") from e

    @staticmethod
    def _ensure_markdown_format(*, vlm_options: Any, preset: str) -> None:
        """Ensure MARKDOWN format for API-based VLM engines."""
        from docling.datamodel.pipeline_options_vlm_model import ResponseFormat

        if vlm_options.model_spec.response_format == ResponseFormat.DOCTAGS:
            logger.info(
                f"Preset '{preset}' uses DOCTAGS format. Converting to MARKDOWN for universal API compatibility."
            )
            vlm_options.model_spec.response_format = ResponseFormat.MARKDOWN
            vlm_options.model_spec.prompt = (
                "Convert this document page to markdown format. Include all text, tables, and structure."
            )
            vlm_options.model_spec.stop_strings = []


class OpenAIPipelineOptionsProvider(VlmPipelineOptionsProvider):
    """Pipeline options provider for OpenAI API."""

    def create_pipeline_options(self, *, preset: str, config: dict[str, Any]) -> Any:
        """
        Create VlmPipelineOptions for OpenAI.

        Args:
            preset: VLM preset name
            config: Configuration containing:
                - vlm_api_key: OpenAI API key (required)
                - model: Model name (optional, defaults to gpt-4-vision-preview)
                - api_base_url: API base URL (optional)

        Returns:
            VlmPipelineOptions configured for OpenAI
        """
        from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
        from docling.datamodel.vlm_engine_options import ApiVlmEngineOptions, VlmEngineType

        self.validate_config(config=config)

        vlm_api_key = config.get(OperatorConstants.Config.VLM_API_KEY)
        vlm_model_name = config.get(OperatorConstants.Config.VLM_MODEL_NAME)
        if not vlm_api_key:
            raise ValueError(f"{OperatorConstants.Config.VLM_API_KEY} is required for OpenAI")
        if not vlm_model_name:
            raise ValueError(f"{OperatorConstants.Config.VLM_MODEL_NAME} is required for OpenAI")

        headers = {"Authorization": f"Bearer {vlm_api_key}"}
        params = {OperatorConstants.Config.MODEL_NAME: vlm_model_name}

        api_base_url = config.get(
            OperatorConstants.Config.VLM_API_BASE_URL, "https://api.openai.com/v1/chat/completions"
        )

        engine_options = ApiVlmEngineOptions(
            runtime_type=VlmEngineType.API_OPENAI,
            url=api_base_url,
            headers=headers,
            params=params,
            timeout=90,
        )

        vlm_options = VlmConvertOptions.from_preset(preset, engine_options=engine_options)

        return VlmPipelineOptions(vlm_options=vlm_options, enable_remote_services=True)

    def validate_config(self, *, config: dict[str, Any]) -> None:
        """Validate OpenAI configuration."""
        if not config.get(OperatorConstants.Config.VLM_API_KEY):
            raise ValueError(f"{OperatorConstants.Config.VLM_API_KEY} is required for OpenAI")
        if not config.get(OperatorConstants.Config.VLM_MODEL_NAME):
            raise ValueError(f"{OperatorConstants.Config.VLM_MODEL_NAME} is required for OpenAI")


class OllamaPipelineOptionsProvider(VlmPipelineOptionsProvider):
    """Pipeline options provider for Ollama."""

    def create_pipeline_options(self, *, preset: str, config: dict[str, Any]) -> Any:
        """
        Create VlmPipelineOptions for Ollama.

        Args:
            preset: VLM preset name
            config: Configuration containing:
                - api_base_url: Ollama API URL (optional, defaults to http://localhost:11434/v1/chat/completions)
                - vlm_model_name: Ollama model name (optional, overrides preset default)

        Returns:
            VlmPipelineOptions configured for Ollama
        """
        from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
        from docling.datamodel.vlm_engine_options import ApiVlmEngineOptions, VlmEngineType

        self.validate_config(config=config)

        api_base_url = config.get(
            OperatorConstants.Config.VLM_API_BASE_URL, "http://localhost:11434/v1/chat/completions"
        )

        # Get model name from config if provided (to override preset default)
        vlm_model_name = config.get(OperatorConstants.Config.VLM_MODEL_NAME)

        # Build params with model name if provided
        params = {}
        if vlm_model_name:
            # Use 'model' key for OpenAI-compatible API
            params["model"] = vlm_model_name
            logger.info(f"Using Ollama model: {vlm_model_name}")

        engine_options = ApiVlmEngineOptions(
            runtime_type=VlmEngineType.API_OLLAMA,
            url=api_base_url,
            params=params if params else {},
            timeout=90,
        )

        vlm_options = VlmConvertOptions.from_preset(preset, engine_options=engine_options)

        logger.info(f"Using Ollama engine with API base URL: {api_base_url}")

        return VlmPipelineOptions(vlm_options=vlm_options, enable_remote_services=True)

    def validate_config(self, *, config: dict[str, Any]) -> None:
        """Ollama has minimal configuration requirements."""
        pass


class LMStudioPipelineOptionsProvider(VlmPipelineOptionsProvider):
    """Pipeline options provider for LM Studio."""

    def create_pipeline_options(self, *, preset: str, config: dict[str, Any]) -> Any:
        """
        Create VlmPipelineOptions for LM Studio.

        Args:
            preset: VLM preset name
            config: Configuration containing:
                - api_base_url: LM Studio API URL (optional, defaults to http://localhost:1234)

        Returns:
            VlmPipelineOptions configured for LM Studio
        """
        from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
        from docling.datamodel.vlm_engine_options import ApiVlmEngineOptions, VlmEngineType

        self.validate_config(config=config)

        api_base_url = config.get(OperatorConstants.Config.VLM_API_BASE_URL, "http://localhost:1234")

        engine_options = ApiVlmEngineOptions(
            runtime_type=VlmEngineType.API_LMSTUDIO,
            url=api_base_url,
            timeout=90,
        )

        vlm_options = VlmConvertOptions.from_preset(preset, engine_options=engine_options)

        logger.info(f"Using LM Studio engine with API base URL: {api_base_url}")

        return VlmPipelineOptions(vlm_options=vlm_options, enable_remote_services=True)

    def validate_config(self, *, config: dict[str, Any]) -> None:
        """LM Studio has minimal configuration requirements."""
        pass


class GenericApiPipelineOptionsProvider(VlmPipelineOptionsProvider):
    """Pipeline options provider for generic API endpoints."""

    def create_pipeline_options(self, *, preset: str, config: dict[str, Any]) -> Any:
        """
        Create VlmPipelineOptions for generic API.

        Args:
            preset: VLM preset name
            config: Configuration containing:
                - api_base_url: API URL (required)
                - headers: Custom headers dict (optional)
                - params: Custom params dict (optional)
                - vlm_api_key: API key for Bearer token auth (optional)

        Returns:
            VlmPipelineOptions configured for generic API
        """
        from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
        from docling.datamodel.vlm_engine_options import ApiVlmEngineOptions, VlmEngineType

        self.validate_config(config=config)

        # Start with custom headers if provided
        headers = config.get("headers", {}).copy() if config.get("headers") else {}

        # Add Bearer token if vlm_api_key provided and Authorization not already set
        vlm_api_key = config.get(OperatorConstants.Config.VLM_API_KEY)
        if vlm_api_key and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {vlm_api_key}"

        # Get custom params
        params = (
            config.get(OperatorConstants.Config.PARAMETERS, {}).copy()
            if config.get(OperatorConstants.Config.PARAMETERS)
            else {}
        )

        api_base_url = config.get(OperatorConstants.Config.VLM_API_BASE_URL)
        if not api_base_url:
            raise ValueError(f"{OperatorConstants.Config.VLM_API_BASE_URL} is required for generic API")

        engine_options = ApiVlmEngineOptions(
            runtime_type=VlmEngineType.API,
            url=api_base_url,
            headers=headers if headers else {},
            params=params if params else {},
            timeout=90,
        )

        vlm_options = VlmConvertOptions.from_preset(preset, engine_options=engine_options)

        logger.info(f"Using generic API engine with URL: {api_base_url}")

        return VlmPipelineOptions(vlm_options=vlm_options, enable_remote_services=True)

    def validate_config(self, *, config: dict[str, Any]) -> None:
        """Validate generic API configuration."""
        if not config.get(OperatorConstants.Config.VLM_API_BASE_URL):
            raise ValueError(f"{OperatorConstants.Config.VLM_API_BASE_URL} is required for generic API")


class TransformersPipelineOptionsProvider(VlmPipelineOptionsProvider):
    """Pipeline options provider for local Transformers inference."""

    def create_pipeline_options(self, *, preset: str, config: dict[str, Any]) -> Any:
        """
        Create VlmPipelineOptions for Transformers.

        Args:
            preset: VLM preset name
            config: Configuration (minimal requirements for local inference)

        Returns:
            VlmPipelineOptions configured for Transformers
        """
        from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
        from docling.datamodel.vlm_engine_options import TransformersVlmEngineOptions

        self.validate_config(config=config)

        engine_options = TransformersVlmEngineOptions()
        vlm_options = VlmConvertOptions.from_preset(preset, engine_options=engine_options)

        logger.info("Using Transformers engine for local inference")

        return VlmPipelineOptions(vlm_options=vlm_options)

    def validate_config(self, *, config: dict[str, Any]) -> None:
        """Transformers has minimal configuration requirements."""
        pass


class MlxPipelineOptionsProvider(VlmPipelineOptionsProvider):
    """Pipeline options provider for MLX inference (macOS optimized)."""

    def create_pipeline_options(self, *, preset: str, config: dict[str, Any]) -> Any:
        """
        Create VlmPipelineOptions for MLX.

        Args:
            preset: VLM preset name
            config: Configuration (minimal requirements for local inference)

        Returns:
            VlmPipelineOptions configured for MLX
        """
        from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
        from docling.datamodel.vlm_engine_options import MlxVlmEngineOptions

        self.validate_config(config=config)

        engine_options = MlxVlmEngineOptions()
        vlm_options = VlmConvertOptions.from_preset(preset, engine_options=engine_options)

        logger.info("Using MLX engine for local inference")

        return VlmPipelineOptions(vlm_options=vlm_options)

    def validate_config(self, *, config: dict[str, Any]) -> None:
        """MLX has minimal configuration requirements."""
        pass


class VlmPipelineOptionsProviderFactory:
    """
    Factory for creating VLM pipeline options providers.

    Maps engine types to their corresponding provider implementations.
    """

    _providers: ClassVar[dict[str, type[VlmPipelineOptionsProvider]]] = {
        OperatorConstants.Config.VLM_ENGINE_API: GenericApiPipelineOptionsProvider,
        OperatorConstants.Config.VLM_ENGINE_API_WATSONX: WatsonxPipelineOptionsProvider,
        OperatorConstants.Config.VLM_ENGINE_API_OPENAI: OpenAIPipelineOptionsProvider,
        OperatorConstants.Config.VLM_ENGINE_API_OLLAMA: OllamaPipelineOptionsProvider,
        OperatorConstants.Config.VLM_ENGINE_API_LMSTUDIO: LMStudioPipelineOptionsProvider,
        OperatorConstants.Config.VLM_ENGINE_TRANSFORMERS: TransformersPipelineOptionsProvider,
        OperatorConstants.Config.VLM_ENGINE_MLX: MlxPipelineOptionsProvider,
    }

    @classmethod
    def get_provider(cls, *, engine_type: str | None) -> VlmPipelineOptionsProvider:
        """
        Get pipeline options provider for the specified engine type.

        Args:
            engine_type: VLM engine type (e.g., "api", "api_watsonx", "transformers", "mlx")

        Returns:
            Instance of appropriate VlmPipelineOptionsProvider

        Raises:
            ValueError: If engine_type is unknown
        """
        # Default to Transformers if no engine type specified
        if not engine_type:
            engine_type = OperatorConstants.Config.VLM_ENGINE_TRANSFORMERS

        provider_class = cls._providers.get(engine_type)
        if not provider_class:
            raise ValueError(f"Unknown VLM engine type: {engine_type}. Supported types: {list(cls._providers.keys())}")

        return provider_class()

    @classmethod
    def register_provider(cls, *, engine_type: str, provider_class: type[VlmPipelineOptionsProvider]) -> None:
        """
        Register a custom pipeline options provider.

        Args:
            engine_type: Engine type identifier
            provider_class: Provider class to register
        """
        cls._providers[engine_type] = provider_class
