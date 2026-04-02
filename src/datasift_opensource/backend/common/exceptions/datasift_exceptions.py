from json import JSONEncoder
from typing import Any

from common.exceptions.error_codes import ErrorCode
from common.exceptions.error_messages import ValidationMessage


class DatasiftException(Exception):
    def __init__(
        self,
        message,
        status_code: int = 500,
        error_code: ErrorCode | None = None,
        message_code: str | None = None,
        more_info: str = "https://www.ibm.com/docs/en/software-hub/5.2.x?topic=data-getting-started",
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.more_info = more_info
        self.message_code = message_code


class ValidationAlert(dict):
    def __init__(
        self,
        code=None,
        message=None,
        message_code=None,
        node_id=None,
        node_name=None,
        operator=None,
        **kwargs,
    ):
        all_fields = {
            "code": code,
            "message": message,
            "message_code": message_code,
            "node_id": node_id,
            "node_name": node_name,
            "operator": operator,
            **kwargs,
        }

        super().__init__(**all_fields)

        self.code: ErrorCode = code
        self.message: str = message
        self.message_code: str = message_code
        self.node_id = node_id
        self.node_name = node_name
        self.operator: str = operator

        # Set extra fields as instance attributes with validation
        self._set_extra_attributes(kwargs)

    def _set_extra_attributes(self, kwargs: dict[str, Any]) -> None:
        """Set extra fields as instance attributes with basic validation."""
        for key, value in kwargs.items():
            if not isinstance(key, str) or not key.isidentifier():
                # Lazy import to avoid circular dependency
                from common.util.infrastructure.logging import get_logger

                logger = get_logger()
                logger.warning(msg=f"Invalid attribute name: {key}", stack_info=True)
                continue
            setattr(self, key, value)

    def to_dict(self) -> dict[str, Any]:
        """Return a copy of the dictionary representation."""
        return dict(self)


class ValidationAlertEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__


class FlowExecutionFailedException(DatasiftException):
    # Thrown when the given flow or flow definition not found
    def __init__(self, message: str, status_code: int = 500, errors: list[ValidationAlert] | None = None):
        from common.exceptions.error_codes import ErrorCode

        super().__init__(message, status_code, error_code=ErrorCode.FLOW_EXECUTION_FAILED)
        self.errors = errors


class FlowValidationException(DatasiftException):
    def __init__(
        self,
        message="Invalid Flow definition",
        errors: list[ValidationAlert | ValidationMessage] | None = None,
        warnings: list[ValidationAlert | ValidationMessage] | None = None,
    ):
        super().__init__(message, 400)

        self.errors = errors
        self.warnings = warnings


class PrefectFlowFailed(DatasiftException):
    # thrown when a prefect flow execution failed for a task
    def __init__(
        self,
        message,
        error_code: ErrorCode,
        message_code: str | None = None,
        status_code: int = 500,
    ):
        super().__init__(
            message,
            error_code=error_code,
            message_code=message_code,
            status_code=status_code,
        )


class ValidationException(DatasiftException):
    def __init__(
        self,
        message="Invalid definition",
        errors: list[ValidationAlert | ValidationMessage] | None = None,
        warnings: list[ValidationAlert | ValidationMessage] | None = None,
    ):
        super().__init__(message, 400)

        self.errors = errors
        self.warnings = warnings


class ConfigurationError(DatasiftException):
    """
    Exception raised for configuration errors.

    Used when required configuration parameters are missing or invalid,
    such as missing API keys, invalid credentials, or malformed settings.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode | None = ErrorCode.INVALID_CONFIGURATION,
        status_code: int = 400,
    ):
        super().__init__(
            message,
            status_code=status_code,
            error_code=error_code,
        )


class DependencyError(DatasiftException):
    """
    Exception raised when required dependencies are missing.

    Used when optional packages or libraries are not installed
    but are required for specific functionality.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode | None = ErrorCode.EXTERNAL_SERVICE_ERROR,
        status_code: int = 500,
    ):
        super().__init__(
            message,
            status_code=status_code,
            error_code=error_code,
        )


class ExternalServiceError(DatasiftException):
    """
    Exception raised when external service calls fail.

    Used for API errors, network failures, authentication errors,
    rate limits, and other external service-related issues.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode | None = ErrorCode.EXTERNAL_SERVICE_ERROR,
        status_code: int = 502,
    ):
        super().__init__(
            message,
            status_code=status_code,
            error_code=error_code,
        )
