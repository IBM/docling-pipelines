"""Middleware package for FastAPI application.

This package contains middleware components for request/response processing,
including payload validation, authentication, rate limiting, and logging.
"""

from docpipe.api.middleware.payload_validation import validate_payload_size

__all__ = ["validate_payload_size"]
