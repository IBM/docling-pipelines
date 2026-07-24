"""
Local PII and HAP Detection using Ollama.

This module provides PII and HAP detection functionality using local
Ollama models, following the enterprise pattern but adapted for opensource.
"""

import json
import os
from typing import Any

from docpipe.core.constants import OperatorConstants
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.integrations.ollama.client import InteractionMode, OllamaClient
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)

_prompt_cache: dict[str, Any] = {"static_prompt": None}
PROMPT_EXAMPLES_PATH = os.path.join(os.path.dirname(__file__), "pii_prompt_examples.json")


def _load_static_prompt() -> str:
    """
    Load and cache the static prompt with examples from JSON file.

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


def detect_pii_hap_ollama(request_data: dict[str, Any], model_name: str = "granite4") -> dict[str, Any]:
    """
    Detect PII and HAP in text using Ollama model.

    This function follows the enterprise pattern but uses local Ollama models
    instead of external services.

    Args:
        request_data: Dictionary containing:
            - input: Text to analyze
            - detectors: Dict with 'hap' and 'pii' threshold configurations
        model_name: Name of the Ollama model to use

    Returns:
        Dictionary with 'detections' key containing list of detected items

    Raises:
        DocpipeException: If JSON parsing fails

    Example:
        >>> request_data = {
        ...     "input": "My email is john@example.com",
        ...     "detectors": {
        ...         "hap": {"threshold": 0.8},
        ...         "pii": {"threshold": 0.5}
        ...     }
        ... }
        >>> result = detect_pii_hap(request_data, "granite4")
        >>> print(result['detections'])
    """
    text = request_data.get("input", "")
    detectors = request_data.get("detectors", {})
    hap_threshold = detectors.get("hap", {}).get("threshold", 0.8)
    pii_threshold = detectors.get("pii", {}).get("threshold", 0.5)

    static_prompt = _load_static_prompt()
    dynamic_prompt = (
        f"Now analyze the following text, applying thresholds hap={hap_threshold} and pii={pii_threshold}:\n\n"
        f'"""{text}"""\n'
    )
    full_prompt = static_prompt + dynamic_prompt

    try:
        ollama_wrapper = OllamaClient(model_name=model_name, mode=InteractionMode.GENERATE)
        result = ollama_wrapper.run_json(prompt=full_prompt)
        return result
    except json.JSONDecodeError as exc:
        raise DocpipeException(message=f"Failed to parse JSON from model: {exc!s}", status_code=500) from exc


def detect_pii_hap_litellm(
    request_data: dict[str, Any],
    model_name: str,
    api_key: str | None = None,
    api_base: str | None = None,
    **litellm_config: Any,
) -> dict[str, Any]:
    """
    Detect PII and HAP using LiteLLM (supports 100+ providers).

    Args:
        request_data: Dictionary containing input text and detector thresholds
        model_name: Model identifier in LiteLLM format (e.g., "gpt-4", "claude-3-opus-20240229")
        api_key: Optional API key (falls back to provider-specific env vars)
        api_base: Optional custom API base URL
        **litellm_config: Additional LiteLLM configuration parameters

    Returns:
        Dictionary with 'detections' key containing list of detected items

    Raises:
        DocpipeException: If JSON parsing fails or API call fails
    """
    try:
        from docpipe.integrations.litellm.client import LiteLLMLLMClient
    except ImportError as exc:
        raise DocpipeException(message=f"litellm package not installed: {exc}", status_code=500) from exc

    text = request_data.get(OperatorConstants.PIIHAP.INPUT_FIELD, "")
    detectors = request_data.get("detectors", {})
    hap_threshold = detectors.get("hap", {}).get("threshold", 0.8)
    pii_threshold = detectors.get("pii", {}).get("threshold", 0.5)

    static_prompt = _load_static_prompt()
    dynamic_prompt = (
        f"Now analyze the following text, applying thresholds hap={hap_threshold} and pii={pii_threshold}:\n\n"
        f'"""{text}"""\n'
    )
    full_prompt = static_prompt + dynamic_prompt

    try:
        client = LiteLLMLLMClient(model_name=model_name, api_key=api_key, api_base=api_base, **litellm_config)

        messages = [{"role": "user", "content": full_prompt}]
        raw_content = client.chat(messages=messages, temperature=0.0)

        if not raw_content:
            raise DocpipeException(message="Model returned empty response", status_code=500)

        # Try to parse JSON from response
        try:
            return json.loads(raw_content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown or mixed content
            import re

            match = re.search(r"\{.*\}", raw_content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise

    except json.JSONDecodeError as exc:
        raise DocpipeException(message=f"Failed to parse JSON from model: {exc!s}", status_code=500) from exc
    except Exception as exc:
        raise DocpipeException(message=f"Error calling LiteLLM API: {exc!s}", status_code=500) from exc
