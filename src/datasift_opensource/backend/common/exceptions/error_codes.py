from enum import Enum


class ErrorCode(str, Enum):
    FLOW_VALIDATION_FAILED = "flow_validation_failed"
    FLOW_EXECUTION_FAILED = "flow_execution_failed"
    UNKNOWN_ERROR = "unknown_error"
    DATASIFT_DATA_ACCESS_COS_FAILED = "datasift_data_access_cos_failed"
    DATASIFT_DATA_ACCESS_S3_FAILED = "datasift_data_access_s3_failed"
    MISSING_FEATURES = "missing_features"
    PREFECT_FLOW_TASK_FAILED = "prefect_flow_failed"
    SQL_FILTER_ERROR = "sql_filter_error"
    INCOMPATIBLE_FEATURE_MAPPINGS = "incompatible_feature_mappings"
    OPENSEARCH_INSERT_FAILED = "opensearch_insert_failed"
    CONNECTIONS_API_FAILED = "connections_api_failed"
    INVALID_CONFIGURATION = "invalid_configuration"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
