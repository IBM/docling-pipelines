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

# Ollama model token limits (approximate)
OLLAMA_MODEL_TOKEN_LIMITS: dict[str, int] = {
    "llama2": 4096,
    "llama3": 8192,
    "llama3.1": 128000,
    "llama3.2": 128000,
    "mistral": 8192,
    "mixtral": 32768,
    "codellama": 16384,
    "phi": 2048,
    "gemma": 8192,
    "qwen": 32768,
    "deepseek-coder": 16384,
    "neural-chat": 4096,
    "starling-lm": 8192,
    "vicuna": 4096,
    "orca-mini": 4096,
    "wizard-vicuna": 4096,
    "nous-hermes": 4096,
    "openhermes": 8192,
    "granite3.2:2b": 128000,
    "granite3.2:8b": 128000,
    "granite4": 131072,
}

# Default token limit for unknown models
DEFAULT_TOKEN_LIMIT = 4096


class InteractionMode(Enum):
    """
    Defines the interaction modes supported by the wrapper.

    Supported modes:
    - GENERATE: Single-turn text generation
    - CHAT: Multi-turn conversational interactions
    - EMBEDDINGS: Generate vector embeddings for text
    """

    GENERATE = "generate"
    CHAT = "chat"
    EMBEDDINGS = "embeddings"


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
            mode: Interaction mode (GENERATE, CHAT, or EMBEDDINGS)
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
                # When stream=False, response is a dict with the message content
                # Returns empty string if response format is unexpected (e.g., streaming mode not fully handled)
                # Handle both dict and ChatResponse object
                if isinstance(response, dict):
                    return response.get("message", {}).get("content", "")
                elif hasattr(response, "message"):
                    # ChatResponse object
                    message = response.message
                    if isinstance(message, dict):
                        return message.get("content", "")
                    elif hasattr(message, "content"):
                        return message.content or ""
                return ""  # Fallback for unexpected response format
            else:
                response = ollama.generate(model=self.model, prompt=prompt, stream=stream)
                # When stream=False, response is a dict with the generated text
                # Returns empty string if response format is unexpected (e.g., streaming mode not fully handled)
                if isinstance(response, dict):
                    return response.get("response", "")
                return ""  # Fallback for unexpected response format
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

    def generate_embeddings(self, prompt: str) -> list[float]:
        """
        Generate embeddings for the given text using Ollama.

        Args:
            prompt: Text to generate embeddings for

        Returns:
            List of floats representing the embedding vector

        Raises:
            ImportError: If ollama package is not installed
            Exception: For other errors during embedding generation
        """
        try:
            import ollama
        except ImportError as exc:
            raise ImportError(f"ollama package not installed: {exc}") from exc

        try:
            embedding_response = ollama.embeddings(model=self.model, prompt=prompt)

            # Handle both dict and EmbeddingsResponse object types
            if isinstance(embedding_response, dict):
                embedding = embedding_response.get("embedding")
            elif hasattr(embedding_response, "embedding"):
                # Handle EmbeddingsResponse object from newer ollama versions
                embedding = embedding_response.embedding
            else:
                raise TypeError(
                    f"Unexpected response type from model '{self.model}': {type(embedding_response).__name__}"
                )

            if not isinstance(embedding, list) or not embedding:
                raise ValueError(f"Empty or missing embedding in response from model '{self.model}'.")

            return embedding

        except (ConnectionError, TimeoutError) as exc:
            logger.error("Connection failed during embedding generation: %s", exc)
            raise

        except (ValueError, TypeError) as exc:
            logger.error("Invalid response structure from Ollama API: %s", exc)
            raise

        except Exception:
            logger.exception("Unexpected error during embedding generation")
            raise

    @staticmethod
    def is_installed() -> bool:
        """
        Check if Ollama CLI is installed on the system.

        Returns:
            bool: True if Ollama is installed, False otherwise
        """
        import subprocess

        try:
            result = subprocess.run(["ollama", "--version"], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return False

    @staticmethod
    def is_server_running() -> bool:
        """
        Check if Ollama server is running and accessible.

        Returns:
            bool: True if Ollama server is accessible, False otherwise
        """
        try:
            import ollama

            # Try to list models - this will fail if server is not running
            ollama.list()
            return True
        except Exception:
            return False

    @staticmethod
    def start_server(wait_timeout: int = 10) -> bool:
        """
        Start Ollama server in background.

        Args:
            wait_timeout: Maximum seconds to wait for server to start (default: 10)

        Returns:
            bool: True if server started successfully, False otherwise
        """
        import platform
        import subprocess
        import time

        try:
            system = platform.system()

            if system == "Windows":
                # Windows: Start in background using START command
                subprocess.Popen(
                    ["cmd", "/c", "start", "/B", "ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
            else:
                # macOS/Linux: Start in background using nohup
                subprocess.Popen(
                    ["nohup", "ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=lambda: None,
                )

            # Wait for server to start
            logger.info("Starting Ollama server...")
            for i in range(wait_timeout):
                time.sleep(1)
                if OllamaClient.is_server_running():
                    logger.info("Ollama server started successfully")
                    return True
                logger.debug(f"Waiting for server... ({i + 1}/{wait_timeout})")

            logger.warning("Ollama server may not have started properly")
            return False

        except Exception as e:
            logger.error(f"Failed to start Ollama server: {e}")
            return False

    @staticmethod
    def is_model_available(model_name: str) -> bool:
        """
        Check if a model is already pulled in Ollama.

        Args:
            model_name: Name of the model to check

        Returns:
            bool: True if model is available, False otherwise
        """
        try:
            import ollama

            models = ollama.list()

            # Check if model exists in the list
            if hasattr(models, "models"):
                model_list = models.models
            elif isinstance(models, dict) and "models" in models:
                model_list = models["models"]
            else:
                model_list = models

            for model in model_list:
                # Handle both dict and object formats
                if isinstance(model, dict):
                    name = model.get("name", "")
                else:
                    name = getattr(model, "model", "")

                # Check if model name matches (handle version tags)
                if name.startswith(model_name) or name.split(":")[0] == model_name:
                    return True

            return False

        except Exception as e:
            logger.error(f"Failed to check model availability: {e}")
            return False

    @staticmethod
    def pull_model(model_name: str, show_progress: bool = True) -> bool:
        """
        Pull an Ollama model.

        Args:
            model_name: Name of the model to pull
            show_progress: Whether to display progress output (default: True)

        Returns:
            bool: True if model pulled successfully, False otherwise
        """
        import subprocess

        try:
            if show_progress:
                logger.info(f"Pulling model '{model_name}'... (this may take several minutes)")

            # Use subprocess to show real-time progress
            process = subprocess.Popen(
                ["ollama", "pull", model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Stream output if progress is enabled
            if show_progress and process.stdout:
                for line in process.stdout:
                    line = line.strip()
                    if line:
                        logger.debug(f"Pull progress: {line}")

            process.wait()

            if process.returncode == 0:
                logger.info(f"Model '{model_name}' pulled successfully")
                return True
            else:
                logger.error(f"Failed to pull model '{model_name}'")
                return False

        except Exception as e:
            logger.error(f"Failed to pull model: {e}")
            return False

    @classmethod
    def _ensure_server_running(cls, auto_start: bool) -> tuple[bool, str]:
        """
        Ensure Ollama server is running, optionally starting it.

        Args:
            auto_start: Whether to automatically start the server if not running

        Returns:
            tuple: (success: bool, error_message: str or empty)
        """
        if cls.is_server_running():
            return True, ""

        if not auto_start:
            return False, "Ollama server is not running. Start with: ollama serve"

        logger.info("Ollama server not running, attempting to start...")
        if cls.start_server():
            return True, ""

        return False, ("Failed to start Ollama server automatically. Please start it manually with: ollama serve")

    @classmethod
    def _ensure_model_available(cls, model_name: str, auto_pull: bool) -> tuple[bool, str]:
        """
        Ensure model is available, optionally pulling it.

        Args:
            model_name: Name of the model to check/pull
            auto_pull: Whether to automatically pull the model if not available

        Returns:
            tuple: (success: bool, error_message: str or empty)
        """
        if cls.is_model_available(model_name):
            return True, ""

        if not auto_pull:
            return (
                False,
                f"Model '{model_name}' not available. Pull with: ollama pull {model_name}",
            )

        logger.info(f"Model '{model_name}' not found, attempting to pull...")
        if cls.pull_model(model_name, show_progress=False):
            return True, ""

        return False, (f"Failed to pull model '{model_name}'. Please pull it manually with: ollama pull {model_name}")

    @classmethod
    def ensure_ready(cls, model_name: str, auto_start: bool = True, auto_pull: bool = True) -> tuple[bool, str]:
        """
        Comprehensive readiness check with auto-remediation.

        This method checks if Ollama is installed, the server is running,
        and the specified model is available. It can automatically start
        the server and pull the model if requested.

        Args:
            model_name: Model to check/pull
            auto_start: Automatically start server if not running (default: True)
            auto_pull: Automatically pull model if not available (default: True)

        Returns:
            tuple: (success: bool, message: str) - Status and user-friendly message

        Example:
            >>> success, message = OllamaClient.ensure_ready("llama2")
            >>> if not success:
            ...     print(f"Error: {message}")
            >>> else:
            ...     client = OllamaClient(model="llama2")
        """
        # Guard clause: Check installation
        if not cls.is_installed():
            return (
                False,
                "Ollama is not installed. Install from: https://ollama.ai/download",
            )

        # Ensure server is running
        server_ok, server_msg = cls._ensure_server_running(auto_start)
        if not server_ok:
            return False, server_msg

        # Ensure model is available
        model_ok, model_msg = cls._ensure_model_available(model_name, auto_pull)
        if not model_ok:
            return False, model_msg

        return True, f"Ollama ready with model '{model_name}'"
