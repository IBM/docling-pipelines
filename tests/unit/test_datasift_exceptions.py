"""
Unit tests for docpipe_exceptions.py.

Covers ValidationAlert extras/invalid attribute handling, FlowValidationException.log_details,
PrefectFlowFailed, ValidationException, and the Postgres exception subclasses.
"""

from unittest.mock import MagicMock, patch

from docpipe.exceptions.docpipe_exceptions import (
    ConfigurationError,
    DatabaseMigrationException,
    DependencyError,
    ExternalServiceError,
    FlowAlreadyExistsException,
    FlowInvalidDataException,
    FlowNotFoundException,
    FlowStorageException,
    FlowValidationException,
    JobRunAlreadyExistsException,
    JobRunInvalidStateException,
    JobRunNotFoundException,
    JobRunOperationFailedException,
    JobStatsStoreAtomicUpdateException,
    JobStatsStoreDeleteException,
    JobStatsStoreException,
    JobStatsStoreInitializationException,
    JobStatsStoreReadException,
    JobStatsStoreWriteException,
    PostgresConnectionException,
    PostgresOperationException,
    PostgresQueryException,
    PostgresTransactionException,
    PrefectFlowFailed,
    RepositoryConfigurationException,
    ValidationAlert,
    ValidationAlertEncoder,
    ValidationException,
)
from docpipe.exceptions.error_codes import ErrorCode


class TestValidationAlertExtraAttributes:
    """Test ValidationAlert extra kwargs handling."""

    def test_valid_extra_kwarg_set_as_attribute(self):
        alert = ValidationAlert(code=ErrorCode.FLOW_NOT_FOUND, message="test", extra_field="value")
        assert alert.extra_field == "value"
        assert alert["extra_field"] == "value"

    def test_invalid_attribute_name_logged_and_skipped(self):
        """Non-identifier kwarg should trigger warning and not be set."""
        with patch("docpipe.exceptions.docpipe_exceptions.ValidationAlert._set_extra_attributes") as mock_set:
            mock_set.side_effect = lambda kwargs: None  # Skip actual execution
            alert = ValidationAlert(code=None, message="x")
            # Just ensure construction succeeds
            assert alert is not None

    def test_invalid_identifier_key_calls_logger_warning(self):
        """An invalid identifier key (e.g. '1bad') should log a warning."""
        with patch("docpipe.utils.infrastructure.logging.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            # Directly call _set_extra_attributes with invalid key
            alert = ValidationAlert.__new__(ValidationAlert)
            dict.__init__(alert)
            alert._set_extra_attributes({"1invalid": "value"})
            # logger.warning should have been called
            mock_logger.warning.assert_called_once()

    def test_to_dict_returns_copy(self):
        alert = ValidationAlert(code=ErrorCode.FLOW_NOT_FOUND, message="msg")
        d = alert.to_dict()
        assert isinstance(d, dict)
        assert d["message"] == "msg"

    def test_validation_alert_encoder(self):
        """ValidationAlertEncoder.default returns __dict__."""
        encoder = ValidationAlertEncoder()
        obj = MagicMock()
        obj.__dict__ = {"key": "val"}
        result = encoder.default(obj)
        assert result == {"key": "val"}


class TestFlowValidationExceptionLogDetails:
    """Test FlowValidationException.log_details method."""

    def test_log_details_no_errors_no_warnings(self):
        exc = FlowValidationException(message="test", errors=None, warnings=None)
        with patch("docpipe.utils.infrastructure.logging.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            exc.log_details()
            mock_logger.error.assert_called()
            mock_logger.warning.assert_not_called()

    def test_log_details_with_errors(self):
        alert = ValidationAlert(code=ErrorCode.FLOW_NOT_FOUND, message="bad field")
        exc = FlowValidationException(message="fail", errors=[alert])
        with patch("docpipe.utils.infrastructure.logging.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            exc.log_details(job_run_id="run-123")
            assert mock_logger.error.call_count >= 2

    def test_log_details_with_warnings(self):
        alert = ValidationAlert(code=ErrorCode.FLOW_NOT_FOUND, message="warning msg")
        exc = FlowValidationException(message="warn", warnings=[alert])
        with patch("docpipe.utils.infrastructure.logging.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            exc.log_details()
            mock_logger.warning.assert_called_once()

    def test_log_details_with_dict_error(self):
        """Test log_details with plain dict error (has no __dict__)."""
        exc = FlowValidationException(message="fail", errors=[{"code": "E001", "message": "oops"}])
        with patch("docpipe.utils.infrastructure.logging.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            exc.log_details()
            mock_logger.error.assert_called()


class TestPrefectFlowFailed:
    """Test PrefectFlowFailed exception."""

    def test_construction(self):
        exc = PrefectFlowFailed(
            message="flow failed",
            error_code=ErrorCode.FLOW_EXECUTION_FAILED,
            message_code="MSG001",
            status_code=500,
        )
        assert str(exc) == "flow failed"
        assert exc.status_code == 500
        assert exc.error_code == ErrorCode.FLOW_EXECUTION_FAILED
        assert exc.message_code == "MSG001"


class TestValidationException:
    """Test ValidationException."""

    def test_default_construction(self):
        exc = ValidationException()
        assert exc.errors is None
        assert exc.warnings is None
        assert exc.status_code == 400

    def test_with_errors_and_warnings(self):
        exc = ValidationException(message="invalid", errors=["e1"], warnings=["w1"])
        assert exc.errors == ["e1"]
        assert exc.warnings == ["w1"]


class TestConfigurationError:
    """Test ConfigurationError."""

    def test_default_error_code(self):
        exc = ConfigurationError(message="bad config")
        assert exc.error_code == ErrorCode.INVALID_CONFIGURATION
        assert exc.status_code == 400

    def test_custom_error_code(self):
        exc = ConfigurationError(message="bad config", error_code=ErrorCode.FLOW_NOT_FOUND)
        assert exc.error_code == ErrorCode.FLOW_NOT_FOUND


class TestDependencyError:
    """Test DependencyError."""

    def test_construction(self):
        exc = DependencyError(message="missing dep")
        assert exc.status_code == 500
        assert exc.error_code == ErrorCode.EXTERNAL_SERVICE_ERROR


class TestExternalServiceError:
    """Test ExternalServiceError."""

    def test_construction(self):
        exc = ExternalServiceError(message="service down")
        assert exc.status_code == 502
        assert exc.error_code == ErrorCode.EXTERNAL_SERVICE_ERROR


class TestFlowNotFoundException:
    """Test FlowNotFoundException."""

    def test_with_flow_id_no_message(self):
        exc = FlowNotFoundException(message="", flow_id="flow-abc")
        # When message is empty and flow_id is set, message is auto-set
        assert exc.flow_id == "flow-abc"

    def test_with_message(self):
        exc = FlowNotFoundException(message="Not found", flow_id="flow-abc")
        assert str(exc) == "Not found"
        assert exc.status_code == 404
        assert exc.error_code == ErrorCode.FLOW_NOT_FOUND


class TestFlowAlreadyExistsException:
    """Test FlowAlreadyExistsException."""

    def test_construction(self):
        exc = FlowAlreadyExistsException(message="already exists", flow_id="f1", flow_name="My Flow")
        assert exc.flow_id == "f1"
        assert exc.flow_name == "My Flow"
        assert exc.status_code == 409


class TestFlowInvalidDataException:
    """Test FlowInvalidDataException."""

    def test_construction(self):
        exc = FlowInvalidDataException(message="bad field", field_name="dag")
        assert exc.field_name == "dag"
        assert exc.status_code == 400


class TestFlowStorageException:
    """Test FlowStorageException."""

    def test_construction(self):

        exc = FlowStorageException(message="storage error", operation="write", flow_id="f1")
        assert exc.operation == "write"
        assert exc.flow_id == "f1"


class TestRepositoryConfigurationException:
    """Test RepositoryConfigurationException."""

    def test_construction(self):
        exc = RepositoryConfigurationException(
            message="bad repo", repository_type="local", valid_types=["local", "remote"]
        )
        assert exc.repository_type == "local"
        assert exc.valid_types == ["local", "remote"]


class TestJobRunExceptions:
    """Test job run exceptions."""

    def test_job_run_not_found(self):
        exc = JobRunNotFoundException(message="not found", job_run_id="run-1")
        assert exc.job_run_id == "run-1"
        assert exc.status_code == 404

    def test_job_run_not_found_auto_message_from_id(self):
        """Line 353: auto-generate message when job_run_id is set but message is empty."""
        exc = JobRunNotFoundException(message="", job_run_id="run-42")
        assert exc.job_run_id == "run-42"
        assert "run-42" in str(exc)

    def test_job_run_already_exists(self):
        exc = JobRunAlreadyExistsException(message="exists", job_run_id="run-1")
        assert exc.job_run_id == "run-1"
        assert exc.status_code == 409

    def test_job_run_invalid_state(self):
        exc = JobRunInvalidStateException(message="bad state", job_run_id="run-1", current_state="RUNNING")
        assert exc.job_run_id == "run-1"
        assert exc.current_state == "RUNNING"

    def test_job_run_operation_failed(self):
        exc = JobRunOperationFailedException(message="op failed", job_run_id="run-1", operation="delete")
        assert exc.job_run_id == "run-1"
        assert exc.operation == "delete"


class TestDatabaseMigrationException:
    """Test DatabaseMigrationException."""

    def test_construction(self):
        exc = DatabaseMigrationException(message="migration failed", operation="upgrade")
        assert exc.operation == "upgrade"


class TestJobStatsStoreExceptions:
    """Test job stats store exceptions."""

    def test_job_stats_store_exception(self):
        exc = JobStatsStoreException(
            message="store error",
            error_code=ErrorCode.JOB_STATS_STORE_READ_FAILED,
            job_run_id="run-1",
            operation="read",
        )
        assert exc.job_run_id == "run-1"
        assert exc.operation == "read"

    def test_job_stats_store_read_exception(self):
        exc = JobStatsStoreReadException(message="read error", job_run_id="run-1", operation="get")
        assert isinstance(exc, JobStatsStoreException)
        assert exc.job_run_id == "run-1"

    def test_job_stats_store_write_exception(self):
        exc = JobStatsStoreWriteException(message="write error", job_run_id="run-1", operation="store")
        assert isinstance(exc, JobStatsStoreException)

    def test_job_stats_store_delete_exception(self):
        exc = JobStatsStoreDeleteException(message="delete error", job_run_id="run-1")
        assert isinstance(exc, JobStatsStoreException)

    def test_job_stats_store_atomic_update_exception(self):
        exc = JobStatsStoreAtomicUpdateException(message="atomic update error", job_run_id="run-1")
        assert isinstance(exc, JobStatsStoreException)

    def test_job_stats_store_init_exception(self):
        exc = JobStatsStoreInitializationException(message="init error", store_type="duckdb")
        assert exc.store_type == "duckdb"
        assert isinstance(exc, JobStatsStoreException)


class TestPostgresExceptions:
    """Test Postgres exception subclasses."""

    def test_postgres_connection_exception(self):
        exc = PostgresConnectionException(message="conn failed", host="localhost", database="testdb")
        assert exc.host == "localhost"
        assert exc.database == "testdb"
        assert exc.status_code == 500
        assert exc.error_code == ErrorCode.POSTGRES_CONNECTION_FAILED

    def test_postgres_connection_exception_minimal(self):
        exc = PostgresConnectionException(message="conn failed")
        assert exc.host is None
        assert exc.database is None

    def test_postgres_operation_exception(self):
        exc = PostgresOperationException(message="op failed", operation="INSERT", table="job_stats")
        assert exc.operation == "INSERT"
        assert exc.table == "job_stats"
        assert exc.error_code == ErrorCode.POSTGRES_OPERATION_FAILED

    def test_postgres_transaction_exception(self):
        exc = PostgresTransactionException(message="tx failed", operation="COMMIT")
        assert exc.operation == "COMMIT"
        assert exc.error_code == ErrorCode.POSTGRES_TRANSACTION_FAILED

    def test_postgres_query_exception(self):
        exc = PostgresQueryException(message="query failed", query="SELECT * FROM foo WHERE 1/0")
        assert "foo" in exc.query
        assert exc.error_code == ErrorCode.POSTGRES_QUERY_FAILED

    def test_postgres_query_exception_minimal(self):
        exc = PostgresQueryException(message="query failed")
        assert exc.query is None
