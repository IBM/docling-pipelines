"""REST API standard error response DTOs.

These models implement an industry-standard error response format following
REST API best practices for structured error handling.

Models:
- ErrorTarget: Identifies the specific element that caused an error (field, parameter, header)
- ErrorDetail: Individual error with code, message, and optional target
- ErrorResponse: Complete error response with array of errors and trace ID

Validation errors are handled by the validation_exception_handler in error_handler.py,
which converts FastAPI RequestValidationError to ErrorResponse format.
"""

from enum import StrEnum
from typing import ClassVar, Literal

from pydantic import BaseModel, Field


class TargetType(StrEnum):
    """Error target types."""

    PARAMETER = "parameter"
    FIELD = "field"
    HEADER = "header"


# Standard error codes used across the API
ErrorCode = Literal[
    "invalid_request",
    "invalid_parameter",
    "unauthorized",
    "forbidden",
    "not_found",
    "method_not_allowed",
    "conflict",
    "validation_error",
    "too_many_requests",
    "internal_error",
    "service_unavailable",
    "unknown_error",
    # Flow CRUD operation error codes
    "flow_not_found",
    "flow_already_exists",
    "flow_invalid_data",
    "flow_storage_error",
    # Configuration error codes
    "invalid_configuration",
]


class ErrorTarget(BaseModel):
    """Target information for an error."""

    type: str = Field(
        min_length=1,
        max_length=50,
        pattern="^[a-z_]+$",
        description="Type of target (e.g., 'parameter', 'field', 'header')",
        examples=["parameter", "field", "header"],
        json_schema_extra={
            "minLength": 1,
            "maxLength": 50,
            "pattern": "^[a-z_]+$",
        },
    )
    name: str = Field(
        min_length=1,
        max_length=256,
        pattern=r"^[\s\S]{1,256}$",
        description="Name of the target element",
        examples=["flow_id", "name", "Authorization", "definition -> nodes -> 0 -> operator_type"],
        json_schema_extra={
            "minLength": 1,
            "maxLength": 256,
            "pattern": r"^[\s\S]{1,256}$",
        },
    )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra: ClassVar[dict] = {
            "examples": [
                {"type": "parameter", "name": "flow_id"},
                {"type": "field", "name": "definition"},
                {"type": "header", "name": "Authorization"},
            ]
        }


class ErrorDetail(BaseModel):
    """Individual error detail following REST API standard format."""

    code: ErrorCode = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z_]+$",
        description="Machine-readable error code (snake_case)",
        examples=["invalid_parameter", "not_found", "validation_error", "internal_error"],
        json_schema_extra={
            "minLength": 1,
            "maxLength": 100,
            "pattern": r"^[a-z_]+$",
        },
    )
    message: str = Field(
        min_length=1,
        max_length=10000,
        pattern=r"^[\x20-\x7E\r\n]{1,10000}$",
        description="Human-readable error message explaining what went wrong",
        examples=["The 'flow_id' parameter is invalid", "Flow not found", "Validation failed for field 'name'"],
        json_schema_extra={
            "minLength": 1,
            "maxLength": 10000,
            "pattern": r"^[\x20-\x7E\r\n]{1,10000}$",
        },
    )
    more_info: str | None = Field(
        default=None,
        min_length=0,
        max_length=10000,
        pattern=r"^[ -~]{0,10000}$",
        description="URL to documentation about this error",
        examples=["https://docs.example.com/errors/invalid_parameter"],
        json_schema_extra={
            "minLength": 0,
            "maxLength": 10000,
            "pattern": r"^[ -~]{0,10000}$",
        },
    )
    target: ErrorTarget | None = Field(default=None, description="Specific element that caused the error")

    class Config:
        """Pydantic model configuration."""

        json_schema_extra: ClassVar[dict] = {
            "examples": [
                {
                    "code": "invalid_parameter",
                    "message": "The 'flow_id' parameter must be a valid UUID",
                    "more_info": "https://docs.example.com/errors/invalid_parameter",
                    "target": {"type": "parameter", "name": "flow_id"},
                },
                {
                    "code": "not_found",
                    "message": "Flow with ID '550e8400-e29b-41d4-a716-446655440000' not found",
                    "more_info": "https://docs.example.com/errors/not_found",
                },
                {
                    "code": "validation_error",
                    "message": "Field 'name' is required and cannot be empty",
                    "target": {"type": "field", "name": "name"},
                },
                {"code": "internal_error", "message": "An unexpected error occurred"},
            ]
        }


class ErrorResponse(BaseModel):
    """REST API standard error response format."""

    errors: list[ErrorDetail] = Field(
        min_length=1,
        max_length=100,
        description="Array of error details (at least one error required)",
        json_schema_extra={
            "minItems": 1,
            "maxItems": 100,
        },
    )
    trace: str = Field(
        min_length=36,
        max_length=36,
        pattern="^[0-9a-f]{8}-[0-9a-f]{4}-[0-7][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12}$",
        description="Unique trace ID for debugging and request tracking",
        examples=["98765432-1098-1654-0210-987654321098"],
        json_schema_extra={
            "minLength": 36,
            "maxLength": 36,
            "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-7][0-9a-f]{3}-[089ab][0-9a-f]{3}-[0-9a-f]{12}$",
        },
    )
    status_code: int = Field(
        description="HTTP status code",
        ge=400,
        le=599,
        examples=[400, 404, 500],
        json_schema_extra={"format": "int32"},
    )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra: ClassVar[dict] = {
            "examples": [
                {
                    "errors": [
                        {
                            "code": "not_found",
                            "message": "Flow with ID '550e8400-e29b-41d4-a716-446655440000' not found",
                        }
                    ],
                    "trace": "req-abc-123",
                    "status_code": 404,
                },
                {
                    "errors": [
                        {
                            "code": "validation_error",
                            "message": "Field 'name' is required",
                            "target": {"type": "field", "name": "name"},
                        },
                        {
                            "code": "validation_error",
                            "message": "Field 'definition' must be a valid JSON object",
                            "target": {"type": "field", "name": "definition"},
                        },
                    ],
                    "trace": "req-def-456",
                    "status_code": 400,
                },
                {
                    "errors": [
                        {
                            "code": "internal_error",
                            "message": "An unexpected error occurred while processing the request",
                            "more_info": "https://docs.example.com/errors/internal_error",
                        }
                    ],
                    "trace": "req-ghi-789",
                    "status_code": 500,
                },
            ]
        }
