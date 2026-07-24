"""Flow execution reporter for clean, user-friendly console output.

This module provides reporting for flow execution using the logging system
at INFO level. Users can control visibility via DS_LOG_LEVEL environment variable.
"""

from datetime import datetime
from typing import Any, ClassVar

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.job_management.domain.models.job_stats import JobStats
from docpipe.core.job_management.domain.models.node_stats import NodeStats
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class FlowExecutionReporter:
    """Reports on flow execution progress and results to console.

    Uses logger.info() for all output, providing clean, structured summaries
    of flow execution progress and results. Output visibility is controlled
    via DS_LOG_LEVEL environment variable (INFO level or lower shows summaries).

    Uses PyArrow tables as the source of truth for schema information and
    document name lookups.
    """

    # Fields already shown in header or schema section
    _STANDARD_FIELDS: ClassVar[set[str]] = {
        "total_docs_count",
        "processed_docs",
        "failed_docs_count",
        "skipped_docs_count",
        "node_status",
        "enrichment_columns",
        "columns_added",
        "new_columns",
        "output_columns",
        "added_columns",
    }

    def __init__(self) -> None:
        """Initialize the flow output formatter."""
        self._flow_start_time: datetime | None = None
        self._current_tables: list | None = None
        self._previous_tables: list | None = None

    def print_flow_header(self, *, flow_name: str, operator_count: int) -> None:
        """Print flow execution start banner.

        Args:
            flow_name: Name of the flow being executed
            operator_count: Number of operators in the flow
        """
        self._flow_start_time = datetime.now()
        logger.info("")
        logger.info("=" * 80)
        logger.info(f" FLOW: {flow_name}")
        logger.info(f" Operators: {operator_count}")
        logger.info(f" Started: {self._flow_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)
        logger.info("")

    def print_operator_start(self, *, step_name: str, operator_type: str) -> None:
        """Print operator execution start message.

        Args:
            step_name: Name/ID of the operator step
            operator_type: Type of operator (e.g., 'extract_operator', 'embeddings')
        """
        logger.info(f"[{step_name}] Starting {operator_type}...")

    def print_operator_summary(self, *, step_name: str, node_stats: NodeStats, tables=None) -> None:
        """Print operator execution summary card.

        Args:
            step_name: Name/ID of the operator step
            node_stats: Statistics for the completed operator
            tables: Optional list of PyArrow tables for enhanced display (e.g., document name lookup)
        """
        # Store current tables and update previous for next iteration
        self._current_tables = tables
        status = node_stats.node_status
        duration_str = self._format_duration(node_stats.time_taken)

        # Calculate counts
        completed_count = len(node_stats.docs_completed)
        failed_count = len(node_stats.failed_docs)
        skipped_count = len(node_stats.skipped_docs)

        logger.info("")
        logger.info("=" * 80)
        logger.info(f" {step_name} ({status})")
        logger.info("=" * 80)
        logger.info(
            f" Duration: {duration_str} | Documents: {completed_count} processed, {failed_count} failed, {skipped_count} skipped"
        )

        # Print schema information if available
        if node_stats.col_names:
            self._print_schema_info(col_names=node_stats.col_names, step_name=step_name)

        # Print operator-specific metadata if available
        if node_stats.node_metadata:
            self._print_operator_metadata(node_stats.node_metadata)

        logger.info("=" * 80)
        logger.info("")

        # Save current tables as previous for next operator
        self._previous_tables = self._current_tables

    def _format_duration(self, time_taken: int | float | None) -> str:
        """Format duration for display.

        Args:
            time_taken: Time in seconds

        Returns:
            Formatted duration string
        """
        if not time_taken or time_taken < 1:
            return "< 1s"
        return f"{float(time_taken):.2f}s"

    def _print_schema_info(self, *, col_names: list[str], step_name: str) -> None:  # NOSONAR python:S3776
        """Print schema/column information in a user-friendly format.

        Args:
            col_names: List of column names in the table
            step_name: Name of the operator step (for context)
        """
        if not col_names:
            return

        # Get new columns added by this operator
        new_columns = self._get_new_columns(col_names=col_names)
        # Get removed columns (columns that were in previous but not in current)
        removed_columns = self._get_removed_columns(col_names=col_names)
        existing_columns = [col for col in col_names if col not in new_columns]

        total_cols = len(col_names)
        new_cols_count = len(new_columns)
        removed_cols_count = len(removed_columns)

        logger.info("")
        # Build the header message based on what changed
        if new_cols_count > 0 and removed_cols_count > 0:
            logger.info(
                f" Data Columns: {total_cols} total ({new_cols_count} added, {removed_cols_count} removed by this operator)"
            )
        elif new_cols_count > 0:
            logger.info(f" Data Columns: {total_cols} total ({new_cols_count} added by this operator)")
        elif removed_cols_count > 0:
            logger.info(f" Data Columns: {total_cols} total ({removed_cols_count} removed by this operator)")
        else:
            logger.info(f" Data Columns: {total_cols} total")

        # Show new columns with appropriate formatting
        if new_columns:
            logger.info(f"   Added ({new_cols_count}):")
            self._print_column_list(new_columns)

            # Add spacing before removed/existing columns
            if removed_columns or existing_columns:
                logger.info("")

        # Show removed columns with appropriate formatting
        if removed_columns:
            logger.info(f"   Removed ({removed_cols_count}):")
            self._print_column_list(removed_columns)

            # Add spacing before existing columns
            if existing_columns:
                logger.info("")

        # Show existing columns if any
        if existing_columns:
            logger.info(f"   Existing ({len(existing_columns)}): {', '.join(existing_columns[:10])}")
            if len(existing_columns) > 10:
                logger.info(f"      ... and {len(existing_columns) - 10} more")

        if not new_columns and not removed_columns and not existing_columns:
            # No columns at all (shouldn't happen, but handle gracefully)
            logger.info("   (no columns)")

    def _print_column_list(self, columns: list[str], *, indent: str = "     ") -> None:
        """Print a list of columns with appropriate formatting based on count.

        Args:
            columns: List of column names to print
            indent: Indentation string for each line
        """
        col_count = len(columns)
        if col_count <= 10:
            # Simple comma-separated list
            logger.info(f"{indent}{', '.join(columns)}")
        elif col_count <= 20:
            # Wrapped list without grouping
            self._print_wrapped_columns(columns, indent=indent)
        else:
            # Many columns: group by prefix
            self._print_grouped_columns(columns, indent=indent)

    def _get_new_columns(self, *, col_names: list[str]) -> list[str]:
        """Get list of new columns added by this operator.

        Uses PyArrow tables as the source of truth for schema changes.

        Args:
            col_names: Current column names

        Returns:
            List of new column names
        """
        # Use PyArrow tables to get actual schema changes
        if self._previous_tables and self._current_tables:
            try:
                prev_cols = self._extract_column_names(self._previous_tables)
                curr_cols = self._extract_column_names(self._current_tables)

                # New columns are those in current but not in previous
                if curr_cols:
                    return list(curr_cols - prev_cols)
            except Exception:
                # If table comparison fails, return empty list
                pass

        # First operator or no tables: all columns are "new"
        return col_names

    def _get_removed_columns(self, *, col_names: list[str]) -> list[str]:
        """Get list of columns removed by this operator.

        Uses PyArrow tables as the source of truth for schema changes.

        Args:
            col_names: Current column names

        Returns:
            List of removed column names
        """
        # Use PyArrow tables to get actual schema changes
        if self._previous_tables and self._current_tables:
            try:
                prev_cols = self._extract_column_names(self._previous_tables)
                curr_cols = self._extract_column_names(self._current_tables)

                # Removed columns are those in previous but not in current
                if prev_cols:
                    return list(prev_cols - curr_cols)
            except Exception:
                # If table comparison fails, return empty list
                pass

        # First operator or no previous tables: no columns removed
        return []

    def _extract_column_names(self, tables: list) -> set[str]:
        """Extract all column names from a list of PyArrow tables.

        Args:
            tables: List of PyArrow tables

        Returns:
            Set of column names
        """
        columns = set()
        for table in tables:
            if table is not None and hasattr(table, "column_names"):
                columns.update(table.column_names)
        return columns

    def _print_wrapped_columns(self, columns: list[str], *, indent: str = "   ") -> None:
        """Print columns wrapped at ~70 characters per line.

        Args:
            columns: List of column names
            indent: Indentation string for each line
        """
        current_line = indent
        for i, col in enumerate(columns):
            # Check if adding this column would exceed line length
            test_line = current_line + col + (", " if i < len(columns) - 1 else "")
            if len(test_line) > 70 and current_line != indent:
                # Print current line and start new one
                logger.info(current_line.rstrip(", "))
                current_line = indent + col
            else:
                current_line += col

            if i < len(columns) - 1:
                current_line += ", "

        # Print final line
        if current_line != indent:
            logger.info(current_line)

    def _print_grouped_columns(self, columns: list[str], *, indent: str = "   ") -> None:
        """Print columns grouped by common prefix.

        Args:
            columns: List of column names
            indent: Indentation string for each line
        """
        groups = self._group_columns_by_prefix(columns)

        # If grouping resulted in empty dict, fall back to wrapped display
        if not groups:
            self._print_wrapped_columns(columns, indent=indent)
            return

        for group_name, cols in groups.items():
            logger.info(f"{indent}{group_name} ({len(cols)}):")
            self._print_wrapped_columns(cols, indent=indent + "  ")

    def _group_columns_by_prefix(self, columns: list[str]) -> dict[str, list[str]]:
        """Group columns by common prefix (before first underscore).

        Args:
            columns: List of column names

        Returns:
            Dictionary mapping group names to lists of column names
        """
        from collections import defaultdict

        prefix_groups: dict[str, list[str]] = defaultdict(list)

        for col in columns:
            parts = col.split("_", 1)  # Split on first underscore only
            if len(parts) > 1:
                prefix = parts[0]
                prefix_groups[prefix].append(col)
            else:
                prefix_groups["other"].append(col)

        # Convert to nice group names and organize
        result: dict[str, list[str]] = {}
        other_cols: list[str] = []

        for prefix, cols in sorted(prefix_groups.items()):
            if len(cols) >= 2:  # Only group if 2+ columns share prefix
                group_name = self._format_group_name(prefix)
                result[group_name] = sorted(cols)
            else:
                # Single column with this prefix goes to "Other"
                other_cols.extend(cols)

        # Add "Other" group if it has columns
        if other_cols:
            result["Other"] = sorted(other_cols)

        return result

    def _format_group_name(self, prefix: str) -> str:
        """Convert prefix to nice group name.

        Args:
            prefix: Column prefix

        Returns:
            Formatted group name
        """
        # Special cases for common prefixes
        special_names = {
            "ml": "ML Features",
            "lang": "Language Features",
            "acl": "ACL Features",
            "chunk": "Chunking Features",
            "classification": "Classification Features",
            "embedding": "Embedding Features",
        }

        prefix_lower = prefix.lower()
        if prefix_lower in special_names:
            return special_names[prefix_lower]

        # Default: Title case with "Features" suffix
        return f"{prefix.title()} Features"

    def _print_operator_metadata(self, metadata: dict[str, Any]) -> None:
        """Print all operator metadata with formatting.

        Args:
            metadata: Operator-specific metadata dictionary (may contain nested 'node_metadata' for old format)
        """
        if not metadata:
            return

        # Handle old format where metadata is wrapped
        actual_metadata = metadata.get("node_metadata", metadata) if "node_metadata" in metadata else metadata

        if not actual_metadata:
            return

        # Separate metadata by type for organized display
        categorized = self._categorize_metadata(actual_metadata)

        if not any(categorized.values()):
            return

        # Print sections
        logger.info("")
        self._print_numeric_fields(categorized["numeric"])
        self._print_dict_fields(categorized["dict"], has_numeric=bool(categorized["numeric"]))
        self._print_other_fields(categorized["other"])
        self._print_list_fields(categorized["list"])

    def _categorize_metadata(self, metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Categorize metadata fields by type.

        Args:
            metadata: Metadata dictionary

        Returns:
            Dictionary with categorized fields
        """
        categorized: dict[str, dict[str, Any]] = {"numeric": {}, "dict": {}, "list": {}, "other": {}}

        for field, value in metadata.items():
            if field in self._STANDARD_FIELDS:
                continue

            if isinstance(value, (int, float)) and value != 0:
                categorized["numeric"][field] = value
            elif isinstance(value, dict) and value:
                categorized["dict"][field] = value
            elif isinstance(value, list):
                categorized["list"][field] = value
            elif value not in (None, ""):
                categorized["other"][field] = value

        return categorized

    def _print_numeric_fields(self, fields: dict[str, Any]) -> None:
        """Print numeric metadata fields."""
        if not fields:
            return

        logger.info(" Operator Metrics:")
        for field, value in sorted(fields.items()):
            display_name = field.replace("_", " ").title()
            logger.info(f"   {display_name}: {value}")

    def _print_dict_fields(self, fields: dict[str, Any], *, has_numeric: bool) -> None:
        """Print dictionary metadata fields."""
        if not fields:
            return

        if not has_numeric:
            logger.info(" Operator Details:")

        for field, value in sorted(fields.items()):
            display_name = field.replace("_", " ").title()
            self._format_dict_field(display_name, value)

    def _format_dict_field(self, display_name: str, value: dict) -> None:  # NOSONAR python:S3776
        """Format and print a dictionary field."""
        has_nested_dicts = any(isinstance(v, dict) for v in value.values())

        if has_nested_dicts:
            logger.info(f"   {display_name}:")
            for k, v in value.items():
                if isinstance(v, dict):
                    logger.info(f"      {k}:")
                    for nested_k, nested_v in v.items():
                        logger.info(f"         {nested_k}: {nested_v}")
                else:
                    logger.info(f"      {k}: {v}")
        elif len(value) <= 10:
            formatted = ", ".join(f"{k}={v}" for k, v in value.items())
            logger.info(f"   {display_name}: {formatted}")
        else:
            logger.info(f"   {display_name}:")
            for k, v in list(value.items())[:10]:
                logger.info(f"      {k}: {v}")
            if len(value) > 10:
                logger.info(f"      ... and {len(value) - 10} more")

    def _print_other_fields(self, fields: dict[str, Any]) -> None:
        """Print string/other metadata fields."""
        if not fields:
            return

        for field, value in sorted(fields.items()):
            display_name = field.replace("_", " ").title()
            str_value = str(value)
            if len(str_value) > 100:
                str_value = str_value[:97] + "..."
            logger.info(f"   {display_name}: {str_value}")

    def _print_list_fields(self, fields: dict[str, Any]) -> None:
        """Print list metadata fields."""
        if not fields:
            return

        for field, value in sorted(fields.items()):
            if field in ("failed_docs", "skipped_docs"):
                self._print_failed_skipped_docs(field, value)
            else:
                self._print_generic_list(field, value)

    def _print_failed_skipped_docs(self, field: str, docs: list) -> None:
        """Print failed or skipped documents."""
        if not docs:
            return

        logger.info("")
        logger.info(f" {field.replace('_', ' ').upper()} ({len(docs)} items):")
        for item in docs[:10]:
            if isinstance(item, dict):
                doc_id = item.get("id", "unknown")
                reason = item.get("reason", "")
                display_name = self._lookup_doc_name_from_table(doc_id) or doc_id

                if reason:
                    logger.info(f"   - {display_name}: {reason}")
                else:
                    logger.info(f"   - {display_name}")
            else:
                logger.info(f"   - {item}")

        if len(docs) > 10:
            logger.info(f"   ... and {len(docs) - 10} more")

    def _print_generic_list(self, field: str, value: list) -> None:
        """Print generic list field."""
        display_name = field.replace("_", " ").title()
        if value:
            if len(value) <= 5:
                formatted_list = ", ".join(str(v) for v in value)
                logger.info(f"   {display_name}: {formatted_list}")
            else:
                preview = ", ".join(str(v) for v in value[:3])
                logger.info(f"   {display_name} ({len(value)} items): {preview}, ...")
        else:
            logger.info(f"   {display_name}: []")

    def _lookup_doc_name_from_table(self, doc_id: str) -> str | None:  # NOSONAR python:S3776
        """Look up document name from PyArrow table using document ID.

        Args:
            doc_id: Document ID (hash) to look up

        Returns:
            Document name/path if found, None otherwise
        """
        if not doc_id:
            return None

        try:
            # Try current tables first, then previous tables (for skipped docs)
            tables_to_search = []
            if self._current_tables:
                tables_to_search.extend(self._current_tables)
            if self._previous_tables:
                tables_to_search.extend(self._previous_tables)

            if not tables_to_search:
                return None

            # Try each table in the list
            for table in tables_to_search:
                if table is None:
                    continue

                # Check if table has the 'id' column
                id_column = OperatorConstants.Columns.ID
                if id_column not in table.column_names:
                    continue

                # Look for the document ID by iterating through rows
                id_col = table.column(id_column)
                for idx in range(len(id_col)):
                    # Convert both to string for comparison
                    row_id = str(id_col[idx].as_py())
                    search_id = str(doc_id)

                    if row_id == search_id:
                        # Found the document, now get its name
                        # Try 'name' column first, then 'path'
                        for col_name in ["name", "path"]:
                            if col_name in table.column_names:
                                name_value = table.column(col_name)[idx].as_py()
                                if name_value and str(name_value) != search_id:
                                    return name_value

                        # If name/path same as ID, return None to use fallback
                        return None

            return None
        except Exception:
            # Silently fail - this is just for enhanced display
            return None

    def print_flow_summary(self, *, job_stats: JobStats, dag_nodes: list[dict]) -> None:
        """Print final flow execution summary.

        Args:
            job_stats: Complete job statistics
            dag_nodes: DAG node definitions in execution order
        """
        status = job_stats.status.value if job_stats.status else "UNKNOWN"
        duration = float(job_stats.duration) if job_stats.duration else 0.0

        logger.info("")
        logger.info("=" * 80)
        logger.info(" FLOW EXECUTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f" Status: {status}")
        logger.info(f" Total Duration: {duration:.2f}s")

        # Use total_docs as the authoritative count
        total_docs = job_stats.total_docs
        actually_completed = total_docs - job_stats.failed_docs - job_stats.skipped_docs

        logger.info(
            f" Documents: {actually_completed} completed, {job_stats.failed_docs} failed, {job_stats.skipped_docs} skipped (of {total_docs} total)"
        )

        # Print per-operator summary table in execution order
        if job_stats.node_stats:
            self._print_operator_summary_table(job_stats.node_stats, dag_nodes)

        logger.info("=" * 80)
        logger.info("")

    def _print_operator_summary_table(self, node_stats: dict, dag_nodes: list[dict]) -> None:
        """Print operator summary table in DAG execution order."""
        logger.info("")
        logger.info(" Operator Summary:")
        logger.info(f" {'Operator':<30} {'Status':<20} {'Duration':<12} {'Docs':<10}")
        logger.info(" " + "-" * 78)

        # Create position map from DAG order
        dag_order = [
            op_def.get(OperatorConstants.Columns.ID) for op_def in dag_nodes if op_def.get(OperatorConstants.Columns.ID)
        ]
        position_map = {node_id: idx for idx, node_id in enumerate(dag_order)}

        # Sort nodes by DAG position
        sorted_nodes = sorted(node_stats.items(), key=lambda x: position_map.get(x[0], float("inf")))

        for node_id, stats in sorted_nodes:
            step_name = stats.name or node_id[:8]
            status_str = stats.node_status
            duration_str = self._format_duration(stats.time_taken)

            # Calculate document counts
            completed = len(stats.docs_completed)
            failed = len(stats.failed_docs)
            skipped = len(stats.skipped_docs)
            total = completed + failed + skipped
            docs_str = f"{completed}/{total}"

            logger.info(f" {step_name:<30} {status_str:<20} {duration_str:<12} {docs_str:<10}")
