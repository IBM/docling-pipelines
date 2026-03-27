"""
Datasift utility functions organized by domain.
"""

# Core utilities - Pure Python functions
from common.util.core.collections import batch_list, process_in_batches
from common.util.core.datetime import get_current_timestamp
from common.util.core.patterns import Singleton
from common.util.core.strings import get_truncated_text, split_text_into_chunks
from common.util.core.validation import is_date_time_as_per_format, is_value_in_range, to_bool
from common.util.data.incremental_update import IncrementalUpdateUtil

# Data utilities
from common.util.data.pyarrow_handler import (
    BaseParquetTableHandler,
    CpdParquetTableHandler,
    get_parquet_table_handler,
)
from common.util.data.transform import HAS_TRANSFORM_UTILS, TransformUtils
from common.util.infrastructure.caching import LRUCache
from common.util.infrastructure.concurrency import (
    process_batches_in_parallel,
    run_with_session_info,
    submit_task_with_context_propagation,
)
from common.util.infrastructure.config import get_env_bool, get_env_int, get_env_var, get_opensearch_config
from common.util.infrastructure.filesystem import delete_folders, get_data_path

# Infrastructure utilities
from common.util.infrastructure.logging import get_logger
from common.util.infrastructure.performance import (
    cleanup_pyarrow_buffers,
    get_process_memory_mb,
    get_pyarrow_table_size_mb,
    log_elapsed_time,
    log_memory_usage,
)
from common.util.infrastructure.retry import retry_with_exponential_backoff
from common.util.operators.display import (
    display_operator_summary,
    format_operator_details,
    list_operators,
)
from common.util.operators.logging import (
    format_node_stats,
    format_operator_logs,
    retrieve_node_specific_operator_logs,
    retrieve_operator_logs,
    retrieve_operators_sequence,
)
from common.util.orchestration.deleted_rows_tracker import (
    combine_cumulative_deleted_rows,
    update_deleted_rows,
)

# Orchestration utilities
from common.util.orchestration.flow_utils import (
    add_validation_alert,
    create_log_folders,
    create_node_id_to_index_map,
    write_job_logs,
)
from common.util.orchestration.prefect_config import clean_up_prefect_home, set_prefect_env_variables

# Operator utilities
from core.operators.operator_metadata import OperatorMetadata

__all__ = [
    # Core utilities
    "batch_list",
    "process_in_batches",
    "get_truncated_text",
    "split_text_into_chunks",
    "to_bool",
    "is_value_in_range",
    "is_date_time_as_per_format",
    "get_current_timestamp",
    "Singleton",
    # Infrastructure utilities
    "get_logger",
    "get_opensearch_config",
    "get_env_var",
    "get_env_bool",
    "get_env_int",
    "get_data_path",
    "delete_folders",
    "process_batches_in_parallel",
    "run_with_session_info",
    "submit_task_with_context_propagation",
    "log_elapsed_time",
    "get_pyarrow_table_size_mb",
    "get_process_memory_mb",
    "log_memory_usage",
    "cleanup_pyarrow_buffers",
    "retry_with_exponential_backoff",
    "LRUCache",
    # Data utilities
    "BaseParquetTableHandler",
    "CpdParquetTableHandler",
    "get_parquet_table_handler",
    "TransformUtils",
    "HAS_TRANSFORM_UTILS",
    "IncrementalUpdateUtil",
    # Orchestration utilities
    "add_validation_alert",
    "create_node_id_to_index_map",
    "create_log_folders",
    "write_job_logs",
    "set_prefect_env_variables",
    "clean_up_prefect_home",
    "combine_cumulative_deleted_rows",
    "update_deleted_rows",
    # Operator utilities
    "OperatorMetadata",
    "format_operator_details",
    "display_operator_summary",
    "list_operators",
    "retrieve_operator_logs",
    "retrieve_node_specific_operator_logs",
    "retrieve_operators_sequence",
    "format_node_stats",
    "format_operator_logs",
]

# Made with Bob
