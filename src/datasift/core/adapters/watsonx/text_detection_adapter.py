"""WatsonX text detection adapter implementation.

This module provides the WatsonX-specific implementation of the TextDetectionPort
interface for detecting PII and HAP (Hate, Abuse, and Profanity) in text.
"""

import json
import logging
from typing import Any

from datasift.core.ports.text_detection_port import TextDetectionPort
from datasift.integrations.watsonx.client import WatsonXClient

logger = logging.getLogger(__name__)


class WatsonXTextDetectionAdapter(TextDetectionPort):
    """WatsonX implementation of the text detection port.

    This adapter uses WatsonX AI models to detect PII (Personally Identifiable Information)
    and HAP (Hate, Abuse, and Profanity) in text content.

    Attributes:
        model_id: WatsonX model identifier
        provider_config: WatsonX-specific configuration
        client: WatsonX client instance
    """

    def __init__(
        self,
        *,
        model_id: str,
        provider_config: dict[str, Any],
    ) -> None:
        """Initialize the WatsonX text detection adapter.

        Args:
            model_id: WatsonX model identifier for text detection
            provider_config: WatsonX-specific configuration including:
                - api_key: WatsonX API key
                - project_id: WatsonX project ID
                - url: WatsonX API endpoint URL
                - max_tokens: Maximum tokens for response (default: 2000)
                - temperature: Sampling temperature (default: 0.0)

        Raises:
            ValueError: If required configuration is missing
        """
        self.model_id = model_id
        self.provider_config = provider_config

        # Validate required configuration
        required_keys = ["api_key", "project_id", "url"]
        missing_keys = [key for key in required_keys if key not in provider_config]
        if missing_keys:
            raise ValueError(f"Missing required WatsonX configuration: {missing_keys}")

        # Initialize WatsonX client
        self.client = WatsonXClient(
            model_name=model_id,
            api_key=provider_config["api_key"],
            container_id=provider_config["project_id"],
            api_base=provider_config["url"],
        )

        # Set default generation parameters
        self.max_tokens = provider_config.get("max_tokens", 2000)
        self.temperature = provider_config.get("temperature", 0.0)

        logger.info(f"Initialized WatsonX text detection adapter with model: {model_id}")

    def detect(
        self,
        *,
        text: str,
        detection_types: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Perform text detection using WatsonX.

        Args:
            text: Input text to analyze
            detection_types: Optional list of detection types (e.g., ["pii", "hap"])
            **kwargs: Additional parameters including 'prompt' for detection instructions

        Returns:
            Detection results dict with structure:
            {
                "success": bool,
                "detections": list[dict],
                "error": str | None
            }

        Raises:
            ValueError: If text is empty or detection fails
        """
        if not text or not text.strip():
            raise ValueError("Input text cannot be empty")

        # Get prompt from kwargs or use default
        prompt = kwargs.get("prompt", "Detect PII and HAP in the following text:")

        try:
            result = self.detect_entities(text=text, prompt=prompt)
            return {
                "success": result.get("detected", False),
                "detections": result.get("entities", []),
                "error": None,
            }
        except Exception as e:
            logger.error(f"Text detection failed: {e}")
            return {
                "success": False,
                "detections": [],
                "error": str(e),
            }

    def detect_entities(
        self,
        *,
        text: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Detect entities (PII/HAP) in text using a detection prompt.

        Args:
            text: Input text to analyze for entities
            prompt: Detection prompt that instructs the model what to detect

        Returns:
            Dictionary containing detection results with structure:
            {
                "detected": bool,
                "entities": list[dict],
                "confidence": float,
                "raw_response": str
            }

        Raises:
            ValueError: If text or prompt is empty, or if detection fails
        """
        if not text or not text.strip():
            raise ValueError("Input text cannot be empty")
        if not prompt or not prompt.strip():
            raise ValueError("Detection prompt cannot be empty")

        try:
            # Construct the full prompt with text
            full_prompt = f"{prompt}\n\nText to analyze:\n{text}"

            # Call WatsonX for detection
            response = self.client.generate(
                prompt=full_prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            # Parse response
            result = self._parse_detection_response(response)
            return result

        except Exception as e:
            logger.error(f"Entity detection failed: {e}")
            raise ValueError(f"Entity detection failed: {e}") from e

    def detect_entities_batch(
        self,
        *,
        texts: list[str],
        prompt: str,
    ) -> list[dict[str, Any]]:
        """Detect entities in multiple texts using batch processing.

        Args:
            texts: List of input texts to analyze
            prompt: Detection prompt that instructs the model what to detect

        Returns:
            List of detection result dictionaries, one per input text

        Raises:
            ValueError: If texts list is empty or if batch detection fails
        """
        if not texts:
            raise ValueError("Input texts list cannot be empty")
        if not prompt or not prompt.strip():
            raise ValueError("Detection prompt cannot be empty")

        results = []
        for text in texts:
            try:
                result = self.detect_entities(text=text, prompt=prompt)
                results.append(result)
            except Exception as e:
                logger.warning(f"Failed to detect entities in text: {e}")
                # Return empty result for failed detection
                results.append(
                    {
                        "detected": False,
                        "entities": [],
                        "confidence": 0.0,
                        "error": str(e),
                    }
                )

        return results

    def _parse_detection_response(self, response: str) -> dict[str, Any]:
        """Parse the WatsonX detection response into structured format.

        Args:
            response: Raw response string from WatsonX

        Returns:
            Structured detection result dictionary
        """
        try:
            # Try to parse as JSON first
            parsed = json.loads(response)
            return {
                "detected": parsed.get("detected", False),
                "entities": parsed.get("entities", []),
                "confidence": parsed.get("confidence", 0.0),
                "raw_response": response,
            }
        except json.JSONDecodeError:
            # If not JSON, return raw response with basic structure
            logger.warning("Response is not valid JSON, returning raw response")
            return {
                "detected": "yes" in response.lower() or "true" in response.lower(),
                "entities": [],
                "confidence": 0.5,
                "raw_response": response,
            }
