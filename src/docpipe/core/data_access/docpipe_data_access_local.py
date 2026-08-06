"""
Docpipe DataAccessLocal implementation that handles memmap file paths correctly.

This module provides a Docpipe implementation of DataAccessLocal that ensures:
- Cache stores tables with memmap file paths (memory efficient)
- Persistent parquet files store actual expanded data (portable and complete)
"""

from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from data_processing.data_access import DataAccessLocal

from docpipe.utils.core.memmap_file_utils import replace_memmap_paths_combined
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class DocpipeDataAccessLocal(DataAccessLocal):
    """
    Docpipe DataAccessLocal that separates cache and persistent storage for memmap handling.

    This class overrides save_table to:
    1. Cache the table with memmap file paths (memory efficient)
    2. Write expanded table (with actual data) to parquet file (persistent and portable)

    This ensures:
    - In-memory cache contains memmap paths for efficiency
    - Parquet files contain actual data for persistence and portability
    """

    def save_table(self, path: str, table: pa.Table) -> tuple[int, dict[str, Any], int]:
        """
        Saves a pyarrow table with proper memmap handling.

        Strategy:
        1. Cache the table with memmap paths in self.tables (memory efficient)
        2. Replace memmap paths with actual data
        3. Write expanded table to parquet file

        Args:
            path (str): The path to the output file.
            table (pa.Table): The pyarrow table to save (may contain memmap file paths).

        Returns:
            tuple: A tuple containing:
                - size_in_memory (int): The size of the table in memory (bytes).
                - file_info (dict or None): A dictionary containing:
                    - name (str): The name of the file.
                    - size (int): The size of the file (bytes).
                  If saving fails, file_info will be None.
                - status (int): 0 for success, -1 for error.
        """
        # Step 1: Save the table in memory cache with memmap paths (memory efficient)
        if self.cache:
            logger.debug(f"Caching table with memmap paths: {path}")
            self.tables[path] = table

        # Get table size in memory
        size_in_memory = table.nbytes

        try:
            # Step 2: Replace memmap paths with actual data for persistent storage
            logger.debug("Replacing memmap paths with actual data for parquet file")
            expanded_table = replace_memmap_paths_combined(table=table)

            # Step 3: Write expanded table to parquet format
            path_obj = Path(path)
            if path_obj.parent.name:
                path_obj.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(expanded_table, path)

            # Get file size and create file_info
            file_info = {"name": path_obj.name, "size": path_obj.stat().st_size}
            logger.info(f"Saved table with data to: {path}")
            return size_in_memory, file_info, 0

        except Exception as e:
            logger.error(f"Error saving table to {path}: {e}", exc_info=True)
            return -1, {}, 0
