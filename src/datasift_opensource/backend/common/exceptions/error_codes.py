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
    FLOW_STORAGE_ERROR = "flow_storage_error"

    # Operator errors
    OPERATOR_CONFIGURATION_INVALID = "operator_configuration_invalid"
    OPERATOR_EXECUTION_FAILED = "operator_execution_failed"
    SQL_FILTER_ERROR = "sql_filter_error"

    # Ollama integration
    OLLAMA_CONNECTION_FAILED = "ollama_connection_failed"
    OLLAMA_MODEL_NOT_FOUND = "ollama_model_not_found"

    # OpenSearch integration
    OPENSEARCH_CONNECTION_FAILED = "opensearch_connection_failed"
    OPENSEARCH_INDEX_ERROR = "opensearch_index_error"

    # Configuration and external services
    INVALID_CONFIGURATION = "invalid_configuration"
    EXTERNAL_SERVICE_ERROR = "external_service_error"

    # REST client errors
    HTTP_ERROR = "http_error"
    CONNECTION_ERROR = "connection_error"
    INVALID_RESPONSE = "invalid_response"
