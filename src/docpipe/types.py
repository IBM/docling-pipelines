"""Shared type aliases for docpipe.

Import these instead of repeating verbose annotations across operators and
orchestration modules.

Usage:
    from docpipe.types import FlowConfig, OperatorConfig, OperatorMetadata, PyArrowTable
"""

from typing import Any

import pyarrow as pa

# A PyArrow table — the data contract between all operators.
PyArrowTable = pa.Table

# Operator configuration dict passed to AbstractOperator.__init__.
OperatorConfig = dict[str, Any]

# Flow-level global_config dict (and runtime params merged into it).
FlowConfig = dict[str, Any]

# Return type of AbstractOperator.get_metadata() and similar registry dicts.
OperatorMetadata = dict[str, Any]

# Metadata dict returned by AbstractOperator.transform() and create_base_metadata().
# Contains keys like total_docs, processed_docs, failed_docs, skipped_docs, node_status.
OperatorOutputMetadata = dict[str, Any]

# Standard transform return type: (output tables, execution metadata).
TransformResult = tuple[list[pa.Table], OperatorOutputMetadata]
