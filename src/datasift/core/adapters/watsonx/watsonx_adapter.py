"""Unified WatsonX adapter for inference, embeddings, and text detection.

This adapter consolidates all WatsonX capabilities into a single class,
providing a unified interface for:
- LLM inference (chat and text generation)
- Embedding generation
- Text detection (PII/HAP)
"""

import json
import logging
from typing import Any

from datasift.core.ports.llm_embedding_port import LLMEmbeddingPort
from datasift.core.ports.llm_inference_port import LLMInferencePort
from datasift.core.ports.text_detection_port import TextDetectionPort
from datasift.integrations.watsonx.client import WatsonXClient

logger = logging.getLogger(__name__)


class WatsonXAdapter(LLMInferencePort, LLMEmbeddingPort, TextDetectionPort):
    """Unified WatsonX adapter for all LLM capabilities.

    This adapter provides a single interface for WatsonX operations including
    inference, embeddings, and specialized text detection APIs.

    Attributes:
        client: WatsonX client instance
        model_name: Default model name (can be overridden per method call)
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
        container_id: str | None = None,
        container_kind: str | None = None,
        timeout: int = 120,
        model_name: str | None = None,
    ):
        """Initialize unified WatsonX adapter.

        Args:
            api_key: WatsonX API key
            api_base: WatsonX API base URL
            container_id: WatsonX container ID (project_id or space_id)
            container_kind: WatsonX container kind ('project', 'space', or 'catalog')
            timeout: Request timeout in seconds
            model_name: Default model name (optional, can be overridden per method)
        """
        self.client = WatsonXClient(
            model_name=model_name or "",  # Can be empty, will be set per method
            api_key=api_key,
            container_id=container_id,
            api_base=api_base,
            container_kind=container_kind,
            timeout=timeout,
        )
        self.model_name = model_name
        self._dimension: int | None = None

    # ==================== Inference Methods ====================

    def chat(
        self,
        *,
        model_name: str | None = None,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> str:
        """Multi-turn chat completion using WatsonX.

        Args:
            model_name: Model identifier (uses default if not provided)
            messages: List of message dicts with 'role' and 'content' keys
            response_format: Optional response format specification (passed to kwargs)
            **kwargs: WatsonX-specific parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text response

        Raises:
            Exception: WatsonX client errors
        """
        # Add response_format to kwargs if provided
        if response_format:
            kwargs["response_format"] = response_format

        # Use provided model_name or fall back to default
        effective_model = model_name or self.model_name
        if effective_model:
            self.client.model_name = effective_model

        return self.client.chat(messages=messages, **kwargs)

    def generate(
        self,
        *,
        model_name: str | None = None,
        prompt: str,
        response_format: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> str:
        """Single-turn text generation using WatsonX.

        Args:
            model_name: Model identifier (uses default if not provided)
            prompt: Input prompt text
            response_format: Optional response format specification (passed to kwargs)
            **kwargs: WatsonX-specific parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text response

        Raises:
            Exception: WatsonX client errors
        """
        # Add response_format to kwargs if provided
        if response_format:
            kwargs["response_format"] = response_format

        # Use provided model_name or fall back to default
        effective_model = model_name or self.model_name
        if effective_model:
            self.client.model_name = effective_model

        return self.client.generate(prompt=prompt, **kwargs)

    # ==================== Embedding Methods ====================

    def generate_embeddings(
        self,
        *,
        model_name: str | None = None,
        text: str,
        **kwargs: Any,
    ) -> list[float]:
        """Generate embeddings for single text using WatsonX.

        Args:
            model_name: Embedding model identifier (uses default if not provided)
            text: Input text to embed
            **kwargs: Additional WatsonX parameters

        Returns:
            List of embedding values (floats)

        Raises:
            Exception: WatsonX client errors
        """
        # Use provided model_name or fall back to default
        effective_model = model_name or self.model_name
        if effective_model:
            self.client.model_name = effective_model

        return self.client.generate_embeddings(text=text)

    def generate_embeddings_batch(
        self,
        *,
        model_name: str | None = None,
        texts: list[str],
        **kwargs: Any,
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts using WatsonX.

        Args:
            model_name: Embedding model identifier (uses default if not provided)
            texts: List of input texts to embed
            **kwargs: Additional WatsonX parameters

        Returns:
            List of embedding lists, one per input text

        Raises:
            Exception: WatsonX client errors
        """
        # Use provided model_name or fall back to default
        effective_model = model_name or self.model_name
        if effective_model:
            self.client.model_name = effective_model

        return self.client.generate_embeddings_batch(texts=texts)

    def get_embedding_dimension(self, *, model_name: str | None = None) -> int:
        """Get embedding dimension for WatsonX model.

        Detects dimension by generating a sample embedding if not cached.

        Args:
            model_name: Embedding model identifier (uses default if not provided)

        Returns:
            Dimension of embedding vectors

        Raises:
            Exception: WatsonX client errors
        """
        if self._dimension is None:
            # Detect dimension by generating sample embedding
            sample = self.generate_embeddings(model_name=model_name, text="test")
            self._dimension = len(sample)
        return self._dimension

    # ==================== Text Detection Methods ====================

    def detect(
        self,
        *,
        text: str,
        detection_types: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Perform text detection using WatsonX specialized API.

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
        model_name: str | None = None,
    ) -> dict[str, Any]:
        """Detect entities (PII/HAP) in text using a detection prompt.

        Args:
            text: Input text to analyze for entities
            prompt: Detection prompt that instructs the model what to detect
            model_name: Model identifier (uses default if not provided)

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

            # Use provided model_name or fall back to default
            effective_model = model_name or self.model_name
            if effective_model:
                self.client.model_name = effective_model

            # Call WatsonX for detection
            response = self.client.generate(
                prompt=full_prompt,
                max_tokens=2000,
                temperature=0.0,
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
        model_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Detect entities in multiple texts using batch processing.

        Args:
            texts: List of input texts to analyze
            prompt: Detection prompt that instructs the model what to detect
            model_name: Model identifier (uses default if not provided)

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
                result = self.detect_entities(text=text, prompt=prompt, model_name=model_name)
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
