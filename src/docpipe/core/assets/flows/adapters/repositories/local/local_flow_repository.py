"""
Local filesystem implementation of FlowRepository with file locking support.

This adapter implements the FlowRepository port using local JSON file storage.
Flows are stored as individual JSON files with the naming pattern: {flowName}_{flowId}.json

Example:
    >>> import os
    >>> from docpipe.core.assets.flows.adapters.repositories.local import LocalFlowRepository
    >>> from docpipe.core.assets.flows.domain.models import Flow
    >>>
    >>> # Set flows directory via environment variable or docling-pipelines-config.yaml
    >>> os.environ["LOCAL_FLOWS_DIR"] = "/path/to/flows"
    >>>
    >>> # Initialize repository (self-configures from env or yaml)
    >>> repo = LocalFlowRepository()
    >>>
    >>> # Create and save a flow (thread-safe with locking enabled)
    >>> flow = Flow(name="my_flow", flow_id="abc-123", ...)
    >>> saved_flow = repo.save(flow)
    >>>
    >>> # Retrieve flow
    >>> retrieved = repo.find_by_id("abc-123")
    >>>
    >>> # List all flows
    >>> all_flows = repo.find_all()
    >>>
    >>> # Delete flow
    >>> repo.delete("abc-123")

Thread Safety:
    When enable_locking=True (default), this repository IS thread-safe and process-safe.
    File-level locking prevents race conditions in concurrent access scenarios.
    When enable_locking=False, external synchronization is required for concurrent access.

Atomicity:
    Individual operations (save, update, delete) use atomic file operations
    (write-then-rename pattern) to prevent corruption. However, sequences of
    operations are not transactional.
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any

from docpipe.core.assets.flows.adapters.repositories.flow_filesystem_utils import FlowFilesystemUtils
from docpipe.core.assets.flows.adapters.repositories.local.file_lock_manager import FileLockManager
from docpipe.core.assets.flows.domain.models.flow import Flow
from docpipe.core.assets.flows.domain.ports.flow_repository import FlowRepository

logger = logging.getLogger(__name__)


class LocalFlowRepository(FlowRepository):
    """
    Local filesystem implementation of FlowRepository with optional file locking.

    Stores flows as JSON files in a specified directory with the naming pattern:
    {flowName}_{flowId}.json

    Thread Safety:
        When enable_locking=True (default), this repository IS thread-safe and process-safe.
        File-level locking prevents race conditions using the filelock library
        for cross-platform support. All locks are treated as exclusive.

        When enable_locking=False, external synchronization is required for concurrent access.

    Atomicity:
        Individual operations (save, update, delete) use atomic file operations
        (write-then-rename pattern) to prevent corruption. However, sequences of
        operations are not transactional.

    Locking Strategy:
        - Read operations (find_by_id, find_all, exists): Exclusive locks (marked as shared in API for compatibility)
        - Write operations (save, update, delete): Exclusive locks
        Note: The filelock library treats all locks as exclusive, so read operations
        do not allow concurrent access despite the API parameter.

    Attributes:
        FILE_EXTENSION (str): File extension for flow files (".json")
        flows_dir (Path): Directory where flow files are stored
        lock_manager (FileLockManager): Manager for file locking operations
    """

    FILE_EXTENSION = ".json"
    GLOBAL_LOCK_ID = "__global__"

    def __init__(
        self,
        *,
        enable_locking: bool = True,
        lock_timeout: float = 30.0,
        lock_retry_interval: float = 0.1,
    ):
        """Initialize LocalFlowRepository.

        The flows directory resolution order:
        1. LOCAL_FLOWS_DIR environment variable
        2. docling-pipelines-config.yaml configuration (assets_management.flow_repository.config.base_dir)
        3. Built-in default: ~/Documents/pipeline/assets

        Args:
            enable_locking (bool): Enable file-level locking for thread/process safety.
                                  Default: True
            lock_timeout (float): Maximum time to wait for lock acquisition in seconds.
                                 Default: 30.0 seconds
            lock_retry_interval (float): Time between lock acquisition retries in seconds.
                                        Default: 0.1 seconds

        Raises:
            ValueError: If flows_dir exists but is not a directory
            PermissionError: If no write permission for flows_dir
        """
        self.flows_dir = self.get_flows_dir()
        self.locks_dir = self.flows_dir / ".locks"

        # Validate directory before creating
        if self.flows_dir.exists():
            if not self.flows_dir.is_dir():
                raise ValueError(f"flows_dir must be a directory, not a file: {self.flows_dir}")
            if not os.access(self.flows_dir, os.W_OK):
                raise PermissionError(f"No write permission for flows_dir: {self.flows_dir}")
        else:
            self.flows_dir.mkdir(parents=True, exist_ok=True)

        # Create locks directory
        self.locks_dir.mkdir(parents=True, exist_ok=True)

        # Initialize file lock manager
        self.lock_manager = FileLockManager(
            enable_locking=enable_locking, lock_timeout=lock_timeout, lock_retry_interval=lock_retry_interval
        )

        # Operation-specific lock timeouts (in seconds)
        self.TIMEOUT_READ = 5.0  # Fast read operations (find_by_id, exists)
        self.TIMEOUT_WRITE = 10.0  # Medium write operations (save, update, delete)
        self.TIMEOUT_BULK = 30.0  # Slow bulk operations (bulk_delete)
        self.TIMEOUT_LIST = 15.0  # Directory scan operations (find_all)

        locking_status = "enabled" if enable_locking else "disabled"
        logger.info(f"LocalFlowRepository initialized with directory: {self.flows_dir}, locking: {locking_status}")

    @staticmethod
    def get_flows_dir() -> Path:
        """
        Get the flows directory from explicit config, environment variable, or default.

        Resolution order:
        1. LOCAL_FLOWS_DIR environment variable
        2. docling-pipelines-config.yaml configuration (assets_management.flow_repository.config.base_dir)
        3. Built-in default: ~/Documents/pipeline/assets

        Returns:
            Path: Absolute path to the flows directory
        """
        # 1. Environment variable (highest priority for overrides)
        env_path = os.getenv("LOCAL_FLOWS_DIR")
        if env_path:
            resolved_path = Path(env_path).expanduser().resolve()
            logger.info(f"Using flows directory from environment (LOCAL_FLOWS_DIR): {resolved_path}")
            return resolved_path

        # 2. Try to load from docling-pipelines-config.yaml
        try:
            project_directory = Path(__file__).resolve().parents[8]
            config_path = Path(
                os.getenv("DOCPIPE_CONFIG_PATH", str(project_directory / "docling-pipelines-config.yaml"))
            )

            if config_path.exists():
                import yaml

                with config_path.open() as f:
                    yaml_config = yaml.safe_load(f)
                    if yaml_config:
                        assets_config = yaml_config.get("assets_management", {}) or {}
                        repo_config = assets_config.get("flow_repository", {}) or {}
                        base_dir = repo_config.get("config", {}).get("base_dir")

                        if base_dir:
                            resolved_path = Path(base_dir).expanduser().resolve()
                            logger.info(f"Using flows directory from config ({config_path}): {resolved_path}")
                            return resolved_path
        except Exception as e:
            logger.warning(f"Failed to load flows directory from config: {e}")

        # 3. Default path fallback
        resolved_path = (Path.home() / "Documents" / "pipeline" / "assets").resolve()
        logger.info(f"Using default flows directory: {resolved_path}")
        return resolved_path

    def _get_lock_file_path(self, flow_id: str) -> Path:
        """Get the lock file path for a flow.

        Args:
            flow_id (str): Flow identifier

        Returns:
            Path: Path to the lock file (stored in .locks directory)
        """
        return self.locks_dir / f"{flow_id}.lock"

    @contextmanager
    def _file_lock(self, flow_id: str, exclusive: bool = True, timeout: float | None = None):
        """Context manager for file locking with timeout.

        Delegates to FileLockManager for actual locking implementation.

        Args:
            flow_id (str): Flow identifier to lock
            exclusive (bool): If True, acquire exclusive lock (write).
                            If False, acquire shared lock (read).
                            Default: True
            timeout (float | None): Lock timeout in seconds (uses default if None)

        Yields:
            None: Lock is held during context

        Raises:
            TimeoutError: If lock cannot be acquired within lock_timeout
            OSError: If lock file operations fail
        """
        # Use provided timeout or fall back to default
        if timeout is None:
            timeout = self.lock_manager.lock_timeout

        lock_file = self._get_lock_file_path(flow_id)
        with self.lock_manager.acquire_lock(lock_file, exclusive=exclusive, timeout=timeout):
            yield

    @contextmanager
    def _global_lock(self, exclusive: bool = True):
        """Context manager for global repository lock.

        Used for operations that affect multiple flows (e.g., find_all).

        Args:
            exclusive (bool): If True, acquire exclusive lock. Default: True

        Yields:
            None: Lock is held during context
        """
        # Use a special lock file for global operations
        with self._file_lock(self.GLOBAL_LOCK_ID, exclusive=exclusive):
            yield

    def _cleanup_temp_file(self, temp_path: Path | None) -> None:
        """
        Clean up temporary file if it exists.

        Args:
            temp_path (Optional[Path]): Path to temporary file to clean up, or None

        Note:
            Failures during cleanup are silently ignored as they are not critical.
        """
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass  # Cleanup failure is acceptable if main operation failed

    def _handle_file_operation_error(
        self, operation: str, flow_id: str, error: Exception, temp_path: Path | None = None
    ) -> None:
        """Centralized error handling for file operations.

        Args:
            operation: Name of the operation being performed (e.g., "save", "update")
            flow_id: Flow identifier involved in the operation
            error: The exception that occurred
            temp_path: Optional temporary file path to clean up

        Raises:
            PermissionError: If the error is permission-related
            OSError: If the error is a file system error
            Exception: For any other unexpected errors
        """
        # Clean up temp file if provided
        if temp_path:
            self._cleanup_temp_file(temp_path)

        # Handle specific error types
        if isinstance(error, PermissionError):
            logger.error(f"Permission denied during {operation} for flow '{flow_id}': {error}")
            raise PermissionError(f"Insufficient permissions for {operation}: {error}")
        if isinstance(error, OSError):
            logger.error(f"File system error during {operation} for flow '{flow_id}': {error}")
            raise
        logger.error(f"Unexpected error during {operation} for flow '{flow_id}': {error}")
        raise

    def _get_file_path(self, flow: Flow) -> Path:
        """Get the file path for a flow using the format {flow_name}_{flow_id}.json.

        Uses FlowFilesystemUtils for filename generation.

        Args:
            flow (Flow): Flow entity

        Returns:
            Path: Path to the flow file
        """
        if flow.flow_id is None:
            raise ValueError("Flow ID is required to generate file path")
        filename = FlowFilesystemUtils.generate_flow_filename(flow.name, flow.flow_id)
        return self.flows_dir / filename

    def _find_flow_files(self, flow_id: str) -> list[Path]:
        """Find all files matching the flow_id pattern.

        Args:
            flow_id: Flow identifier to search for

        Returns:
            List of matching file paths
        """
        return [
            f
            for f in self.flows_dir.glob(f"*{self.FILE_EXTENSION}")
            if FlowFilesystemUtils.matches_flow_id_pattern(f.name, flow_id)
        ]

    def save(self, flow: Flow) -> Flow:
        """Save a flow atomically to local filesystem with file locking.

        This method saves a new flow or overwrites an existing one. The flow's
        timestamps (created_at, modified_at) should be managed by the domain model
        before calling this method.

        Uses atomic write-then-rename pattern to prevent corruption.
        Writes to temporary file first, then atomically renames.
        Acquires exclusive lock if locking is enabled.

        Args:
            flow (Flow): Flow entity to save

        Returns:
            Flow: Saved flow

        Raises:
            ValueError: If flow object is invalid or flow_id is empty
            PermissionError: If write permission denied on flows directory
            OSError: If file system operation fails
            TimeoutError: If lock cannot be acquired within timeout (when locking enabled)

        Note:
            This method does NOT modify timestamps. The caller is responsible for
            setting appropriate timestamps on the Flow object before saving.
            Uses atomic write-then-rename pattern to prevent file corruption.
            If the operation fails, no partial file is left on disk.
        """
        if flow.flow_id is None:
            raise ValueError("Flow ID is required for saving")

        # Check permissions before acquiring lock
        if not os.access(self.flows_dir, os.W_OK):
            raise PermissionError(f"No write permission for directory: {self.flows_dir}")

        with self._file_lock(flow.flow_id, exclusive=True, timeout=self.TIMEOUT_WRITE):
            temp_path = None
            try:
                flow_file_path = self._get_file_path(flow)
                temp_path = flow_file_path.with_suffix(".tmp")

                # Write to temporary file first
                with temp_path.open("w", encoding="utf-8") as f:
                    json.dump(flow.to_dict(), f, indent=2, default=str)

                # Atomic rename - OS guarantees this operation is atomic
                # (either completes fully or not at all, preventing corruption)
                temp_path.replace(flow_file_path)
                # Clear temp_path after successful rename so error handler won't try to clean it up
                temp_path = None

                logger.info(f"Saved flow {flow.flow_id} to {flow_file_path}")
                return flow

            except (PermissionError, OSError, Exception) as e:
                self._handle_file_operation_error("save", flow.flow_id, e, temp_path)
                raise  # Ensure type checker knows this path doesn't return

    def update(self, flow: Flow) -> Flow:
        """Update an existing flow atomically with file locking.

        This method updates the modified_at timestamp automatically before saving.
        Updates flow with atomic write-then-rename. If flow name changes,
        old file is deleted after successful write.
        Acquires exclusive lock if locking is enabled.

        Args:
            flow (Flow): Flow entity with updated data

        Returns:
            Flow: Updated flow with updated modified_at timestamp

        Raises:
            ValueError: If flow not found or flow object is invalid
            PermissionError: If write permission denied on flows directory
            OSError: If file system operation fails
            TimeoutError: If lock cannot be acquired within timeout (when locking enabled)

        Note:
            Uses atomic write-then-rename pattern for the new file.
            If flow name changes, old file is deleted after successful write.
            Old file deletion failure is logged but does not fail the operation.
        """
        if flow.flow_id is None:
            raise ValueError("Flow ID is required for updating")

        # Check permissions before acquiring lock
        if not os.access(self.flows_dir, os.W_OK):
            raise PermissionError(f"No write permission for directory: {self.flows_dir}")

        with self._file_lock(flow.flow_id, exclusive=True, timeout=self.TIMEOUT_WRITE):
            temp_path = None
            try:
                # Update timestamp
                flow.update_timestamp()

                # Find old file(s) with this flow_id
                old_files = self._find_flow_files(flow.flow_id)

                if not old_files:
                    raise ValueError(f"Flow with id {flow.flow_id} not found")

                old_path = old_files[0]
                new_path = self._get_file_path(flow)
                temp_path = new_path.with_suffix(".tmp")

                # Write to temp file
                with temp_path.open("w", encoding="utf-8") as f:
                    json.dump(flow.to_dict(), f, indent=2, default=str)

                # Atomic rename
                temp_path.replace(new_path)
                # Clear temp_path after successful rename so error handler won't try to clean it up
                temp_path = None

                # Delete old file if flow_id changed
                name_changed = old_path != new_path
                if name_changed and old_path.exists():
                    try:
                        old_path.unlink()
                        logger.debug(f"Deleted old flow file after rename: {old_path.name}")
                    except OSError as e:
                        logger.warning(
                            f"Failed to delete old flow file {old_path.name}. Manual cleanup may be required: {e}"
                        )
                        # Don't raise - the update succeeded, orphaned file is not critical

                # Check for and clean up any orphaned files for this flow_id
                try:
                    all_files_for_flow = self._find_flow_files(flow.flow_id)
                    if len(all_files_for_flow) > 1:
                        logger.warning(
                            "Found %d files for flow_id %s (expected 1). Cleaning up orphaned files.",
                            len(all_files_for_flow),
                            flow.flow_id,
                        )
                        # Keep the newest file, delete the rest
                        all_files_for_flow.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                        for orphaned_file in all_files_for_flow[1:]:
                            try:
                                orphaned_file.unlink()
                                logger.info("Cleaned up orphaned file: %s", orphaned_file.name)
                            except OSError as e:
                                logger.warning("Failed to clean up orphaned file %s: %s", orphaned_file.name, e)
                except Exception as e:
                    logger.warning("Error checking for orphaned files for flow_id %s: %s", flow.flow_id, e)

                logger.info(f"Updated flow {flow.flow_id}")
                return flow

            except (PermissionError, OSError, Exception) as e:
                self._handle_file_operation_error("update", flow.flow_id, e, temp_path)
                raise  # Ensure type checker knows this path doesn't return

    def _read_and_validate_flow(self, flow_file_path: Path, expected_flow_id: str) -> Flow:
        """Read and validate a flow file.

        Args:
            flow_file_path: Path to the flow file
            expected_flow_id: Expected flow_id for validation

        Returns:
            Flow: The loaded and validated flow

        Raises:
            ValueError: If file is corrupted or flow_id doesn't match
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If JSON is invalid
        """
        try:
            with flow_file_path.open(encoding="utf-8") as f:
                flow_dict = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Corrupted flow file {flow_file_path.name}: invalid JSON - {e}") from e
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Flow file not found: {flow_file_path}") from e

        flow = Flow.from_dict(data=flow_dict)

        # Validate flow_id matches filename
        if flow.flow_id != expected_flow_id:
            raise ValueError(
                f"Data integrity error in {flow_file_path.name}: "
                f"expected flow_id '{expected_flow_id}' but got '{flow.flow_id}'"
            )

        return flow

    def find_by_id(self, flow_id: str) -> Flow | None:
        """Find a flow by ID with file locking.

        Uses filename for fast O(1) lookup, then validates the loaded flow's
        ID matches to ensure data integrity. Protected against race conditions.
        Acquires shared lock if locking is enabled.

        Args:
            flow_id (str): UUID of the flow to find

        Returns:
            Optional[Flow]: Flow if found and valid, None otherwise

        Raises:
            ValueError: If flow_id is empty, JSON is corrupted, or data integrity error detected
            PermissionError: If read permission denied on flows directory
            FileNotFoundError: If flow file does not exist
            OSError: If file system operation fails
            TimeoutError: If lock cannot be acquired within timeout (when locking enabled)
        """
        # Check permissions before acquiring lock
        if not os.access(self.flows_dir, os.R_OK):
            raise PermissionError(f"No read permission for directory: {self.flows_dir}")

        try:
            with self._file_lock(flow_id, exclusive=False, timeout=self.TIMEOUT_READ):
                matching_files = self._find_flow_files(flow_id)

                if not matching_files:
                    logger.debug(f"Flow '{flow_id}' not found")
                    return None

                if len(matching_files) > 1:
                    raise ValueError(
                        f"Data integrity error: multiple files found for flow_id '{flow_id}'. "
                        f"Found: {[f.name for f in matching_files]}"
                    )

                try:
                    flow = self._read_and_validate_flow(matching_files[0], flow_id)
                    logger.info(f"Retrieved flow '{flow_id}'")
                    return flow
                except FileNotFoundError:
                    # File was deleted between glob and read - not an error
                    logger.debug("Flow file was deleted during read")
                    return None

        except ValueError:
            # Re-raise ValueError (data integrity errors)
            raise
        except Exception as e:
            self._handle_file_operation_error("find_by_id", flow_id, e)
            return None

    def _find_all_flow_files(self) -> list[Path]:
        """Find all flow files in the repository directory.

        Returns:
            List[Path]: List of paths to flow JSON files
        """
        return list(self.flows_dir.glob(f"*{self.FILE_EXTENSION}"))

    def _read_flow_file(self, flow_file: Path) -> dict[str, Any]:
        """Read and parse a flow file.

        Args:
            flow_file: Path to the flow file

        Returns:
            dict: Parsed flow data

        Raises:
            json.JSONDecodeError: If JSON is invalid
            OSError: If file cannot be read
        """
        with flow_file.open(encoding="utf-8") as f:
            return json.load(f)

    def find_all(self, filters: dict[str, Any] | None = None) -> list[Flow]:
        """Retrieve all flows from the repository.

        Uses per-file shared locks instead of global lock for better concurrency.
        Provides eventually consistent snapshot (flows read sequentially).
        If individual flow files fail to load, they are skipped with a warning.

        Args:
            filters: Optional dictionary of filters to apply (reserved for future use)

        Returns:
            List[Flow]: List of all successfully loaded flows. May be empty if
                no flows exist or all flows failed to load.

        Raises:
            PermissionError: If read permission is denied for the flows directory
            OSError: If there's a file system error accessing the directory
            TimeoutError: If lock cannot be acquired within timeout (when locking enabled)

        Note:
            This method returns partial results if some flows fail to load.
            Check logs for warnings about failed loads.
            Uses per-file locks for better concurrency compared to global lock.
        """
        logger.debug("Finding all flows with filters: %s", filters)

        # Check permissions before starting
        if not os.access(self.flows_dir, os.R_OK):
            raise PermissionError(f"No read permission for directory: {self.flows_dir}")

        try:
            # Find all flow files (no lock needed for directory scan)
            flow_files = self._find_all_flow_files()
            flows = []

            # Read each flow with per-file lock
            for flow_file in flow_files:
                try:
                    flow_id = FlowFilesystemUtils.extract_flow_id_from_filename(flow_file.name)

                    # Skip files with invalid flow_id
                    if flow_id is None:
                        logger.warning("Could not extract flow_id from filename: %s", flow_file.name)
                        continue

                    # Use per-file shared lock for reading
                    with self._file_lock(flow_id, exclusive=False, timeout=self.TIMEOUT_LIST):
                        flow_data = self._read_flow_file(flow_file)
                        flow = Flow.from_dict(data=flow_data)
                        flows.append(flow)

                except KeyError as e:
                    logger.warning("Skipping corrupted flow file %s: missing required field %s", flow_file.name, e)
                    continue
                except (ValueError, OSError, FileNotFoundError) as e:
                    logger.warning("Failed to read flow file %s: %s", flow_file.name, e)
                    continue

            logger.info("Found %d flows", len(flows))
            return flows

        except Exception as e:
            logger.error("Failed to find flows: %s", e)
            raise ValueError(f"Failed to find flows: {e}") from e

    def delete(self, flow_id: str) -> bool:
        """Delete a flow from local filesystem with file locking.

        Searches for files matching the pattern *_{flow_id}.json and deletes them.
        Acquires exclusive lock if locking is enabled.

        Args:
            flow_id (str): Unique identifier of the flow to delete

        Returns:
            bool: True if at least one file was deleted, False if no matching files were found

        Raises:
            PermissionError: If write permission denied on flows directory
            OSError: If file system operation fails
            TimeoutError: If lock cannot be acquired within timeout (when locking enabled)
        """
        # Check permissions before acquiring lock
        if not os.access(self.flows_dir, os.W_OK):
            raise PermissionError(f"No write permission for directory: {self.flows_dir}")

        try:
            with self._file_lock(flow_id, exclusive=True, timeout=self.TIMEOUT_WRITE):
                matching_files = self._find_flow_files(flow_id)

                if not matching_files:
                    logger.info(f"Flow '{flow_id}' not found for deletion")
                    return False

                # Delete the flow file
                flow_file_path = matching_files[0]
                flow_file_path.unlink()
                logger.info(f"Successfully deleted flow {flow_id}")

                # Clean up the lock file for this flow
                lock_file = self._get_lock_file_path(flow_id)
                self.lock_manager.cleanup_lock_file(lock_file)

                return True

        except Exception as e:
            self._handle_file_operation_error("delete", flow_id, e)
            raise  # Ensure type checker knows this path doesn't return

    def bulk_delete(self, flow_ids: list[str], batch_size: int = 10, max_workers: int = 4) -> dict[str, Any]:
        """Delete multiple flows in parallel using per-file locking.

        Uses ThreadPoolExecutor for parallel processing with per-file locks
        instead of a global lock, allowing true parallelization.

        Args:
            flow_ids: List of unique identifiers of flows to delete
            batch_size: Number of flows per batch (reserved for future batching support)
            max_workers: Maximum number of parallel workers (default: 4)

        Returns:
            Dictionary containing:
                - deleted (list[str]): Successfully deleted flow_ids
                - failed (list[dict]): Failed deletions with flow_id and error
                - total_requested (int): Total number requested
                - total_deleted (int): Count of successful deletions
                - total_failed (int): Count of failed deletions

        Raises:
            ValueError: If flow_ids list is empty
            PermissionError: If write permission denied on flows directory
            OSError: If file system operation fails
            TimeoutError: If lock cannot be acquired within timeout (when locking enabled)

        Note:
            Uses per-file locks for each deletion, enabling parallel processing.
            Lock timeout uses TIMEOUT_BULK (30.0 seconds) for each individual file lock.
            Individual flow deletions continue even if some fail.
            The batch_size parameter is reserved for future batching support.
        """
        if not flow_ids:
            raise ValueError("flow_ids list cannot be empty")

        # Check permissions before starting
        if not os.access(self.flows_dir, os.W_OK):
            raise PermissionError(f"No write permission for directory: {self.flows_dir}")

        # Thread-safe result aggregation
        results_lock = Lock()
        results: dict[str, list[Any]] = {"deleted": [], "failed": []}

        logger.info(f"Starting parallel bulk delete for {len(flow_ids)} flows with {max_workers} workers")

        def _delete_single_flow(flow_id: str) -> None:
            """Delete a single flow with per-file lock."""
            try:
                with self._file_lock(flow_id, exclusive=True, timeout=self.TIMEOUT_BULK):
                    matching_files = self._find_flow_files(flow_id)

                    if not matching_files:
                        with results_lock:
                            results["failed"].append({"flow_id": flow_id, "error": f"Flow {flow_id} not found"})
                        logger.debug(f"Flow '{flow_id}' not found for deletion")
                        return

                    # Delete the flow file
                    flow_file_path = matching_files[0]
                    flow_file_path.unlink()

                    with results_lock:
                        results["deleted"].append(flow_id)
                    logger.debug(f"Successfully deleted flow {flow_id} in bulk operation")

            except TimeoutError as e:
                with results_lock:
                    results["failed"].append({"flow_id": flow_id, "error": f"Lock timeout: {e}"})
                logger.warning(f"Lock timeout deleting flow {flow_id}: {e}")
            except PermissionError as e:
                with results_lock:
                    results["failed"].append({"flow_id": flow_id, "error": f"Permission denied: {e}"})
                logger.warning(f"Permission denied deleting flow {flow_id}: {e}")
            except OSError as e:
                with results_lock:
                    results["failed"].append({"flow_id": flow_id, "error": f"File system error: {e}"})
                logger.warning(f"File system error deleting flow {flow_id}: {e}")
            except Exception as e:
                with results_lock:
                    results["failed"].append({"flow_id": flow_id, "error": str(e)})
                logger.warning(f"Unexpected error deleting flow {flow_id}: {e}")

        # Process deletions in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_delete_single_flow, flow_id) for flow_id in flow_ids]
            for future in as_completed(futures):
                try:
                    future.result()  # Raise any exceptions that occurred
                except Exception as e:
                    # Exceptions are already handled in _delete_single_flow
                    # This is just to ensure we don't miss any critical errors
                    logger.error(f"Unexpected error in parallel deletion: {e}")

        result = {
            "deleted": results["deleted"],
            "failed": results["failed"],
            "total_requested": len(flow_ids),
            "total_deleted": len(results["deleted"]),
            "total_failed": len(results["failed"]),
        }

        logger.info(
            f"Bulk delete completed: {result['total_deleted']} deleted, "
            f"{result['total_failed']} failed out of {result['total_requested']} requested"
        )

        return result

    def exists(self, flow_id: str) -> bool:
        """
        Check if a flow exists.

        Args:
            flow_id: The flow ID to check

        Returns:
            True if the flow exists, False otherwise

        Raises:
            ValueError: If flow_id is invalid
            TimeoutError: If lock cannot be acquired within timeout

        Warning:
            This method has a Time-of-Check-Time-of-Use (TOCTOU) vulnerability.
            The flow may be deleted between checking existence and using it.

            Recommended pattern:
                # BAD: TOCTOU vulnerability
                if repo.exists(flow_id):
                    flow = repo.find_by_id(flow_id)  # Might return None!

                # GOOD: Direct read
                flow = repo.find_by_id(flow_id)
                if flow is not None:
                    # Use flow safely

        Note:
            Uses per-file shared lock with TIMEOUT_READ (5.0 seconds).
        """
        with self._file_lock(flow_id, exclusive=False, timeout=self.TIMEOUT_READ):
            return bool(self._find_flow_files(flow_id))
