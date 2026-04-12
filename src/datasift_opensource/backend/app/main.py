"""FastAPI application main entry point.

This module configures the FastAPI application with:
- ConditionalFormatter for structured JSON logging with transaction ID tracking
- Transaction middleware for request tracking across the application
- Security headers middleware for enhanced security
- CORS middleware for cross-origin resource sharing
- Standardized error handlers following IBM Cloud standards
"""

import logging
import os
import sys
from typing import Any, cast

import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.api_router import api_router
from app.middleware import validate_payload_size
from app.middleware.api_logging_middleware import ApiLoggingMiddleware
from app.middleware.error_handler import (
    datasift_exception_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.middleware.transaction_middleware import TransactionMiddleware
from common.exceptions.datasift_exceptions import DatasiftException
from common.util.infrastructure.logging import ConditionalFormatter


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    async def dispatch(self, request, call_next):
        # Process request
        response = await call_next(request)

        # Add security headers to all responses
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )

        return response


# Configure logging with ConditionalFormatter for structured JSON logging
# ConditionalFormatter retrieves transaction IDs from session_info context
# and includes them in all log entries for request tracing
formatter = ConditionalFormatter(datefmt="%H:%M:%S")

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)

# Configure root logger
logging.basicConfig(level=logging.INFO, handlers=[handler])

# Ensure all loggers use the formatter
root_logger = logging.getLogger()
root_logger.handlers = [handler]

# Configure uvicorn.access logger to use ConditionalFormatter
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.handlers = []  # Clear existing handlers
uvicorn_access_logger.addHandler(handler)
uvicorn_access_logger.propagate = False  # Prevent duplicate logs

app = FastAPI(
    title="DataSift Opensource API",
    description="API for DataSift opensource",
    version="0.1.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
    servers=[
        {"url": "http://localhost:8080", "description": "Local development server"},
        {"url": "https://api.datasift.example.com", "description": "Production server"},
    ],
    openapi_tags=[
        {
            "name": "flows",
            "description": "Flow management operations for creating, reading, updating, and deleting data processing flows",
        },
        {
            "name": "system",
            "description": "System health and status endpoints",
        },
    ],
)


def custom_openapi():
    """Customize OpenAPI schema for IBM validator compatibility by removing nullable keywords.

    Returns:
        dict: OpenAPI schema with nullable keywords removed
    """
    # Return cached schema if already generated
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    # Generate base OpenAPI schema using FastAPI's standard generator
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
        servers=app.servers,
    )

    def remove_nullable_keywords(schema: dict) -> dict:
        """Recursively remove all nullable keywords from the schema.

        IBM validator rejects the `nullable` keyword entirely. Since nullable fields
        are optional in our API (they have defaults or are not required), we simply
        remove the nullable keyword without replacement.

        The semantic meaning is preserved because:
        - Optional fields are already marked as not required in the schema
        - Fields with defaults will use those defaults when null is provided
        - The API handles null values appropriately in validation

        Args:
            schema: OpenAPI schema object (dict) to process

        Returns:
            dict: Processed schema with all nullable keywords removed
        """
        if not isinstance(schema, dict):
            return schema

        # Simply remove nullable keyword if present
        if "nullable" in schema:
            schema.pop("nullable")

        # Recursively process nested schemas
        for key, value in list(schema.items()):
            if isinstance(value, dict):
                schema[key] = remove_nullable_keywords(value)
            elif isinstance(value, list):
                schema[key] = [remove_nullable_keywords(item) if isinstance(item, dict) else item for item in value]

        return schema

    # Process component schemas
    if "components" in openapi_schema and "schemas" in openapi_schema["components"]:
        for schema_name, schema_def in openapi_schema["components"]["schemas"].items():
            openapi_schema["components"]["schemas"][schema_name] = remove_nullable_keywords(schema_def)

            # Add description to HTTPValidationError schema if missing
            if schema_name == "HTTPValidationError" and "description" not in schema_def:
                schema_def["description"] = "HTTP 422 validation error response with detailed error information"

    # Process path operation schemas
    if "paths" in openapi_schema:
        for path_item in openapi_schema["paths"].values():
            for operation in path_item.values():
                if not isinstance(operation, dict):
                    continue

                # Process parameters
                if "parameters" in operation:
                    for param in operation["parameters"]:
                        if "schema" in param:
                            param["schema"] = remove_nullable_keywords(param["schema"])

                # Process request body
                if "requestBody" in operation and "content" in operation["requestBody"]:
                    for content in operation["requestBody"]["content"].values():
                        if "schema" in content:
                            content["schema"] = remove_nullable_keywords(content["schema"])

                # Process responses
                if "responses" in operation:
                    for response in operation["responses"].values():
                        if isinstance(response, dict) and "content" in response:
                            for content in response["content"].values():
                                if "schema" in content:
                                    content["schema"] = remove_nullable_keywords(content["schema"])

    # Cache and return processed schema
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Override the default OpenAPI schema generator
cast(Any, app).openapi = custom_openapi


# Middleware execution order (reverse of registration):
# 1. TransactionMiddleware - generates/extracts transaction ID, stores in request.state and async context
# 2. ApiLoggingMiddleware - logs requests/responses with transaction ID from request.state
# 3. SecurityHeadersMiddleware - adds security headers to responses
# 4. CORSMiddleware - handles CORS preflight and headers

# Register in reverse order (last registered = first executed)
app.add_middleware(SecurityHeadersMiddleware)  # Executes third
app.add_middleware(ApiLoggingMiddleware)  # Executes second - accesses transaction_id from request.state
app.add_middleware(TransactionMiddleware)  # Executes first - sets transaction_id in context

# Configure CORS
# Get allowed origins from environment variable, default to localhost for development
cors_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:3000")
allowed_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register IBM Cloud standard error handlers
# Order matters: more specific handlers first, then generic
app.add_exception_handler(DatasiftException, cast(Any, datasift_exception_handler))
app.add_exception_handler(StarletteHTTPException, cast(Any, http_exception_handler))
app.add_exception_handler(RequestValidationError, cast(Any, validation_exception_handler))
app.add_exception_handler(Exception, generic_exception_handler)


@app.get(
    "/",
    tags=["system"],
    operation_id="read_root",
    summary="API root endpoint",
)
async def root():
    """Root endpoint returning welcome message."""
    from app.dto.flow_dto import RootResponse

    return RootResponse(message="Welcome to DataSift Opensource API")


@app.get(
    "/health",
    tags=["system"],
    operation_id="health_check",
    summary="Health check endpoint",
)
async def health_check():
    """Health check endpoint returning service status."""
    from app.dto.flow_dto import HealthCheckResponse

    return HealthCheckResponse(status="healthy")


# Register middleware
app.middleware("http")(validate_payload_size)

# Include routers
app.include_router(api_router)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8080,
        reload=True,
    )
