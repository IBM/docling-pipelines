"""Transaction ID middleware for request tracking and distributed tracing.

This middleware extracts or generates a unique transaction ID for each request
and manages it through multiple mechanisms:
- Stores in request.state.transaction_id for handler access
- Sets in async context variable for logging access
- Populates session_info for ConditionalFormatter access
- Adds to response headers for client tracking

Header pattern for distributed tracing:
- Request: Reads transaction ID from X-Global-Transaction-Id header
- Response: Returns transaction ID in X-Transaction-ID header
- This enables transaction tracking across services

The async context variable approach allows ConditionalFormatter and other
logging components to access the transaction ID without explicit parameter passing.
"""

import uuid
from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from docpipe.core.models.session_info import create_session_info

# Context variable to store transaction ID for async context propagation
# This allows logging components to access the transaction ID without explicit passing
transaction_id_var: ContextVar[str] = ContextVar("transaction_id", default="unknown")


def set_transaction_id(transaction_id: str) -> None:
    """Set the transaction ID in the current async context.

    This function stores the transaction ID in a context variable that automatically
    propagates through async call chains, making it accessible to logging formatters
    and other components without explicit parameter passing.

    Args:
        transaction_id: The transaction ID to set (typically a UUID string)
    """
    transaction_id_var.set(transaction_id)


def get_transaction_id() -> str:
    """Get the transaction ID from the current async context.

    Retrieves the transaction ID that was set by TransactionMiddleware for the
    current request. Used by logging components to include transaction IDs in logs.

    Returns:
        The transaction ID string, or "unknown" if not set in the current context
    """
    return transaction_id_var.get()


class TransactionMiddleware(BaseHTTPMiddleware):
    """Middleware to handle transaction ID for request tracking and distributed tracing.

    Header pattern:
    - Incoming: Reads transaction ID from X-Global-Transaction-Id header
    - Outgoing: Returns transaction ID in X-Transaction-ID header
    - Generates new UUID if X-Global-Transaction-Id is not provided

    This pattern enables distributed tracing across services while maintaining
    a consistent header naming convention for request/response flow.

    Stores the ID in request.state.transaction_id, sets it in the async context,
    populates session_info, and adds it to response headers.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and add transaction ID.

        Header handling:
        1. Reads transaction ID from X-Global-Transaction-Id header (incoming)
        2. Generates new UUID if header not present
        3. Returns transaction ID in X-Transaction-ID header (outgoing)

        Args:
            request: FastAPI request object
            call_next: Next middleware or route handler

        Returns:
            Response: Response with X-Transaction-ID header
        """
        # Get transaction ID from X-Global-Transaction-Id header
        transaction_id = request.headers.get("X-Global-Transaction-Id")

        # If not provided, generate a new one
        if not transaction_id:
            transaction_id = str(uuid.uuid4())

        # Store in request state for access by handlers
        request.state.transaction_id = transaction_id

        # Set in async context for logging
        set_transaction_id(transaction_id)

        # Populate session_info for ConditionalFormatter access
        create_session_info(transaction_id=transaction_id)

        # Process request
        response = await call_next(request)

        # Add transaction ID to response headers
        response.headers["X-Transaction-ID"] = transaction_id

        return response
