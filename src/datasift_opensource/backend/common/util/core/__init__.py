"""Core utility functions for collections, strings, validation, patterns, and datetime operations."""

from .collections import (
    batch_list,
    get_index,
    get_list_from_map,
    get_map_from_map,
    lowercase_keys,
    process_in_batches,
)
from .datetime import get_current_timestamp
from .patterns import Singleton
from .strings import (
    escape_query_value,
    get_truncated_text,
    is_null_or_empty,
    split_text_into_chunks,
)
from .validation import (
    deduplicate_tags,
    is_date_time_as_per_format,
    is_value_in_range,
    to_bool,
    validate_container_kind,
    validate_flow_definition,
    validate_uuid_format,
)

__all__ = [
    "Singleton",
    "batch_list",
    "deduplicate_tags",
    "escape_query_value",
    "get_current_timestamp",
    "get_index",
    "get_list_from_map",
    "get_map_from_map",
    "get_truncated_text",
    # Validation
    "is_date_time_as_per_format",
    "is_null_or_empty",
    "is_value_in_range",
    "lowercase_keys",
    "process_in_batches",
    "split_text_into_chunks",
    "to_bool",
    "validate_container_kind",
    "validate_flow_definition",
    "validate_uuid_format",
]
