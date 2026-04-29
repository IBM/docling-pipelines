from enum import StrEnum


class ErrorCode(StrEnum):
    # Flow validation and execution
    FLOW_VALIDATION_FAILED = "flow_validation_failed"
    FLOW_EXECUTION_FAILED = "flow_execution_failed"
    PREFECT_FLOW_TASK_FAILED = "prefect_flow_failed"

    # Flow CRUD operations
    FLOW_NOT_FOUND = "flow_not_found"
    FLOW_ALREADY_EXISTS = "flow_already_exists"
    FLOW_INVALID_DATA = "flow_invalid_data"

    # Job run operations
    JOB_RUN_NOT_FOUND = "job_run_not_found"
    JOB_RUN_ALREADY_EXISTS = "job_run_already_exists"
    JOB_RUN_INVALID_STATE = "job_run_invalid_state"
    JOB_RUN_OPERATION_FAILED = "job_run_operation_failed"
    FLOW_STORAGE_ERROR = "flow_storage_error"

    # Document Set CRUD operations
    DOCUMENT_SET_NOT_FOUND = "document_set_not_found"
    DOCUMENT_SET_INVALID_DATA = "document_set_invalid_data"
    DOCUMENT_SET_STORAGE_ERROR = "document_set_storage_error"

    # Operator errors
    OPERATOR_CONFIGURATION_INVALID = "operator_configuration_invalid"
    OPERATOR_EXECUTION_FAILED = "operator_execution_failed"
    OPERATOR_METADATA_FAILED = "operator_metadata_failed"
    SQL_FILTER_ERROR = "sql_filter_error"

    # Ollama integration
    OLLAMA_CONNECTION_FAILED = "ollama_connection_failed"
    OLLAMA_MODEL_NOT_FOUND = "ollama_model_not_found"

    # OpenSearch integration
    OPENSEARCH_CONNECTION_FAILED = "opensearch_connection_failed"
    OPENSEARCH_INDEX_ERROR = "opensearch_index_error"

    # Database operations - PostgreSQL
    DATABASE_MIGRATION_FAILED = "database_migration_failed"
    POSTGRES_CONNECTION_FAILED = "postgres_connection_failed"
    POSTGRES_OPERATION_FAILED = "postgres_operation_failed"
    POSTGRES_TRANSACTION_FAILED = "postgres_transaction_failed"
    POSTGRES_QUERY_FAILED = "postgres_query_failed"

    # Job stats store operations
    JOB_STATS_STORE_READ_FAILED = "job_stats_store_read_failed"
    JOB_STATS_STORE_WRITE_FAILED = "job_stats_store_write_failed"
    JOB_STATS_STORE_DELETE_FAILED = "job_stats_store_delete_failed"
    JOB_STATS_STORE_LIST_FAILED = "job_stats_store_list_failed"
    JOB_STATS_STORE_ATOMIC_UPDATE_FAILED = "job_stats_store_atomic_update_failed"
    JOB_STATS_STORE_INITIALIZATION_FAILED = "job_stats_store_initialization_failed"

    # Configuration and external services
    INVALID_CONFIGURATION = "invalid_configuration"
    EXTERNAL_SERVICE_ERROR = "external_service_error"

    # REST client errors
    HTTP_ERROR = "http_error"
    CONNECTION_ERROR = "connection_error"
    INVALID_RESPONSE = "invalid_response"
