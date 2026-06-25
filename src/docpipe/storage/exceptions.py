"""Storage-specific exceptions."""

from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode


class StorageException(DocpipeException):
    """Base exception for storage-related errors."""

    def __init__(self, *, message: str, status_code: int = 500):
        super().__init__(message, status_code=status_code, error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR)


class StorageNotFoundError(StorageException):
    """Exception raised when a storage resource is not found."""

    def __init__(self, *, message: str):
        super().__init__(message=message, status_code=404)


class StorageValidationError(StorageException):
    """Exception raised when storage validation fails."""

    def __init__(self, *, message: str):
        super().__init__(message=message, status_code=400)


class StorageConnectionError(StorageException):
    """Exception raised when storage connection fails."""

    def __init__(self, *, message: str):
        super().__init__(message=message, status_code=503)
