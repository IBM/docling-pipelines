"""API logging middleware for HTTP requests and responses."""

import logging
import time
from typing import ClassVar

from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class ApiLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests and responses with transaction ID and timing."""

    # Health check endpoints to filter out from logging
    HEALTH_CHECK_PATHS: ClassVar[set[str]] = {"/health", "/"}

    async def dispatch(self, request, call_next):
        """Log request and response with timing information."""
        # Skip logging for health check endpoints
        if request.url.path in self.HEALTH_CHECK_PATHS:
            return await call_next(request)

        # Log incoming request
        start_time = time.time()
        logger.info(f"Request: {request.method} {request.url.path}")

        # Process request
        response = await call_next(request)

        # Calculate request duration
        duration_ms = (time.time() - start_time) * 1000

        # Log response
        logger.info(
            f"Response: {response.status_code} {request.method} {request.url.path} [Duration: {duration_ms:.2f}ms]"
        )

        return response
