# Copyright IBM Corp. 2025
# SPDX-License-Identifier: Apache-2.0

"""
Ollama Client Wrapper for PII and HAP Detection.

Provides a simplified interface for interacting with Ollama models,
with support for JSON output parsing and retry logic.
"""

import json
from enum import Enum
from typing import Any

from common.util.log import get_logger

logger = get_logger(__name__)


class InteractionMode(Enum):
    """Defines the interaction modes supported by the wrapper."""

    GENERATE = "generate"
    CHAT = "chat"


class OllamaClient:
    """
    Wrapper for Ollama API interactions with JSON parsing support.

    This client provides a simplified interface for calling Ollama models
    with automatic JSON parsing and retry logic for robust operation.
    """

    def __init__(
        self,
        model: str = "granite4",
        mode: InteractionMode = InteractionMode.GENERATE,
        system_prompt: str | None = None,
        validate_model: bool = True,
        timeout: float | None = None,
    ):
        """
        Initialize the Ollama client.

        Args:
            model: Name of the Ollama model to use (e.g., "granite4", "llama3")
            mode: Interaction mode (GENERATE or CHAT)
            system_prompt: Optional system-level instructions for chat mode
            validate_model: Whether to validate model availability on initialization
            timeout: Timeout in seconds for API calls (default: None, no timeout)

        Raises:
            ImportError: If ollama package is not installed
            ValueError: If model validation is enabled and model is not available
        """
        self.model = model
        self.mode = mode if isinstance(mode, InteractionMode) else InteractionMode(mode)
        self.system_prompt = system_prompt
        self.timeout = timeout

        if validate_model:
            self._validate_model()

    def _validate_model(self) -> None:
        """
        Validate that the specified model is available in Ollama.

        Raises:
            ImportError: If ollama package is not installed
            ValueError: If the model is not available
        """
        try:
            import ollama
        except ImportError as exc:
            raise ImportError(f"ollama package not installed: {exc}") from exc

        try:
            # List available models
            models_response = ollama.list()
            available_models = [m.model.split(":")[0] for m in models_response.get("models", [])]

            # Check if the requested model is available
            model_base = self.model.split(":")[0]  # Handle model:tag format
            if model_base not in available_models:
                raise ValueError(
                    f"Model '{self.model}' is not available. "
                    f"Available models: {', '.join(available_models) if available_models else 'none'}. "
                    f"Please pull the model using: ollama pull {self.model}"
                )

            logger.info(f"Model '{self.model}' validated successfully")
        except ValueError:
            raise
        except Exception as exc:
            logger.warning(f"Could not validate model availability: {exc!s}")
            # Don't fail initialization if validation check itself fails

    def run(self, prompt: str, stream: bool = False) -> str:
        """
        Execute the model with the given prompt.

        Args:
            prompt: Input text for the model
            stream: Enable streaming responses (not implemented)

        Returns:
            Generated text as string

        Raises:
            ImportError: If ollama package is not installed
            Exception: For other errors during model execution
        """
        try:
            import ollama
        except ImportError as exc:
            raise ImportError(f"ollama package not installed: {exc}") from exc

        try:
            if self.mode == InteractionMode.CHAT:
                messages = []
                if self.system_prompt:
                    messages.append({"role": "system", "content": self.system_prompt})
                messages.append({"role": "user", "content": prompt})

                response = ollama.chat(model=self.model, messages=messages, stream=stream)
                return response.get("message", {}).get("content", "")
            else:
                response = ollama.generate(model=self.model, prompt=prompt, stream=stream)
                return response.get("response", "")
        except (ConnectionError, TimeoutError) as exc:
            logger.error(f"Connection failed: {exc}")
            raise
        except ValueError as exc:
            logger.error(f"Invalid model or parameters: {exc}")
            raise
        except Exception as exc:
            logger.error(f"Unexpected error during model execution: {exc}")
            raise

    def _parse_json_response(self, raw: str) -> dict[str, Any] | None:
        """
        Attempt to parse JSON from raw model output.

        Tries direct parsing first, then extracts from markdown/mixed content
        using JSONDecoder for robust handling of nested structures.

        Args:
            raw: Raw string output from model

        Returns:
            Parsed dict if successful, None otherwise
        """
        # Try direct JSON parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown or mixed content
        # Use JSONDecoder for more robust extraction
        try:
            decoder = json.JSONDecoder()
            # Find first valid JSON object
            idx = raw.find("{")
            if idx != -1:
                obj, _end_idx = decoder.raw_decode(raw, idx)
                return obj
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    def run_json(self, prompt: str, system_prompt: str | None = None, retries: int = 3) -> dict[str, Any]:
        """
        Run the model and enforce JSON output with retries.

        Args:
            prompt: The task prompt
            system_prompt: Optional system-level override
            retries: Number of times to retry parsing JSON

        Returns:
            dict parsed from model JSON output

        Raises:
            json.JSONDecodeError: If JSON parsing fails after all retries
        """
        base_instruction = (
            "You must respond with ONLY valid JSON. "
            "Do not include natural language, markdown, or commentary. "
            'If there are no detections, return: {"detections": []}'
        )

        prompt_parts = [base_instruction, "", prompt]
        last_raw = None

        for attempt in range(retries):
            full_prompt = "\n".join(prompt_parts)
            raw = self.run(full_prompt)
            last_raw = raw

            # Try parsing JSON
            parsed = self._parse_json_response(raw)
            if parsed is not None:
                return parsed

            if attempt < retries - 1:
                logger.warning(f"Failed to parse JSON from model (attempt {attempt + 1}/{retries}). Retrying...")
                # Add emphasis only once
                if len(prompt_parts) == 3:
                    prompt_parts.append("\nIMPORTANT: Respond ONLY with JSON, nothing else.")

        # If all retries fail, raise an exception with the last response
        raise json.JSONDecodeError(
            f"Failed to parse JSON after {retries} attempts. "
            f"Model: {self.model}, Mode: {self.mode.value}. "
            f"Last response: {last_raw[:200] if last_raw else 'None'}...",
            last_raw or "",
            0,
        )
