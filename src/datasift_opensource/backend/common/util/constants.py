import os
from enum import Enum
from typing import TypedDict


class DatasiftConstants:
    # Defines constants that are used across Datasift service
    INPUT = "input"
    LOGGER_NAME = "DATASIFT"
    SESSION_INFO = "session_info"
    BEARER = "Bearer "
    BASIC = "Basic "
    CONTEXT_ID = "context_id"
    FORCE_INGEST = "force_ingest"
    RETAIN_DELETED_DOCS = "retain_deleted_docs"
    RETAIN_DELETED_DOCS_DEFAULT = True
    DATA_FOLDER = "data_folder"
    OPERAND_NAMESPACE = "OPERAND_NAMESPACE"
    WDU_SERVER = "WDU_SERVER"
    WML_SERVER = "WML_SERVER"
    DAG = "dag"
    FLOW_ID = "flow_id"
    FLOW_NAME = "flow_name"
    FLOW_DESCRIPTION = "flow_description"
    FLOW_DEFINITION = "flow_definition"
    GEN_AI_INGEST_FLOW = "gen_ai_ingest_flow"
    FLOW_VERSION = "flow_version"
    FLOW_VERSION_2 = "2.0"
    JOB = "job"
    JOB_ID = "job_id"
    NODE_ID = "node_id"
    NODE_NAME = "node_name"
    JOB_RUN = "job_run"
    JOB_RUN_ID = "job_run_id"
    TRACK_PERF = "track_perf"
    DATASIFT = "datasift"
    TEMPLATE_FLAG = "is_template"
    RESOURCES = "resources"
    METADATA = "metadata"
    TRACE_MEMORY_ALLOCATIONS = "TRACE_MEMORY_ALLOCATIONS"
    ASYNC_MODE = "async_mode"
    METRICS = "metrics"
    DEFAULT_TRANSACTION_ID = "TRANSACTION999"
    UDP_LOGS = "UDP_logs"
    INCREMENTAL_PROCESSING_METADATA_PATH = "inc_process_metadata"
    JOBS_STATS_PATH = "job-stats"
    NODE_STATS_PATH = "node-stats"
    TRANSACTION_ID = "transaction_id"
    OUTPUT_FOLDER = "output_folder"
    MASKED_PASSWORD_PATTERN = r"^\*+$"  # Regex pattern to detect masked passwords
    OUTPUT_FEATURES_TO_DROP = "output_features_to_drop"
    LINK_NAME = "link_name"
    ASSET_CATEGORY_SYSTEM = "SYSTEM"
    UPDATED_FEATURES = "updated_features"
    NAME = "name"
    UUID = "uuid"
    STATUS = "status"
    STATE = "state"
    MESSAGE = "message"
    LAST_UPDATED_AT = "last_updated_at"
    ASSET = "asset"
    PROPAGATE_SOURCE_ACLS = "propagate_source_acls"
    FLOWS = "flows"
    FLOW = "flow"
    DETAILS = "details"
    JOBS = "jobs"
    RUNS = "runs"
    OPERATORS = "operators"
    DERIVATIVE_STORE = "derivative_store"
    DOCUMENTS = "documents"
    OPERATOR_FILE = "operator_file"
    DEPENDENCY_ARCHIVE = "dependency_archive"
    PACKAGE_ARCHIVE = "package_archive"
    IS_DERIVATIVE_AVAILABLE = "is_derivative_available"
    SUMMARY = "summary"
    VALIDATION_FAILED = "validation_failed"
    PYTHON_PATH = "PYTHONPATH"
    ABSTRACT_OPERATOR = "AbstractOperator"
    VALIDATING_FLOW = "validating_flow"
    DEEPCOPY = "deepcopy"
    AUTO_COPY_REMOTE_CONNECTIONS = "auto_copy_remote_connections"
    SKIP_CUSTOM_OP_VALIDATION = "skip_custom_op_validation"
    SUCCESS = "success"
    OBJECTS = "objects"
    IS_SPARK_RUNTIME = "IS_SPARK_RUNTIME"
    TMP = "tmp"
    TARGET_ASSET_STORAGE_PATH = "/datasift/storage/job-assets"
    ENABLE_MICRO_BATCHING = "enable_micro_batching"
    MICRO_BATCH_SIZE = "micro_batch_size"
    DEFAULT_MICRO_BATCH_SIZE = 100
    BATCH_NUM = "batch_num"
    BATCH_COUNT = "batch_count"
    INGEST_NODE_ID = "ingest_node_id"
    MAX_CONCURRENT_TASKS = "max_concurrent_tasks"
    DEFAULT_MAX_CONCURRENT_TASKS = 10
    OPERATOR_SEMAPHORE = "_operator_semaphore"
    SUCCESS_FILE_PATH = os.path.join(TARGET_ASSET_STORAGE_PATH, "_SUCCESS")
    BUILD_VERSION = "BUILD_VERSION"
    PARQUET_BATCH_SIZE = 1000
    DEFAULT_SCHEMA = "datasift"
    LANGUAGE_LABEL = "language_label"
    LANGUAGE_CODE = "language_code"
    SCRIPT_CODE = "script_code"
    SCRIPT_LABEL = "script_label"


# Datasource Type Constants
# Used for identifying the type of vector store or entity table connection
DATASOURCE_TYPE = "datasource_type"


class Metrics:
    class External:
        JOB_RUN_STATUS = "job_run_status"
        TOTAL_DOCS = "total_docs_count"
        TOTAL_DOCS_COUNT_FROM_LOGS = "total_docs"
        PROCESSED_DOCS = "processed_docs"
        PROCESSED_ROWS = "processed_rows"
        FAILED_DOCS_COUNT = "failed_docs_count"
        FAILED_DOCS = "failed_docs"
        SKIPPED_DOCS_COUNT = "skipped_docs_count"
        SKIPPED_DOCS = "skipped_docs"
        TOTAL_PAGES_CONVERTED = "total_pages_converted"
        NODE_STATUS = "node_status"
        UNPROCESSED_DOC_COUNT = "unprocessed_doc_count"
        DELETED_DOC_COUNT = "deleted_doc_count"
        START_TIME = "start_time"
        END_TIME = "end_time"
        REMOVED_DOCUMENTS = "removed_documents"
        PROCESSING_MESSAGE = "processing_message"
        TOTAL_CHUNKS = "total_chunks"
        CHUNKS_PROCESSED = "chunks_processed"
        CHUNKS_FAILED = "chunks_failed"
        CHUNKS_SKIPPED_EXISTING = "chunks_skipped_existing"

    class Internal:
        DELETED_FROM_LAST_RUN = "deleted_from_last_run"
        ALL_DOC_IDS = "all_doc_ids"
        BRANCHES = "branches"

    # Metrics that require atomic aggregation to prevent race conditions
    AGGREGATION_METRICS = frozenset(
        {External.TOTAL_PAGES_CONVERTED, External.DELETED_DOC_COUNT}
    )


# Internal metrics used in multiple places so making it as a global variable
internal_metrics = {
    value for name, value in vars(Metrics.Internal).items() if not name.startswith("__")
}


class BucketTypes:
    DEDICATED = "dedicated"
    SHARED = "shared"


class TaskType(Enum):
    EXECUTE_FLOW = "execute_flow"
    VALIDATE_FLOW = "validate_flow"
    SET_NODE_FEATURES = "set_node_features"
    ADD_OPERATOR_CARD_DETAILS = "add_operator_card_details"
    NON_EXECUTE_FLOW = "non_execute_flow"


class DocsStructure(TypedDict):
    id: str
    name: str
    reason: str
    document_url: str


class ExtractionLanguageScripts:
    # Define all WDU scripts
    LATIN = {
        DatasiftConstants.SCRIPT_LABEL: "Latin",
        DatasiftConstants.SCRIPT_CODE: "latn",
    }
    CHINESE_JAPANESE_KOREAN = {
        DatasiftConstants.SCRIPT_LABEL: "Chinese Japanese Korean",
        DatasiftConstants.SCRIPT_CODE: "cjk",
    }
    CYRILLIC = {
        DatasiftConstants.SCRIPT_LABEL: "Cyrillic",
        DatasiftConstants.SCRIPT_CODE: "cyrl",
    }

    # Define all WDU languages
    CHINESE_SIMPLIFIED = {
        DatasiftConstants.LANGUAGE_LABEL: "Chinese - Simplified",
        DatasiftConstants.LANGUAGE_CODE: "chi_sim",
    }
    CHINESE_TRADITIONAL = {
        DatasiftConstants.LANGUAGE_LABEL: "Chinese - Traditional",
        DatasiftConstants.LANGUAGE_CODE: "chi_tra",
    }
    JAPANESE = {
        DatasiftConstants.LANGUAGE_LABEL: "Japanese",
        DatasiftConstants.LANGUAGE_CODE: "jpn",
    }
    SPANISH = {
        DatasiftConstants.LANGUAGE_LABEL: "Spanish",
        DatasiftConstants.LANGUAGE_CODE: "es",
    }
    ENGLISH = {
        DatasiftConstants.LANGUAGE_LABEL: "English",
        DatasiftConstants.LANGUAGE_CODE: "eng",
    }

    SCRIPTS = [
        CHINESE_JAPANESE_KOREAN[DatasiftConstants.SCRIPT_CODE],
        CYRILLIC[DatasiftConstants.SCRIPT_CODE],
    ]
    LANGUAGES = [ENGLISH, SPANISH, JAPANESE, CHINESE_SIMPLIFIED, CHINESE_TRADITIONAL]


class OperatorConstants:
    # Defines constants that are used across multiple operators
    # adding variable for KVP Extraction
    DATABRICKS = "Microsoft Azure Databricks"
    PRIMARY = "primary"
    ENTITY_EXTRACT = "extract_entity"
    KVP_BASE_URL = "kvp_base_url"
    INGEST_TYPE = "ingest_type"
    CATALOG_NAME = "catalog_name"
    DATASET_CONNECTION = "dataset_connection"
    CONNECTION_ID = "connection_id"
    CONNECTION_NAME = "connection_name"
    OUTPUT_CONNECTION = "output_connection"
    INTERACTION_PROPERTIES = "interaction_properties"
    DEFAULT_REDACTION_VALUE = True
    DEFAULT_REDACTION_CHARACTER_VALUE = ""
    KVP_COLUMN = "kvp_column"
    KVP_COLUMN_DEFAULT = "entity"
    DOC_COLUMN = "doc_column"
    DOC_COLUMN_DEFAULT = "content"
    DOC_ID_HASH = "doc_id_hash_column"
    DOC_ID_HASH_DEFAULT = "doc_id_hash"
    DISABLE_VALIDATION = "disable_validation"
    EMBEDDINGS_COLUMN = "embeddings_column"
    EMBEDDINGS_COLUMN_DEFAULT = "embeddings"
    EMBEDDINGS_MODEL_ID = "embeddings_model_id"
    MODEL_ID = "model_id"
    ENTITY = "entity"
    TYPE = "type"
    TYPE_INT8 = "int8"
    TYPE_INT16 = "int16"
    TYPE_INT32 = "int32"
    TYPE_INT64 = "int64"
    TYPE_FLOAT = "float"
    TYPE_DOUBLE = "double"
    TYPE_BOOL = "bool"
    TYPE_JSON = "json"
    TYPE_STRING = "string"
    TYPE_VECTOR = "vector"
    IS_PRIMARY = "is_primary"
    ID = "id"
    NAME = "name"
    VALUE = "value"
    OPERATOR = "operator"
    CONFIG = "config"
    GLOBAL_CONFIG = "global_config"
    BLOCKING_THRESHOLD = "blocking_threshold"
    CONFIGURATION = "configuration"
    SIZE = "size"
    PAGES = "pages"
    COUNT = "count"
    CREATED_TIME = "created_time"
    MODIFIED_TIME = "modified_time"
    BINARY_CONTENT = "binary_content"
    URL = "url"
    CONTENT_TYPE = "content_type"
    WDU_SERVER_KEY = "wdu_server"
    WDU_API_MAX_CONCURRENCY = "wdu_api_max_concurrency"
    BATCH_SIZE = "batch_size"
    SQL_FILTER = "sql_filter"
    SAMPLING_FILTER = "sampling_filter"
    EMBEDDINGS = "embeddings"
    ENTITY_STORE = "entity_store"
    MILVUS_FEATURE_MAPPINGS = "milvus_feature_mappings"
    MILVUS_REQUIRED_FEATURES = "milvus_required_features"
    COLLECTION_NAME = "collection_name"
    FEATURE_MAPPINGS = "feature_mappings"
    CUSTOM_COLLECTION_COLUMN_NAME = "Custom"
    NEW_COLLECTION_DEFAULT_FEATURE_MAPPINGS = "new_collection_default_feature_mappings"
    FEATURES = "features"
    VALID_COLUMNS = "valid_columns"
    AVAILABLE_FEATURES = "available_features"
    ELASTIC_FEATURE_MAPPINGS = "elastic_feature_mappings"
    OPENSEARCH_FEATURE_MAPPINGS = "opensearch_feature_mappings"
    ELASTIC_REQUIRED_FEATURES = "elastic_required_features"

    # OpenSearch/Elasticsearch connection constants
    OPENSEARCH_HOST = "opensearch_host"
    OPENSEARCH_PORT = "opensearch_port"
    OPENSEARCH_USERNAME = "opensearch_username"
    OPENSEARCH_PASSWORD = "opensearch_password"
    OPENSEARCH_USE_SSL = "opensearch_use_ssl"
    OPENSEARCH_VERIFY_CERTS = "opensearch_verify_certs"
    OPENSEARCH_AWS_AUTH = "opensearch_aws_auth"
    OPENSEARCH_AWS_REGION = "opensearch_aws_region"

    # OpenSearch index configuration constants
    INDEX_NAME = "index_name"
    DOC_ID_COLUMN = "doc_id_column"
    CREATE_INDEX = "create_index"
    INDEX_SETTINGS = "index_settings"

    # Vector configuration constants (shared across vector DBs)
    VECTOR_DIMENSION = "vector_dimension"
    PII_LIST = "pii_list"
    PII_THRESHOLD_KEY = "pii_threshold"
    PII_AND_HAP_EXTRACT_REDACT = "pii_and_hap_extract_redact"
    MODERATIONS = "moderations"
    ES = "elasticsearch"
    VECTOR_SIMILARITY_KEY = "vector_similarity"
    OPENSEARCH = "opensearch"
    MILVUS = "milvus"
    ES_CP4D = "elasticsearch_cp4d"
    INGEST = "ingest"
    CHUNKER = "chunker"
    CHUNKED_CONTENT = "chunked_content"
    CHUNK = "chunk"
    CHUNK_SIZE = "chunk_size"
    CHUNK_SIZE_DEFAULT = 4000
    CHUNK_SEQUENCE_NUMBER = "chunk_sequence_number"
    START_INDEX = "start_index"
    KVP_ICEBERG = "kvp_iceberg"
    DESCRIPTION = "description"
    ATTRIBUTES = "attributes"
    DEFAULT = "default"
    REQUIRED = "required"
    MAX_FILE_SIZE = "max_file_size"
    INPUT_ASSETS = "input_assets"
    INCLUDE_FILTER_KEY = "include_filter"
    AVAILABLE_FOR_FILTER = "available_for_filter"
    AVAILABLE_FOR_VECTOR_DB = "available_for_vector_db"
    MANDATORY_FOR_VECTOR_DB = "mandatory_for_vector_db"
    TRANSFORM = "transform"
    SHORT_NAME = "short_name"
    CATEGORY = "category"
    REDACTION_KEY = "redaction"
    PII_REDACTION_CHARACTER_KEY = "redaction_character"
    HAP_REDACTION_CHARACTER_KEY = "hap_redaction_character"
    EXPECTED_REDACTIONS = "expected_redactions"
    WNLP_SERVER_KEY = "wnlp_server"
    WNLP_API_ROUTE = "api_route"
    HAP_THRESHOLD_KEY = "hap_threshold"
    REDACTION_CHARACTER_KEY = "redaction_character"
    PII_REDACTION_KEY = "redaction"
    HAP_REDACTION_KEY = "hap_redaction"
    PII_FIELD_NAME = "pii"
    HAP_FIELD_NAME = "hap"
    REGEX_KEY = "regex"
    PARTIAL_INGEST = "partial_ingest"
    SDK = "sdk"
    DELETED = "deleted"
    CORE_OPERATORS_PATH = "core.operators"
    ALL_OPERATORS_PATH = [CORE_OPERATORS_PATH]
    SCHEMA_NAME = "schema_name"
    TABLE_NAME = "table_name"
    LANG_DETECT = "lang_detect"
    DOC_QUALITY = "doc_quality"
    DOC_ID_OPERATOR = "doc_id_hash"
    CROMA_DB = "chromadb"
    PATHS = "paths"
    PATH = "path"
    INGEST_CSV = "ingest_csv"
    INGEST_LOCAL = "ingest_local"
    INGEST_WEB_PAGES = "ingest_web_page"
    EXTRACT_DOCLING = "extract_docling"
    DOCLING_CHUNKER = "docling_chunker"
    NOOP = "noop"
    MERGE = "merge"
    REDACTION = "redaction"
    REGEX_ANNOTATOR = "regex_annotator"
    INGEST_DOCUMENT_SET = "ingest_document_set"
    SAMPLING_PERCENTAGE = "sampling_percentage"
    DOCUMENT_SET_ID = "document_set_id"
    DOCUMENT_SET = "document_set"
    DOCUMENT_SET_LABEL = "Document Set"
    DOCUMENT_SET_NAME = "document_set_name"
    DOCUMENT_SET_DESCRIPTION = "document_set_description"
    BASE_DOCUMENT_SET_TEMPLATE = "base_document_set_template"
    BASE_DOCUMENT_SET = "base_document_set"
    BASE_DOCUMENT_SET_ID = "base_document_set_id"
    DOCUMENT_LIBRARY_ID = "document_lib_id"
    ICEBERG_STORAGE = "iceberg_storage"
    COLUMN_LIST = "column_list"
    ADD_SPARSE_VECTOR = "add_sparse_vector"
    ADD_SPARSE_VECTOR_DEFAULT = True
    TYPE_VECTOR_SPARSE = "vector_sparse"
    LABEL = "label"
    REDACTION_REGEX_KEY = "redaction_regex"
    REDACTION_MASKING_CHARACTER_KEY = "redaction_masking_character"
    SPARSE_EMBEDDINGS_COLUMN_DEFAULT = "sparse_embeddings"
    DENSE_EMBEDDINGS_COLUMN_DEFAULT = "vector_embeddings"
    COMPUTE = "compute"
    STORAGE = "storage"
    DATASET_STORAGE = "dataset_storage"
    RUNTIME = "runtime"
    ACLS = "acls"
    PROPERTIES = "properties"
    DATASOURCE_TYPE = "datasource_type"
    CATALOG_TYPE = "catalog_type"
    COS_ENDPOINT = "cos_endpoint"
    COS_STORAGE_TYPE = "bmcos_object_storage"
    AWS_STORAGE_TYPE = "amazon_s3"
    DEFAULT_S3_REGION = "us-east-1"
    METADATA = "metadata"
    PIPELINE_DETAILS = "pipeline_details"
    PARAMETERS = "parameters"
    PROJECT_ID = "project_id"
    NODE_PARAMETERS = "node_parameters"
    DOCUMENT_ID = "document_id"
    LAST_MODIFIED_TIME = "last_modified_time"
    LANGUAGE = "language"
    LANGUAGE_SCORE = "language_score"
    IMAGE_PATH = "image_path"
    DOCUMENT_CLASS_ID = "document_class_id"
    DOCUMENT_CLASS = "document_class"
    FORMAT = "format"
    UNSTRUCTURED_DATA_CURATION_ID = "unstructured_data_curation_id"
    UPDATED_DOCUMENTS = "updated_documents"
    API_KEY = "api_key"  # pragma: allowlist secret
    USERNAME = "username"
    CUSTOM_SCHEMA = "custom_schema"
    ALL_SCHEMA_DETAILS = "all_schema_details"
    EXTRACT_CUSTOM_SCHEMA = "extract_schema"
    NODE_METADATA = "node_metadata"
    NODES_METADATA_FILE = "nodes_metadata.json"
    OCR_MODE = "ocr_mode"
    ENABLED = "enabled"
    DISABLED = "disabled"
    FORCED = "forced"
    EXTRACT_ACL = "extract_acl"
    ACL_OPERATOR = "acl_operator"
    IS_OPERATOR_AVAILABLE = "is_operator_available"
    IS_INTERNAL_FEATURE = "is_internal_feature"
    ALWAYS_RETRIEVE_DOCUMENT = "always_retrieve_document"
    EXTRACTION_REQUIRED_FILE_EXTENSIONS = [".pdf", ".docx", ".pptx", ".doc", ".ppt"]
    ACCEPTED_FILE_EXTENSIONS = EXTRACTION_REQUIRED_FILE_EXTENSIONS + [".md", ".txt"]
    INGEST_FILE_EXTENSIONS = ACCEPTED_FILE_EXTENSIONS + [".json"]
    PAGES_PROCESSED_COLUMN = "pages_processed"
    EXTRACT_JSON = "extract_json"
    JSON_SCHEMA = "json_schema"
    LANGUAGE_NAME_COLUMN_KEY = "lang_name"
    LANGUAGE_SCORE_COLUMN_KEY = "lang_score"
    ASSIGNED_DATA_CLASSES = "assigned_data_classes"
    ASSIGNED_BUSINESS_TERMS = "assigned_business_terms"
    ASSIGNED_CLASSIFICATIONS = "assigned_classifications"
    PROCESSING_STATE = "processing_state"
    PRESTO_READ_BATCH_SIZE = "presto_read_batch_size"
    PRESTO_INSERT_BATCH_SIZE = "presto_insert_batch_size"
    PRESTO_DELETE_BATCH_SIZE = "presto_delete_batch_size"
    ORIGINAL_PROJECT_CLIENT = "original_project_client"
    DOCUMENT_TYPE = "document_type"
    DOCUMENT_FORMAT = "document_format"
    GENERIC_KVP = "generic_kvp"
    VALID_VALUES = "valid_values"
    BRANCHING = "branching"
    FILTER_CRITERIA_LIST = "criteria_list"
    FILTER_CRITERIA_JSON = "criteria_json"
    FILTER_LOGICAL_OPERATOR_KEY = "logical_operator"
    FILTER_FEATURES_TO_DROP_KEY = "features_to_drop"
    MIN_VALUE = "min_value"
    MAX_VALUE = "max_value"
    DATA_TYPE_IDENTIFIER_KVPS_OPERATOR = "kvps_datatype_identifier_operator"
    CLASSIFICATION_OPERATOR = "classification_operator"
    ENTITY_CURATION_OPERATOR = "entity_curation_operator"
    DESIGN_FLOW_OUTPUT_OPERATOR = "design_flow_output"
    ENTITY_STORE_OPERATOR = "entity_store"
    KEY = "key"
    SEMANTIC_LABEL = "semantic_label"
    RAW_TEXT = "raw_text"
    DOCLING_DOCUMENT = "docling_document"
    TABLES = "tables"
    IMAGES = "images"
    STRUCTURED_DATA = "structured_data"
    PAGE_NO = "page_no"
    EXTRACTED_DATA = "extracted_data"
    ERRORS = "errors"
    SUCCESS = "success"
    ERROR = "error"
    EXTRACT_TABLES = "extract_tables"
    EXTRACT_IMAGES = "extract_images"
    USE_TEMPLATE = "use_template"
    TEMPLATE = "template"
    EXPAND_EXTRACTED_DATA = "expand_extracted_data"
    MESSAGE = "message"
    STATUS = "status"
    VALUE_DATA_TYPE = "value_data_type"
    KEY_VALUE = "key_value"
    NORMALIZED_VALUE = "normalized_value"
    JSON_IDENTIFIER = "json_identifier"
    USER_DEFINED_CONTENT_COLUMN = "user_defined_content_column"
    JSON_CONTENT = "json_content"
    INPUT_FEATURES = "input_features"
    OUTPUT_FEATURES = "output_features"
    USER_CODE = "user_code"
    PYTHON_CODE_KEY = "python_code"
    CODE_TIMEOUT_KEY = "code_timeout"
    NEW_COLUMNS = "selected_python_features"
    ORIGINAL_FEATURE = "original_feature"
    LINK_ID = "link_id"
    LINK_NAME = "link_name"
    LINK_CONDITIONS = "link_conditions"
    FEATURE_NAME = "feature_name"
    MAPPED_COLUMN_NAME = "mapped_column_name"
    TRANSFORMED_ENTITIES_COLUMN_NAME = "transformed_entities"
    MERGE_OPTION = "merge_option"
    VECTOR_DB_NAME = "vector_db_name"
    ROWS = "rows"
    COLUMNS = "columns"
    INNER_JOIN_DUPLICATE_COLUMN = "inner_join"
    FULL_OUTER_JOIN = "full_outer"
    MERGE_TYPE = "merge_type"
    COLUMN_OPTION = "column_option"
    MODEL_NAME = "model_name"
    PAGE_IMAGES = "page_images"
    DEFAULT_MAX_THREADS = 25
    DEFAULT_WXAI_API_MAX_WAIT_TIME = 3600
    FILTER_UNKNOWN_LANGUAGE = "filter_unknown_language"
    OLD_FEATURE = "old_feature"
    NEW_FEATURE = "new_feature"
    TAGS = "tags"
    INTERNAL_FEATURE = "internal_feature"
    MANDATORY = "mandatory"
    SELECTED_PYTHON_FEATURES = "selected_python_features"
    AVAILABLE_INDICES = "available_indices"
    IS_DATASIFT_SUPPORTED_COLLECTION = "is_datasift_supported_collection"
    IS_DATASIFT_SUPPORTED_INDEX = "is_datasift_supported_index"
    SUPPORTED = "supported"
    REASON = "reason"
    AVAILABLE_COLLECTIONS = "available_collections"
    INDEX_MAPPINGS = "index_mappings"
    COLLECTION_COLUMNS = "collection_columns"
    STORED_INDEX_METADATA = "stored_index_metadata"
    TARGET_STORE = "target_store"
    ASSET_TYPE = "asset_type"
    DOCUMENTS = "documents"
    HREF = "href"
    CONNECTION_PATH = "connection_path"
    ATTACHMENTS = "attachments"
    COMPUTE_EMBEDDINGS = "compute_embeddings"
    TOTAL_PAGES_PROCESSED = "total_pages_converted"
    ENTITY_IDS_COLUMN_NAME = "entity_ids"
    DATABASE_TABLES_COLUMN_NAME = "database_tables"
    ENTITIES = "entities"
    USER_DATA = "user_data"
    RESOURCE_KEY = "resource_key"
    METRIC_TYPE = "metric_type"
    INDEX_TYPE = "index_type"
    INDEX_NAME = "index_name"
    SEMANTIC_CONFIG = "semantic_config"
    ENTITLEMENTS = "entitlements"
    INPUT_LINKS = "input_links"
    MAX_BATCH_SIZE_MB = "max_batch_size_mb"
    ENABLE_DATABRICKS = "enable_databricks"
    MARKED_UNSTRUCTURED_STATUS = "marked_unstructured_status"
    TOTAL_FILE_COUNT = "file_count"
    NODE_IDS = "node_ids"
    MAX_CONCURRENT_DELETIONS = 10
    HEARTBEAT_EMBEDDINGS_PUBLISH_SIZE = "embeddings_publish_compute_size"
    DEFAULT_FEATURE_MAPPINGS = "default_feature_mappings"
    CREATE_EMBEDDED_IMAGES = "create_embedded_images"
    ENABLED_TEXT = "enabled_text"
    LANGUAGES = "languages"  # Extration parameter
    MAX_WORKERS = "max_workers"
    USE_PROCESSES = "use_processes"

    # Docling extraction constants
    EXTRACTED_DATA = "extracted_data"
    STRUCTURED_DATA = "structured_data"
    ERROR = "error"
    TABLES = "tables"
    IMAGES = "images"
    TEMPLATE = "template"
    PAGE_NO = "page_no"
    ERRORS = "errors"
    EXTRACT_TABLES = "extract_tables"
    EXTRACT_IMAGES = "extract_images"
    USE_TEMPLATE = "use_template"
    EXPAND_EXTRACTED_DATA = "expand_extracted_data"
    DOCLING_DOCUMENT = "docling_document"
    SUCCESS = "success"
    STATUS = "status"
    MESSAGE = "message"


class OrchestratorType:
    PYTHON = "python"
    SPARK = "spark"
    CMDLINE = "cmdLine"


class Kvp:
    KVP_SERVER = "kvp_server"
    SEMANTIC_LABEL = "semantic_label"
    KEY = "key"
    VALUE = "value"
    RAW_TEXT = "raw_text"
    TABLE_NAME = "table_name"
    TABLE_ROW_INDEX = "table_row_index"


class DataSourceType:
    AMAZON_S3 = "Amazon S3"
    BOX = "Box"
    DATA_ASSET = "data_asset"
    FILENET = "AppConnectAdapter - FileNet"
    SHAREPOINT = "AppConnectAdapter - MsSharePoint"
    WXD_PRESTO = "IBM watsonx.data Presto"
    ICEBERG_METASTORE = "Iceberg metastore"
    SLACK = "Slack"
    CONFLUENCE = "Confluence"
    IBM_COS = "IBM Cloud Object Storage"


class ExtractionRequestTypes:
    ENTITY = "entity"
    TEXT = "text"
    TEXT_ENTITY = "text_entity"


class TextExtractionStatus:
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RUNNING = "running"


class ExecutionStatus(str, Enum):
    QUEUED = "Queued"
    STARTING = "Starting"
    RUNNING = "Running"
    PAUSED = "Paused"
    RESUMING = "Resuming"
    CANCELING = "Canceling"
    CANCELED = "Canceled"
    FAILED = "Failed"
    COMPLETED = "Completed"
    COMPLETED_WITH_ERRORS = "CompletedWithErrors"
    COMPLETED_WITH_WARNINGS = "CompletedWithWarnings"
    SKIPPED = "Skipped"


# efficient membership checks (O(1) instead of O(n))
COMPLETED_JOB_STATUSES = frozenset(
    [
        ExecutionStatus.COMPLETED,
        ExecutionStatus.COMPLETED_WITH_ERRORS,
        ExecutionStatus.COMPLETED_WITH_WARNINGS,
        ExecutionStatus.CANCELED,
        ExecutionStatus.FAILED,
    ]
)

active_states = [
    ExecutionStatus.STARTING,
    ExecutionStatus.RUNNING,
    ExecutionStatus.RESUMING,
    ExecutionStatus.CANCELING,
]


class ValidationStatus(str, Enum):
    FAILED = "FAILED"
    SUCCEEDED = "SUCCEEDED"
    SUCCEEDED_WITH_WARNINGS = "SUCCEEDED_WITH_WARNINGS"


class DocumentClassKeys:
    # Top level keys
    SCHEMA = "document_class_schema"
    DOCUMENT = "document"
    TARGET_TABLES = "target_tables"

    # Table keys
    TABLE_NAME = "name"
    TABLE_DESCRIPTION = "description"
    COLUMNS = "columns"

    # Column keys
    COLUMN_NAME = "name"
    COLUMN_TYPE = "type"
    COLUMN_DESCRIPTION = "description"
    SOURCE = "source"

    # Transform keys
    TRANSFORM = "transform"
    TRANSFORM_NAME = "transform_name"
    ARGUMENTS = "arguments"

    # Argument keys
    ARG_NAME = "name"
    ARG_VALUE = "value"
    FIELD = "field"


class AttributeDataTypes:
    BOOLEAN = "boolean"
    CRN = "crn"
    DATE = "date"
    DOUBLE = "double"
    FLOAT = "sfloat"
    ENUM = "enum"
    INTEGER = "int64"
    JSON = "json"
    LIST = "list"
    STRING = "string"
    TIME = "time"
    TIMESTAMP = "timestamp"


class LlmModelName(str, Enum):
    OPENAI = "openai"
    WATSONX = "watsonx"
    LLAMA_2 = "llama2"
    MISTRAL = "mistral"
    GEMMA = "gemma"
    CODELLAMA = "codellama"
    PHI = "phi"
    NEURAL_CHAT = "neural-chat"
    FALCON = "falcon"
    OPENHERMES = "openhermes"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    MIXTRAL = "mixtral"
    GRANITE_3_2_2B = "granite3.2:2b"
    GRANITE_3_2_8B = "granite3.2:8b"


class IcebergCatalogType:
    DYNAMODB = "dynamodb"
    GLUE = "glue"
    HIVE = "hive"
    MEMORY = "memory"
    NOOP = "noop"
    WXD_REST = "wxd_rest"
    REST = "rest"
    SQL = "sql"


class CatalogType:
    """Supported catalog types"""

    ICEBERG = "iceberg"
    SNOWFLAKE = "snowflake"
    JDBC = "jdbc"
    NESSIE = "nessie"


class ElasticSearchDataTypes:
    TEXT = "text"
    BYTE = "byte"
    SHORT = "short"
    INTEGER = "integer"
    LONG = "long"
    DENSE_VECTOR = "dense_vector"
    SPARSE_VECTOR = "sparse_vector"
    BOOLEAN = "boolean"
    FLOAT = "float"
    DOUBLE = "double"
    OBJECT = "object"


class MemoryLogPhases:
    START = "Start"
    TRANSFORM_COMPLETED = "Transform Completed"


class ProcessingMessageConstants:
    DOCS_PROCESSED = "documents processed."
    MORE_DOCS_TO_PROCESS = "There are more documents to process. Run again to process."


class LiteralConstants:
    NEWLINE: str = "\n"
    SPACE: str = " "
