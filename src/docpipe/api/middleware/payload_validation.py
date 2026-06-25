"""Payload validation middleware for FastAPI application.

This module provides middleware for validating request payload sizes
to prevent excessive memory usage and potential DoS attacks.
"""

from fastapi import Request
from fastapi.responses import JSONResponse

# Maximum payload size for requests (5MB)
MAX_PAYLOAD_SIZE = 5 * 1024 * 1024  # 5MB in bytes


async def validate_payload_size(request: Request, call_next):
    """Validate request payload size.

    Checks if the Content-Length header exceeds the maximum allowed payload size
    for POST, PUT, and PATCH requests. Returns a 413 error if the payload is too large.

    Args:
        request: The incoming FastAPI request object
        call_next: The next middleware or route handler in the chain

    Returns:
        JSONResponse with 413 status if payload is too large, otherwise
        the response from the next handler in the chain
    """
    if request.method in ["POST", "PUT", "PATCH"]:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_PAYLOAD_SIZE:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Payload too large. Maximum size is {MAX_PAYLOAD_SIZE / (1024 * 1024)}MB"},
            )
    return await call_next(request)
