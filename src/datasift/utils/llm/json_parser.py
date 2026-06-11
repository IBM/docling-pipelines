# Copyright IBM Corp. 2026
# SPDX-License-Identifier: Apache-2.0

"""Reusable JSON parsing utilities for LLM responses.

This module provides utilities for parsing JSON from LLM responses,
handling common issues like markdown formatting, mixed content, and
malformed JSON.
"""

import json
import re
from typing import Any

from datasift.exceptions.datasift_exceptions import DatasiftException
from datasift.exceptions.error_codes import ErrorCode
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


def _try_parse_json(text: str) -> tuple[dict[str, Any] | None, json.JSONDecodeError | None]:
    """Try to parse text as JSON, return (result, error)."""
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, e


def _try_extract_from_markdown(raw_response: str) -> tuple[dict[str, Any] | None, json.JSONDecodeError | None]:
    """Try to extract JSON from markdown code blocks."""
    markdown_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
    markdown_match = re.search(markdown_pattern, raw_response, re.DOTALL)
    if markdown_match:
        return _try_parse_json(markdown_match.group(1))
    return None, None


def _try_extract_from_braces(raw_response: str) -> tuple[dict[str, Any] | None, json.JSONDecodeError | None]:
    """Try to extract JSON between first { and last }."""
    if "{" in raw_response and "}" in raw_response:
        start_idx = raw_response.find("{")
        end_idx = raw_response.rfind("}") + 1
        extracted = raw_response[start_idx:end_idx]
        return _try_parse_json(extracted)
    return None, None


def parse_llm_json_response(
    raw_response: str,
    *,
    log_on_error: bool = True,
    log_level: str = "debug",
) -> dict[str, Any]:
    """Parse JSON from LLM response with fallback strategies.

    This function attempts multiple strategies to extract valid JSON from
    LLM responses:
    1. Direct JSON parsing
    2. Extract JSON from markdown code blocks
    3. Extract JSON between first { and last }

    Args:
        raw_response: Raw response string from LLM
        log_on_error: Whether to log the full response on parsing failure
        log_level: Log level to use for error logging ('debug', 'info', 'warning', 'error')

    Returns:
        Parsed JSON dictionary

    Raises:
        DatasiftException: If JSON cannot be parsed after all strategies

    Example:
        >>> response = '```json\\n{"key": "value"}\\n```'
        >>> result = parse_llm_json_response(response)
        >>> result
        {'key': 'value'}
    """
    if not raw_response:
        raise DatasiftException(
            message="LLM inference failed: Model returned empty response",
            status_code=500,
            error_code=ErrorCode.INVALID_RESPONSE,
        )

    # Try parsing strategies in order
    last_json_error = None
    strategies = [
        lambda: _try_parse_json(raw_response),
        lambda: _try_extract_from_markdown(raw_response),
        lambda: _try_extract_from_braces(raw_response),
    ]

    for strategy in strategies:
        result, error = strategy()
        if result is not None:
            return result
        if error is not None:
            last_json_error = error

    # All strategies failed - log and raise error with original exception details
    if log_on_error:
        log_func = getattr(logger, log_level, logger.debug)
        log_func(f"Failed to parse JSON from LLM response. Full response: {raw_response}")

    # Include original error details in exception message
    error_detail = f": {last_json_error!s}" if last_json_error else ""
    raise DatasiftException(
        message=f"Failed to parse JSON from model{error_detail}",
        status_code=500,
        error_code=ErrorCode.INVALID_RESPONSE,
    ) from last_json_error
