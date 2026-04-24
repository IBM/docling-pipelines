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
from common.util.data.transform import TransformUtils
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

__all__ = [
    # Data utilities
    "BaseParquetTableHandler",
    "CpdParquetTableHandler",
    "IncrementalUpdateUtil",
    "LRUCache",
    "Singleton",
    "TransformUtils",
    # Orchestration utilities
    "add_validation_alert",
    # Core utilities
    "batch_list",
    "clean_up_prefect_home",
    "cleanup_pyarrow_buffers",
    "combine_cumulative_deleted_rows",
    "create_log_folders",
    "create_node_id_to_index_map",
    "delete_folders",
    "display_operator_summary",
    "format_node_stats",
    # Operator utilities
    "format_operator_details",
    "format_operator_logs",
    "get_current_timestamp",
    "get_data_path",
    "get_env_bool",
    "get_env_int",
    "get_env_var",
    # Infrastructure utilities
    "get_logger",
    "get_opensearch_config",
    "get_parquet_table_handler",
    "get_process_memory_mb",
    "get_pyarrow_table_size_mb",
    "get_truncated_text",
    "is_date_time_as_per_format",
    "is_value_in_range",
    "list_operators",
    "log_elapsed_time",
    "log_memory_usage",
    "process_batches_in_parallel",
    "process_in_batches",
    "retrieve_node_specific_operator_logs",
    "retrieve_operator_logs",
    "retrieve_operators_sequence",
    "retry_with_exponential_backoff",
    "run_with_session_info",
    "set_prefect_env_variables",
    "split_text_into_chunks",
    "submit_task_with_context_propagation",
    "to_bool",
    "update_deleted_rows",
    "write_job_logs",
]
