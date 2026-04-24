import os
from enum import Enum, StrEnum
from pathlib import Path
from typing import TypedDict

# Import OperatorConstants for re-export


def _find_project_root() -> Path:
    """Find project root by searching upward for marker files.

    Prioritizes .git directory as the most reliable indicator of project root,
    since pyproject.toml may exist in subdirectories (like backend/).
    """
    current = Path(__file__).resolve()

    # Search upward for marker files - prioritize .git as it's at true project root
    for parent in [current, *list(current.parents)]:
        # .git is the most reliable indicator of project root
        if (parent / ".git").exists():
            return parent

    # Fallback: look for README.md or other root-level files
    for parent in [current, *list(current.parents)]:
        if (parent / "README.md").exists() and (parent / "src").exists():
            return parent

    # Last resort: use fixed parent count
    # constants.py -> common -> backend -> datasift_opensource -> src -> project_root
    return Path(__file__).resolve().parents[5]


class DatasiftConstants:
    # Defines constants that are used across Datasift service
    INPUT_EDGES = "input_edges"
    OUTPUT_EDGES = "output_edges"
    INPUT = "input"
    LOGGER_NAME = "DATASIFT"
    SESSION_INFO = "session_info"
    CONTEXT_ID = "context_id"
    FORCE_INGEST = "force_ingest"
    RETAIN_DELETED_DOCS = "retain_deleted_docs"
    RETAIN_DELETED_DOCS_DEFAULT = True
    DATA_FOLDER = "data_folder"
    OPERAND_NAMESPACE = "OPERAND_NAMESPACE"
    DAG = "dag"
    DESCRIPTION = "description"
    FLOW = "flow"
    FLOW_ID = "flow_id"
    FLOW_NAME = "flow_name"
    FIELD_NAME = "field_name"
    FLOW_DESCRIPTION = "flow_description"
    FLOW_DEFINITION = "flow_definition"
    JOB = "job"
    JOB_ID = "job_id"
    NODE_ID = "node_id"
    NODE_NAME = "node_name"
    JOB_RUN = "job_run"
    JOB_RUN_ID = "job_run_id"
    TRACK_PERF = "track_perf"
    DATASIFT = "datasift"
    METADATA = "metadata"
    TRACE_MEMORY_ALLOCATIONS = "TRACE_MEMORY_ALLOCATIONS"
    METRICS = "metrics"
    DEFAULT_TRANSACTION_ID = "TRANSACTION999"
    UDP_LOGS = "UDP_logs"
    INCREMENTAL_PROCESSING_METADATA_PATH = "inc_process_metadata"
    JOBS_STATS_PATH = "job-stats"
    NODE_STATS_PATH = "node-stats"
    TRANSACTION_ID = "transaction_id"
    OUTPUT_FOLDER = "output_folder"
    OUTPUT_FEATURES_TO_DROP = "output_features_to_drop"
    LINK_NAME = "link_name"
    UPDATED_FEATURES = "updated_features"
    NAME = "name"
    UNNAMED_FLOW = "Unnamed flow"
    UUID = "uuid"
    STATUS = "status"
    STATE = "state"
    MESSAGE = "message"
    LAST_UPDATED_AT = "last_updated_at"
    DETAILS = "details"
    JOBS = "jobs"
    RUNS = "runs"
    OPERATORS = "operators"
    DOCUMENTS = "documents"
    # Use absolute path based on this file's location to work from anywhere
    DOCUMENT_CLASSES_PATH = str(Path(__file__).parent.parent / "document_classes")
    OPERATOR_FILE = "operator_file"
    SUMMARY = "summary"
    VALIDATION_FAILED = "validation_failed"
    PYTHON_PATH = "PYTHONPATH"
    LOCAL = "local"
    TRUE = "True"
    ABSTRACT_OPERATOR = "AbstractOperator"
    VALIDATING_FLOW = "validating_flow"
    SKIP_CUSTOM_OP_VALIDATION = "skip_custom_op_validation"
    SUCCESS = "success"
    TMP = "tmp"
    ENABLE_MICRO_BATCHING = "enable_micro_batching"
    MICRO_BATCH_SIZE = "micro_batch_size"
    DEFAULT_MICRO_BATCH_SIZE = 100
    BATCH_NUM = "batch_num"
    BATCH_COUNT = "batch_count"
    INGEST_NODE_ID = "ingest_node_id"
    # Batch-level concurrency control
    MAX_CONCURRENT_BATCHES = "max_concurrent_batches"
    DEFAULT_MAX_CONCURRENT_BATCHES = 10
    BUILD_VERSION = "BUILD_VERSION"
    PARQUET_BATCH_SIZE = 1000
    LANGUAGE_LABEL = "language_label"
    LANGUAGE_CODE = "language_code"
    SCRIPT_CODE = "script_code"
    SCRIPT_LABEL = "script_label"
    ENABLE_SUMMARIZATION_KEY = "enable_summarization"
    SUMMARY_MODEL_ID_KEY = "summarization_model_id"
    MAX_INPUT_TOKENS_DEFAULT = 8000
    OVERLAP_RATIO_DEFAULT = 0.2
    SUMMARY_SENTENCES_DEFAULT = 2
    SUMMARY_MAX_WORDS_DEFAULT = 20
    SUMMARY_MODEL_ID_DEFAULT = "granite4"
    FLOW_EXECUTION_EVENT_HANDLER = "flow_execution_event_handler"
    JOB_LOG_PATH = "job_log_path"
    FLOW_EXECUTE_LOG = "flow_execute.log"

    # Use absolute path to ensure consistency across different working directories
    # Find project root by searching for marker files (pyproject.toml, .git)
    _PROJECT_ROOT = _find_project_root()
    DOCUMENT_SET_DEFAULT_DB_PATH = str(_PROJECT_ROOT / "data" / "duckdb" / "document_sets.duckdb")


class ServiceConstants:
    """Constants for external service configurations"""

    # Ollama service configuration
    DEFAULT_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


class DoclingClientConstants:
    """Constants for Docling Serve client retry logic"""

    # Retry configuration for 404 errors during polling
    # These handle pod restarts, HPA scaling, and load balancer routing issues
    STATUS_404_MAX_RETRIES = 3
    STATUS_404_BACKOFF_BASE = 1.0  # seconds


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
        ERROR = "error"

    class Internal:
        DELETED_FROM_LAST_RUN = "deleted_from_last_run"
        ALL_DOC_IDS = "all_doc_ids"
        BRANCHES = "branches"

    # Metrics that require atomic aggregation to prevent race conditions
    AGGREGATION_METRICS = frozenset({External.TOTAL_PAGES_CONVERTED, External.DELETED_DOC_COUNT})


# Internal metrics used in multiple places so making it as a global variable
internal_metrics = {value for name, value in vars(Metrics.Internal).items() if not name.startswith("__")}


class TaskType(Enum):
    EXECUTE_FLOW = "execute_flow"
    VALIDATE_FLOW = "validate_flow"
    NON_EXECUTE_FLOW = "non_execute_flow"


class DocumentConstants:
    """
    Consolidated document-related constants.
    Merged from DocumentClassKeys and DocsStructure.
    """

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

    # Document structure type (from DocsStructure TypedDict)
    class Structure(TypedDict):
        """Document structure definition"""

        id: str
        name: str
        reason: str
        document_url: str


class OrchestratorType:
    PYTHON = "python"
    SPARK = "spark"


class DataSourceType:
    AMAZON_S3 = "Amazon S3"
    BOX = "Box"
    FILENET = "AppConnectAdapter - FileNet"
    SHAREPOINT = "AppConnectAdapter - MsSharePoint"
    WXD_PRESTO = "IBM watsonx.data Presto"
    ICEBERG_METASTORE = "Iceberg metastore"
    SLACK = "Slack"
    CONFLUENCE = "Confluence"
    IBM_COS = "IBM Cloud Object Storage"


class ExecutionStatus(StrEnum):
    QUEUED = "Queued"
    STARTING = "Starting"
    RUNNING = "Running"
    PAUSED = "Paused"
    RESUMING = "Resuming"
    CANCELING = "Canceling"
    CANCELED = "Canceled"
    FAILING = "Failing"
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


class ValidationStatus(StrEnum):
    FAILED = "FAILED"
    SUCCEEDED = "SUCCEEDED"
    SUCCEEDED_WITH_WARNINGS = "SUCCEEDED_WITH_WARNINGS"


class DataTypes:
    """
    Data type constants for attributes.
    Renamed from AttributeDataTypes for brevity.
    """

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


class LLMConstants:
    """
    Consolidated LLM-related constants.
    Includes model names and catalog types.
    """

    class Models(StrEnum):
        """Supported LLM model names"""

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

    class CatalogTypes:
        """Supported catalog types"""

        ICEBERG = "iceberg"
        SNOWFLAKE = "snowflake"
        JDBC = "jdbc"
        NESSIE = "nessie"


class ProcessingConstants:
    """
    Consolidated processing-related constants.
    Merged from MemoryLogPhases, ProcessingMessageConstants, and LiteralConstants.
    """

    # Memory log phases
    MEMORY_LOG_START = "Start"
    MEMORY_LOG_TRANSFORM_COMPLETED = "Transform Completed"

    # Processing messages
    DOCS_PROCESSED = "documents processed."
    MORE_DOCS_TO_PROCESS = "There are more documents to process. Run again to process."

    # Literal constants
    NEWLINE: str = "\n"
    SPACE: str = " "


# ============================================================================
# Backward Compatibility Aliases
# ============================================================================
# These aliases maintain backward compatibility with code using old class names.
# New code should use the consolidated classes above.

# DocumentClassKeys -> DocumentConstants
DocumentClassKeys = DocumentConstants

# DocsStructure -> DocumentConstants.Structure
DocsStructure = DocumentConstants.Structure

# AttributeDataTypes -> DataTypes
AttributeDataTypes = DataTypes

# LlmModelName -> LLMConstants.Models
LlmModelName = LLMConstants.Models

# CatalogType -> LLMConstants.CatalogTypes
CatalogType = LLMConstants.CatalogTypes


# MemoryLogPhases constants -> ProcessingConstants
class MemoryLogPhases:
    """Backward compatibility wrapper for ProcessingConstants memory log phases"""

    START = ProcessingConstants.MEMORY_LOG_START
    TRANSFORM_COMPLETED = ProcessingConstants.MEMORY_LOG_TRANSFORM_COMPLETED


# ProcessingMessageConstants -> ProcessingConstants
class ProcessingMessageConstants:
    """Backward compatibility wrapper for ProcessingConstants messages"""

    DOCS_PROCESSED = ProcessingConstants.DOCS_PROCESSED
    MORE_DOCS_TO_PROCESS = ProcessingConstants.MORE_DOCS_TO_PROCESS


# LiteralConstants -> ProcessingConstants
class LiteralConstants:
    """Backward compatibility wrapper for ProcessingConstants literals"""

    NEWLINE: str = ProcessingConstants.NEWLINE
    SPACE: str = ProcessingConstants.SPACE
