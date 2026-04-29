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


class FlowNotFoundException(DatasiftException):
    """
    Exception raised when a flow is not found.

    Used in flow CRUD operations when attempting to retrieve, update,
    or delete a flow that does not exist.
    """

    def __init__(
        self,
        message: str,
        flow_id: str | None = None,
    ):
        if flow_id and not message:
            message = f"Flow {flow_id} not found"
        super().__init__(
            message,
            status_code=404,
            error_code=ErrorCode.FLOW_NOT_FOUND,
        )
        self.flow_id = flow_id


class FlowAlreadyExistsException(DatasiftException):
    """
    Exception raised when attempting to create a flow that already exists.

    Used in flow creation when a flow with the same name or ID already exists.
    """

    def __init__(
        self,
        message: str,
        flow_id: str | None = None,
        flow_name: str | None = None,
    ):
        super().__init__(
            message,
            status_code=409,
            error_code=ErrorCode.FLOW_ALREADY_EXISTS,
        )
        self.flow_id = flow_id
        self.flow_name = flow_name


class FlowInvalidDataException(DatasiftException):
    """
    Exception raised when flow data is invalid.

    Used in flow CRUD operations when validation fails due to invalid
    flow data, empty names, invalid field values, or malformed JSON.
    """

    def __init__(
        self,
        message: str,
        field_name: str | None = None,
    ):
        super().__init__(
            message,
            status_code=400,
            error_code=ErrorCode.FLOW_INVALID_DATA,
        )
        self.field_name = field_name


class FlowStorageException(DatasiftException):
    """
    Exception raised when flow storage operations fail.

    Used in flow CRUD operations when file system errors occur,
    such as permission errors, disk full, corrupted files, or I/O errors.
    """

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        flow_id: str | None = None,
    ):
        super().__init__(
            message,
            status_code=500,
            error_code=ErrorCode.FLOW_STORAGE_ERROR,
        )
        self.operation = operation
        self.flow_id = flow_id


class RepositoryConfigurationException(DatasiftException):
    """
    Exception raised when repository configuration is invalid.

    Used when repository type selection or repository-specific settings
    are missing, unsupported, or malformed.
    """

    def __init__(
        self,
        message: str,
        repository_type: str | None = None,
        valid_types: list[str] | None = None,
        status_code: int = 400,
    ):
        super().__init__(message, status_code=status_code, error_code=ErrorCode.INVALID_CONFIGURATION)
        self.repository_type = repository_type
        self.valid_types = valid_types


class JobRunNotFoundException(DatasiftException):
    """
    Exception raised when a job run is not found.

    Used in job run operations when attempting to retrieve, update,
    cancel, or delete a job run that does not exist.
    """

    def __init__(
        self,
        message: str,
        job_run_id: str | None = None,
    ):
        if job_run_id and not message:
            message = f"Job run {job_run_id} not found"
        super().__init__(
            message,
            status_code=404,
            error_code=ErrorCode.JOB_RUN_NOT_FOUND,
        )
        self.job_run_id = job_run_id


class JobRunAlreadyExistsException(DatasiftException):
    """
    Exception raised when attempting to create a job run that already exists.

    Used in job run creation when a job run with the same ID already exists.
    """

    def __init__(
        self,
        message: str,
        job_run_id: str | None = None,
    ):
        super().__init__(
            message,
            status_code=409,
            error_code=ErrorCode.JOB_RUN_ALREADY_EXISTS,
        )
        self.job_run_id = job_run_id


class JobRunInvalidStateException(DatasiftException):
    """
    Exception raised when job run operation is invalid for current state.

    Used when attempting operations that are not valid for the job run's
    current state (e.g., canceling a completed job, deleting a running job).
    """

    def __init__(
        self,
        message: str,
        job_run_id: str | None = None,
        current_state: str | None = None,
    ):
        super().__init__(
            message,
            status_code=400,
            error_code=ErrorCode.JOB_RUN_INVALID_STATE,
        )
        self.job_run_id = job_run_id
        self.current_state = current_state


class JobRunOperationFailedException(DatasiftException):
    """
    Exception raised when a job run operation fails.

    Used for general job run operation failures such as cancellation
    failures, deletion failures, or status update failures.
    """

    def __init__(
        self,
        message: str,
        job_run_id: str | None = None,
        operation: str | None = None,
    ):
        super().__init__(
            message,
            status_code=500,
            error_code=ErrorCode.JOB_RUN_OPERATION_FAILED,
        )
        self.job_run_id = job_run_id
        self.operation = operation


class DatabaseMigrationException(DatasiftException):
    """
    Exception raised when database migration operations fail.

    Used for Alembic migration failures, schema initialization errors,
    or migration configuration issues.
    """

    def __init__(
        self,
        *,
        message: str,
        operation: str | None = None,
        status_code: int = 500,
    ):
        super().__init__(
            message,
            status_code=status_code,
            error_code=ErrorCode.DATABASE_MIGRATION_FAILED,
        )
        self.operation = operation


class JobStatsStoreException(DatasiftException):
    """
    Base exception for job stats store operations.

    Used as base class for all job stats store-related exceptions.
    """

    def __init__(
        self,
        *,
        message: str,
        error_code: ErrorCode,
        job_run_id: str | None = None,
        operation: str | None = None,
        status_code: int = 500,
    ):
        super().__init__(
            message,
            status_code=status_code,
            error_code=error_code,
        )
        self.job_run_id = job_run_id
        self.operation = operation


class JobStatsStoreReadException(JobStatsStoreException):
    """
    Exception raised when reading from job stats store fails.

    Used for get_job_stats, get_node_stats, list_jobs failures.
    """

    def __init__(
        self,
        *,
        message: str,
        job_run_id: str | None = None,
        operation: str | None = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.JOB_STATS_STORE_READ_FAILED,
            job_run_id=job_run_id,
            operation=operation,
            status_code=500,
        )


class JobStatsStoreWriteException(JobStatsStoreException):
    """
    Exception raised when writing to job stats store fails.

    Used for store_job_stats, store_node_stats, bulk_store_node_stats failures.
    """

    def __init__(
        self,
        *,
        message: str,
        job_run_id: str | None = None,
        operation: str | None = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.JOB_STATS_STORE_WRITE_FAILED,
            job_run_id=job_run_id,
            operation=operation,
            status_code=500,
        )


class JobStatsStoreDeleteException(JobStatsStoreException):
    """
    Exception raised when deleting from job stats store fails.

    Used for delete_job_stats failures.
    """

    def __init__(
        self,
        *,
        message: str,
        job_run_id: str | None = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.JOB_STATS_STORE_DELETE_FAILED,
            job_run_id=job_run_id,
            operation="delete",
            status_code=500,
        )


class JobStatsStoreAtomicUpdateException(JobStatsStoreException):
    """
    Exception raised when atomic update operations fail.

    Used for atomic_increment_fields failures.
    """

    def __init__(
        self,
        *,
        message: str,
        job_run_id: str | None = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.JOB_STATS_STORE_ATOMIC_UPDATE_FAILED,
            job_run_id=job_run_id,
            operation="atomic_update",
            status_code=500,
        )


class JobStatsStoreInitializationException(JobStatsStoreException):
    """
    Exception raised when job stats store initialization fails.

    Used for store initialization, connection setup, migration failures.
    """

    def __init__(
        self,
        *,
        message: str,
        store_type: str | None = None,
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.JOB_STATS_STORE_INITIALIZATION_FAILED,
            operation="initialization",
            status_code=500,
        )
        self.store_type = store_type


class PostgresConnectionException(DatasiftException):
    """
    Exception raised when PostgreSQL connection fails.

    Used for connection establishment, engine creation failures.
    """

    def __init__(
        self,
        *,
        message: str,
        host: str | None = None,
        database: str | None = None,
    ):
        super().__init__(
            message,
            status_code=500,
            error_code=ErrorCode.POSTGRES_CONNECTION_FAILED,
        )
        self.host = host
        self.database = database


class PostgresOperationException(DatasiftException):
    """
    Exception raised when PostgreSQL operations fail.

    Used for DAO/DAL operation failures (insert, update, delete, select).
    """

    def __init__(
        self,
        *,
        message: str,
        operation: str | None = None,
        table: str | None = None,
    ):
        super().__init__(
            message,
            status_code=500,
            error_code=ErrorCode.POSTGRES_OPERATION_FAILED,
        )
        self.operation = operation
        self.table = table


class PostgresTransactionException(DatasiftException):
    """
    Exception raised when PostgreSQL transaction fails.

    Used for transaction commit, rollback failures.
    """

    def __init__(
        self,
        *,
        message: str,
        operation: str | None = None,
    ):
        super().__init__(
            message,
            status_code=500,
            error_code=ErrorCode.POSTGRES_TRANSACTION_FAILED,
        )
        self.operation = operation


class PostgresQueryException(DatasiftException):
    """
    Exception raised when PostgreSQL query execution fails.

    Used for SQL query execution failures, syntax errors.
    """

    def __init__(
        self,
        *,
        message: str,
        query: str | None = None,
    ):
        super().__init__(
            message,
            status_code=500,
            error_code=ErrorCode.POSTGRES_QUERY_FAILED,
        )
        self.query = query


__all__ = [
    "ConfigurationError",
    "DatabaseMigrationException",
    "DatasiftException",
    "DependencyError",
    "ExternalServiceError",
    "FlowAlreadyExistsException",
    "FlowExecutionFailedException",
    "FlowInvalidDataException",
    "FlowNotFoundException",
    "FlowStorageException",
    "FlowValidationException",
    "JobRunAlreadyExistsException",
    "JobRunInvalidStateException",
    "JobRunNotFoundException",
    "JobRunOperationFailedException",
    "JobStatsStoreAtomicUpdateException",
    "JobStatsStoreDeleteException",
    "JobStatsStoreException",
    "JobStatsStoreInitializationException",
    "JobStatsStoreReadException",
    "JobStatsStoreWriteException",
    "PostgresConnectionException",
    "PostgresOperationException",
    "PostgresQueryException",
    "PostgresTransactionException",
    "PrefectFlowFailed",
    "RepositoryConfigurationException",
    "ValidationAlert",
    "ValidationAlertEncoder",
    "ValidationException",
]
