"""
REST client for making HTTP requests with retry logic and error handling.

This module provides a flexible REST client that supports:
- Multiple HTTP methods (GET, POST, PUT, PATCH, DELETE)
- Automatic retry with exponential backoff
- Bearer token authentication
- Request/response logging with sensitive data sanitization
- Configurable timeouts and SSL verification
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypedDict

import requests
from requests import Response
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from docpipe.exceptions.docpipe_exceptions import ExternalServiceError
from docpipe.exceptions.error_codes import ErrorCode

logger = logging.getLogger(__name__)


class RestMethod(Enum):
    """HTTP methods supported by the REST client."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class MethodConfig(TypedDict):
    expected_status_codes: list[int]
    supports_body: bool


# Configuration for each HTTP method
METHOD_CONFIG: dict[RestMethod, MethodConfig] = {
    RestMethod.GET: {
        "expected_status_codes": [200],
        "supports_body": False,
    },
    RestMethod.POST: {
        "expected_status_codes": [200, 201],
        "supports_body": True,
    },
    RestMethod.PUT: {
        "expected_status_codes": [200, 204],
        "supports_body": True,
    },
    RestMethod.PATCH: {
        "expected_status_codes": [200, 204],
        "supports_body": True,
    },
    RestMethod.DELETE: {
        "expected_status_codes": [200, 204],
        "supports_body": False,
    },
}


def sanitize_sensitive_data(data: dict[str, Any] | str) -> dict[str, Any] | str:
    """
    Redact sensitive information from data for logging purposes.

    Args:
        data: Dictionary or string containing potentially sensitive data

    Returns:
        Sanitized copy of the data with sensitive values redacted
    """
    redacted = "[REDACTED]"

    # Patterns to match sensitive data
    sensitive_patterns = [
        (r'(token|password|api[_-]?key|secret|authorization)[\s:=]+["\']?([^"\'\s,}]+)', r"\1: " + redacted),
        (r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer " + redacted),
        (r"Basic\s+[A-Za-z0-9+/]+=*", "Basic " + redacted),
    ]

    if isinstance(data, dict):
        sanitized: dict[str, Any] = {}
        for key, value in data.items():
            # Check if key contains sensitive keywords
            if any(keyword in key.lower() for keyword in ["token", "password", "key", "secret", "auth"]):
                sanitized[key] = redacted
            elif isinstance(value, dict):
                sanitized[key] = sanitize_sensitive_data(value)
            elif isinstance(value, str):
                sanitized[key] = sanitize_sensitive_data(value)
            else:
                sanitized[key] = value
        return sanitized

    elif isinstance(data, str):
        sanitized_str = data
        for pattern, replacement in sensitive_patterns:
            sanitized_str = re.sub(pattern, replacement, sanitized_str, flags=re.IGNORECASE)
        return sanitized_str

    return data


@dataclass
class RestClientConfig:
    """Configuration for REST client behavior."""

    timeout: int = 30
    max_retries: int = 3
    retry_backoff_factor: float = 2.0
    verify_ssl: bool | str = True  # True, False, or path to cert file
    retry_max_attempts: int = 3
    retry_multiplier: float = 2.0
    retry_min_wait: float = 1.0
    retry_max_wait: float = 10.0


class RestClient:
    """
    REST client with retry logic and error handling.

    Supports bearer token authentication, automatic retries with exponential backoff,
    and comprehensive logging with sensitive data sanitization.
    """

    def __init__(
        self,
        config: RestClientConfig,
        base_url: str | None = None,
        auth_token: str | None = None,
    ):
        """
        Initialize the REST client.

        Args:
            config: Configuration for client behavior
            base_url: Optional base URL to prepend to all requests
            auth_token: Optional bearer token for authentication
        """
        self.config = config
        self.base_url = base_url.rstrip("/") if base_url else None
        self.auth_token = auth_token
        self.session = requests.Session()

        # Apply retry decorator dynamically with config values
        self._call_rest_method = retry(
            retry=retry_if_exception_type(
                (
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    requests.exceptions.HTTPError,
                )
            ),
            stop=stop_after_attempt(self.config.retry_max_attempts),
            wait=wait_exponential(
                multiplier=self.config.retry_multiplier, min=self.config.retry_min_wait, max=self.config.retry_max_wait
            ),
            reraise=True,
        )(self._call_rest_method_impl)

    def _build_url(self, endpoint: str) -> str:
        """
        Build full URL from base URL and endpoint.

        Args:
            endpoint: API endpoint path

        Returns:
            Complete URL
        """
        if self.base_url:
            return f"{self.base_url}/{endpoint.lstrip('/')}"
        return endpoint

    def _build_headers(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        """
        Build request headers including authentication.

        Args:
            headers: Optional additional headers

        Returns:
            Complete headers dictionary
        """
        request_headers = headers.copy() if headers else {}

        if self.auth_token and "Authorization" not in request_headers:
            request_headers["Authorization"] = f"Bearer {self.auth_token}"

        return request_headers

    def call_rest_json(
        self,
        method: RestMethod,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        form_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        expected_status_codes: list[int] | None = None,
    ) -> dict[str, Any]:
        """
        Make a REST call expecting JSON response.

        Args:
            method: HTTP method to use
            endpoint: API endpoint
            json_data: Optional JSON body data
            form_data: Optional form-encoded body data (mutually exclusive with json_data)
            params: Optional query parameters
            headers: Optional request headers
            expected_status_codes: Optional list of expected status codes

        Returns:
            Parsed JSON response as dictionary

        Raises:
            DocpipeException: If request fails or response is not valid JSON
        """
        response = self.call_rest(
            method=method,
            endpoint=endpoint,
            json_data=json_data,
            form_data=form_data,
            params=params,
            headers=headers,
            expected_status_codes=expected_status_codes,
        )

        try:
            return response.json()
        except ValueError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise ExternalServiceError(
                message=f"Response is not valid JSON: {e!s}",
                error_code=ErrorCode.INVALID_RESPONSE,
            ) from e

    def call_rest_multipart(
        self,
        method: RestMethod,
        endpoint: str,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        expected_status_codes: list[int] | None = None,
    ) -> dict[str, Any]:
        """
        Make a REST call with multipart/form-data encoding expecting JSON response.

        Args:
            method: HTTP method to use
            endpoint: API endpoint
            files: Dictionary of files to upload {field_name: (filename, content, mime_type)}
            data: Optional form data fields
            params: Optional query parameters
            headers: Optional request headers
            expected_status_codes: Optional list of expected status codes

        Returns:
            Parsed JSON response as dictionary

        Raises:
            DocpipeException: If request fails or response is not valid JSON
        """
        url = self._build_url(endpoint)
        request_headers = self._build_headers(headers)

        if expected_status_codes is None:
            expected_status_codes = METHOD_CONFIG[method]["expected_status_codes"]

        # Log request details (don't log file content)
        log_msg = f"Making {method.value} multipart request to {url}"
        if params:
            log_msg += f" with params: {sanitize_sensitive_data(params)}"
        logger.info(log_msg)
        logger.debug(f"Headers: {sanitize_sensitive_data(request_headers)}")
        if data:
            logger.debug(f"Form data: {sanitize_sensitive_data(data)}")
        if files:
            logger.debug(f"Files: {list(files.keys())}")

        try:
            response = self.session.request(
                method=method.value,
                url=url,
                files=files,
                data=data,
                params=params,
                headers=request_headers,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
            )

            # Log response
            logger.info(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")

            # Check status code
            if expected_status_codes and response.status_code not in expected_status_codes:
                error_msg = f"Unexpected status code {response.status_code}. Expected one of {expected_status_codes}. Response: {response.text[:500]}"
                logger.error(error_msg)
                raise ExternalServiceError(
                    message=error_msg,
                    error_code=ErrorCode.HTTP_ERROR,
                    status_code=response.status_code,
                )

            # Parse JSON response
            try:
                return response.json()
            except ValueError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                raise ExternalServiceError(
                    message=f"Response is not valid JSON: {e!s}",
                    error_code=ErrorCode.INVALID_RESPONSE,
                ) from e

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e!s}")
            raise ExternalServiceError(
                message=f"REST request failed: {e!s}",
                error_code=ErrorCode.CONNECTION_ERROR,
            ) from e

    def call_rest(
        self,
        method: RestMethod,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        form_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        expected_status_codes: list[Any] | None = None,
    ) -> Response:
        """
        Make a generic REST call.

        Args:
            method: HTTP method to use
            endpoint: API endpoint
            json_data: Optional JSON body data
            form_data: Optional form-encoded body data (mutually exclusive with json_data)
            params: Optional query parameters
            headers: Optional request headers
            expected_status_codes: Optional list of expected status codes

        Returns:
            Response object

        Raises:
            DocpipeException: If request fails
        """
        url = self._build_url(endpoint)
        request_headers = self._build_headers(headers)

        if expected_status_codes is None:
            expected_status_codes = METHOD_CONFIG[method]["expected_status_codes"]

        # Log request details with sanitized data
        log_msg = f"Making {method.value} request to {url}"
        if params:
            log_msg += f" with params: {sanitize_sensitive_data(params)}"
        logger.info(log_msg)
        logger.debug(f"Headers: {sanitize_sensitive_data(request_headers)}")
        if json_data:
            logger.debug(f"Body: {sanitize_sensitive_data(json_data)}")
        if form_data:
            logger.debug(f"Form data: {sanitize_sensitive_data(form_data)}")

        try:
            response = self._call_rest_method(
                method=method,
                url=url,
                json_data=json_data,
                form_data=form_data,
                params=params,
                headers=request_headers,
            )

            # Log response
            logger.info(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")

            # Check status code
            if expected_status_codes and response.status_code not in expected_status_codes:
                error_msg = f"Unexpected status code {response.status_code}. Expected one of {expected_status_codes}. Response: {response.text[:500]}"
                logger.error(error_msg)
                raise ExternalServiceError(
                    message=error_msg,
                    error_code=ErrorCode.HTTP_ERROR,
                    status_code=response.status_code,
                )

            return response

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e!s}")
            raise ExternalServiceError(
                message=f"REST request failed: {e!s}",
                error_code=ErrorCode.CONNECTION_ERROR,
            ) from e

    def _call_rest_method_impl(
        self,
        method: RestMethod,
        url: str,
        json_data: dict[str, Any] | None = None,
        form_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Response:
        """
        Internal method to make REST call with retry logic.

        Args:
            method: HTTP method to use
            url: Complete URL
            json_data: Optional JSON body data
            form_data: Optional form-encoded body data (mutually exclusive with json_data)
            params: Optional query parameters
            headers: Optional request headers

        Returns:
            Response object

        Raises:
            requests.exceptions.RequestException: If request fails after retries
        """
        # Validate that json_data and form_data are mutually exclusive
        if json_data is not None and form_data is not None:
            raise ValueError("json_data and form_data are mutually exclusive")

        response = self.session.request(
            method=method.value,
            url=url,
            json=json_data,
            data=form_data,
            params=params,
            headers=headers,
            timeout=self.config.timeout,
            verify=self.config.verify_ssl,
        )

        # Raise HTTPError for 5xx status codes to trigger retry logic.
        # Note: Retry only occurs if tenacity conditions are met (ConnectionError, Timeout, HTTPError)
        # and within the configured max_attempts. 4xx errors are NOT retried.
        if 500 <= response.status_code < 600:
            response.raise_for_status()

        return response
