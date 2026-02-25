from json import JSONEncoder
from typing import Dict, Any, Optional, List, Union

from common.exceptions.error_codes import ErrorCode
from common.exceptions.error_messages import ValidationMessage
from common.util.log import get_logger

logger = get_logger()


class DatasiftException(Exception):
    def __init__(self, message, status_code: int = 500, error_code: ErrorCode = None, message_code: str= None,
                 more_info: str = "https://www.ibm.com/docs/en/software-hub/5.2.x?topic=data-getting-started"):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.more_info = more_info
        self.message_code = message_code


class FlowNotFoundException(DatasiftException):
    # Thrown when the given flow or flow definition not found
    def __init__(self, message):
        super().__init__(message, 404)


class ValidationAlert(dict):
    def __init__(self, code=None, message = None, message_code = None, node_id=None, node_name=None, operator=None,  **kwargs):

        all_fields = {
            'code': code,
            'message': message,
            'message_code': message_code,
            'node_id': node_id,
            'node_name': node_name,
            'operator': operator,
            **kwargs
        }

        super().__init__(**all_fields)

        self.code: ErrorCode = code
        self.message: str = message
        self.message_code : str = message_code
        self.node_id = node_id
        self.node_name = node_name
        self.operator: str = operator

        # Set extra fields as instance attributes with validation
        self._set_extra_attributes(kwargs)

    def _set_extra_attributes(self, kwargs: Dict[str, Any]) -> None:
        """Set extra fields as instance attributes with basic validation."""
        for key, value in kwargs.items():
            if not isinstance(key, str) or not key.isidentifier():
                logger.warning(msg=f"Invalid attribute name: {key}", stack_info=True)
                continue
            setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        """Return a copy of the dictionary representation."""
        return dict(self)


class ValidationAlertEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__


class FlowExecutionFailedException(DatasiftException):
    # Thrown when the given flow or flow definition not found
    def __init__(self, message: str, status_code: int = 500, errors: list[ValidationAlert] = None):
        super().__init__(message, status_code)
        self.errors = errors


class FlowExecutionBlockedException(DatasiftException):
    def __init__(self, message: str, status_code: int = 500, errors: list[ValidationAlert] = None):
        super().__init__(message, status_code)
        self.errors = errors


class FlowValidationException(DatasiftException):
    def __init__(self, message="Invalid Flow definition",
                 errors: Optional[List[Union[ValidationAlert, ValidationMessage]]] = None,
                 warnings: Optional[List[Union[ValidationAlert, ValidationMessage]]] = None):
        super().__init__(message, 400)

        self.errors = errors
        self.warnings = warnings


class MaskedPasswordException(Exception):  # pragma: no cover
    def __init__(self, message):
        super().__init__(message)


class FlowCanceledException(DatasiftException):
    # Thrown when the given flow or flow definition is cancelled
    def __init__(self, message):
        super().__init__(message)


class PrefectFlowFailed(DatasiftException):
    #thrown when a prefect flow execution failed for a task
    def __init__(self, message, error_code: ErrorCode,  message_code: str= None, status_code: int = 500):
        super().__init__(message, error_code=error_code, message_code=message_code, status_code= status_code)
        
class CodeSecurityException(DatasiftException):
    def __init__(self, message:str  = "Code Security Violation", status_code:int = 400, err_code:ErrorCode = ErrorCode.CODE_SECURITY_VIOLATION):
        super().__init__(message, status_code, err_code)


class ValidationException(DatasiftException):
    def __init__(self, message="Invalid definition",
                 errors: Optional[List[Union[ValidationAlert, ValidationMessage]]] = None,
                 warnings: Optional[List[Union[ValidationAlert, ValidationMessage]]] = None):
        super().__init__(message, 400)

        self.errors = errors
        self.warnings = warnings

class InvalidDocumentTypeException(DatasiftException):
    def __init__(self, message):
        super().__init__(message)


class SetSelectOptionsException(DatasiftException):
    def __init__(self,message, status_code: int = 500, error_code: ErrorCode = None, message_code= None):
        super().__init__(message =message,status_code=status_code, error_code=error_code, message_code=message_code)
