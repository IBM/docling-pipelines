# Copyright IBM Corp. 2025
# -License-Identifier: Apache-2.0

"""PII and HAP detection service using common LLM infrastructure.

This service provides a unified interface for PII/HAP detection across different
providers (WatsonX, LiteLLM) by wrapping the common port interfaces.
"""

import json
import os
import re
from typing import Any

from docpipe.core.adapters.llm_adapter_factory import LLMAdapterFactory
from docpipe.core.constants.constants import LLMConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.quality.pii_and_hap.domain.models import (
    PIIHAPDetectionResponse,
    convert_detection_dicts_to_results,
)
from docpipe.core.ports.llm_inference_port import LLMInferencePort
from docpipe.core.ports.text_detection_port import TextDetectionPort
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)

# Prompt cache for LLM-based detection
_prompt_cache: dict[str, Any] = {"static_prompt": None}
PROMPT_EXAMPLES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pii_prompt_examples.json")


class PIIHAPService:
    """Service for PII and HAP detection using common LLM infrastructure.

    This service provides a unified interface for PII/HAP detection that works
    with different providers through the common port interfaces:
    - WatsonX: Uses TextDetectionPort (specialized detection API)
    - LiteLLM: Uses LLMInferencePort (prompt-based detection)

    The service handles:
    - Provider-specific adapter creation
    - Prompt generation for LLM-based detection
    - Response parsing and formatting
    - Error handling and logging
    """

    def __init__(
        self,
        *,
        provider: str,
        model_id: str,
        provider_config: dict[str, Any] | None = None,
    ):
        """Initialize PII/HAP detection service.

        Args:
            provider: Provider name ('watsonx' or 'litellm')
            model_id: Model identifier for the provider
            provider_config: Provider-specific configuration

        Raises:
            ValueError: If provider is not supported
        """
        self.provider = provider.lower()
        self.model_id = model_id
        self.provider_config = provider_config or {}

        # Determine detection path based on provider
        if self.provider == "watsonx":
            # Use specialized TextDetectionPort for WatsonX
            self.adapter: TextDetectionPort | LLMInferencePort = LLMAdapterFactory.create_text_detection_adapter(
                provider=self.provider,
                model_id=self.model_id,
                provider_config=self.provider_config,
            )
            self.use_specialized_api = True
            logger.info("Initialized PIIHAPService with WatsonX TextDetectionPort")

        elif self.provider == "litellm":
            # Use LLMInferencePort for prompt-based detection
            self.adapter = LLMAdapterFactory.create_inference_adapter(
                provider=self.provider,
                model_id=self.model_id,
                provider_config=self.provider_config,
            )
            self.use_specialized_api = False
            logger.info("Initialized PIIHAPService with LiteLLM InferencePort")

        else:
            raise ValueError(f"Unsupported provider: {self.provider}. Supported providers: watsonx, litellm")

        # Validate adapter configuration
        self._validate_adapter()

    def _validate_adapter(self) -> None:
        """Validate adapter configuration on initialization.

        Raises:
            DocpipeException: If adapter validation fails
        """
        result = self.adapter.validate()

        # Log warnings
        if result.get(LLMConstants.ValidationKeys.WARNINGS):
            for warning in result[LLMConstants.ValidationKeys.WARNINGS]:
                logger.warning(f"Adapter validation warning: {warning}")

        # Raise error if validation failed
        if not result.get(LLMConstants.ValidationKeys.VALID, True):
            errors = result.get(LLMConstants.ValidationKeys.ERRORS, ["Unknown validation error"])
            raise DocpipeException(
                message=f"Adapter validation failed: {'; '.join(errors)}",
                status_code=400,
            )

    def detect_pii_hap(self, *, payload: dict[str, Any]) -> PIIHAPDetectionResponse:
        """Detect PII and HAP in the given text.

        Args:
            payload: Detection request payload containing:
                - input: Text to analyze
                - detectors: Dictionary of detector configurations
                    - pii: PII detection config with threshold
                    - hap: HAP detection config with threshold

        Returns:
            PIIHAPDetectionResponse containing list of detections

        Raises:
            ValueError: If payload is invalid
            DocpipeException: If detection fails
        """
        text = payload.get(OperatorConstants.PIIHAP.INPUT_FIELD, "")
        if not text:
            raise ValueError("Input text cannot be empty")

        try:
            if self.use_specialized_api:
                # WatsonX path: Use specialized detection API
                return self._detect_via_specialized_api(payload=payload, text=text)
            else:
                # LiteLLM path: Use prompt-based detection
                return self._detect_via_llm(payload=payload, text=text)

        except DocpipeException:
            raise
        except Exception as exc:
            logger.error(f"Error during PII/HAP detection: {exc}")
            raise DocpipeException(message=f"PII/HAP detection failed: {exc!s}", status_code=500) from exc

    def _detect_via_specialized_api(
        self,
        *,
        payload: dict[str, Any],
        text: str,
    ) -> PIIHAPDetectionResponse:
        """Detect using WatsonX native text detection adapter.

        Args:
            payload: Full detection payload
            text: Input text

        Returns:
            PIIHAPDetectionResponse with detections
        """
        # Cast to TextDetectionPort for type safety
        adapter = self.adapter
        if not isinstance(adapter, TextDetectionPort):
            raise TypeError("Expected TextDetectionPort for specialized API")

        detectors = payload.get("detectors")
        result_dict = adapter.detect(text=text, detectors=detectors)

        # Check for errors
        if not result_dict.get("success", False):
            error_msg = result_dict.get("error", "Unknown error")
            raise DocpipeException(message=f"Text detection failed: {error_msg}", status_code=500)

        # Convert to domain models
        detection_results = convert_detection_dicts_to_results(result_dict.get("detections", []))

        return PIIHAPDetectionResponse(detections=detection_results, input_text=text)

    def _detect_via_llm(
        self,
        *,
        payload: dict[str, Any],
        text: str,
    ) -> PIIHAPDetectionResponse:
        """Detect using LLM with prompts.

        Args:
            payload: Full detection payload
            text: Input text

        Returns:
            PIIHAPDetectionResponse with detections
        """
        # Cast to LLMInferencePort for type safety
        adapter = self.adapter
        if not isinstance(adapter, LLMInferencePort):
            raise TypeError("Expected LLMInferencePort for LLM-based detection")

        # Extract thresholds
        detectors = payload.get("detectors", {})
        hap_threshold = detectors.get("hap", {}).get("threshold", 0.8)
        pii_threshold = detectors.get("pii", {}).get("threshold", 0.5)

        # Build prompt
        static_prompt = self._load_static_prompt()
        dynamic_prompt = (
            f"Now analyze the following text, applying thresholds "
            f"hap={hap_threshold} and pii={pii_threshold}:\n\n"
            f'"""{text}"""\n'
        )
        full_prompt = static_prompt + dynamic_prompt

        try:
            raw_response = adapter.chat(
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.0,
            )

            if not raw_response:
                raise DocpipeException(message="LLM inference failed: Model returned empty response", status_code=500)

            # Parse JSON response
            try:
                result_dict = json.loads(raw_response)
            except json.JSONDecodeError as err:
                # Try to extract JSON from markdown or mixed content
                match = re.search(r"{.*}", raw_response, re.DOTALL)
                if match:
                    try:
                        result_dict = json.loads(match.group(0))
                    except json.JSONDecodeError:
                        # Log full response at DEBUG level only to avoid PII leakage
                        logger.debug(f"Failed to parse extracted JSON. Full response: {raw_response}")
                        raise DocpipeException(
                            message="LLM inference failed: Invalid JSON format in model response",
                            status_code=500,
                        ) from err
                else:
                    # Log full response at DEBUG level only to avoid PII leakage in error messages
                    logger.debug(f"Failed to parse JSON from model response. Full response: {raw_response}")
                    raise DocpipeException(
                        message="LLM inference failed: Model response does not contain valid JSON",
                        status_code=500,
                    ) from err
        except DocpipeException:
            # Re-raise DocpipeException as-is
            raise
        except Exception as exc:
            # Wrap unexpected errors with consistent error message format
            logger.error(f"Unexpected error during LLM inference: {exc}")
            raise DocpipeException(
                message=f"LLM inference failed: {exc!s}",
                status_code=500,
            ) from exc

        # Convert to domain models
        detection_results = convert_detection_dicts_to_results(result_dict.get("detections", []))

        return PIIHAPDetectionResponse(detections=detection_results, input_text=text)

    def _load_static_prompt(self) -> str:
        """Load and cache the static prompt with examples from JSON file.

        Returns:
            Formatted prompt string with description and examples
        """
        if _prompt_cache["static_prompt"] is not None:
            return _prompt_cache["static_prompt"]

        with open(PROMPT_EXAMPLES_PATH, encoding="utf-8") as f:
            data = json.load(f)

        description = data.get("description", "")
        examples = data.get("examples", [])

        prompt = description + "\n\n"
        for ex in examples:
            input_text = ex["input"]
            output_json = json.dumps(ex["output"], indent=2)
            prompt += f'Input:\n"""{input_text}"""\n\nOutput:\n{output_json}\n\n'

        _prompt_cache["static_prompt"] = prompt
        return prompt

    def cleanup(self) -> None:
        """Cleanup resources if needed.

        This method is called when the service is no longer needed.
        Currently a no-op as the common adapters handle their own cleanup.
        """
        pass
