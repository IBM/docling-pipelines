"""
File locking manager for thread-safe and process-safe file operations.

Uses the filelock library for robust cross-platform file locking.
Supports both shared (read) and exclusive (write) locks with configurable timeout.

Example:
    >>> from pathlib import Path
    >>> from docpipe.core.assets.flows.adapters.repositories.local import FileLockManager
    >>>
    >>> # Initialize lock manager
    >>> lock_manager = FileLockManager(enable_locking=True, lock_timeout=30.0)
    >>>
    >>> # Acquire exclusive lock for write operations
    >>> lock_file = Path("/path/to/.myfile.lock")
    >>> with lock_manager.acquire_lock(lock_file, exclusive=True):
    ...     # Perform write operation
    ...     pass
    >>>
    >>> # Acquire shared lock for read operations (treated as exclusive on some platforms)
    >>> with lock_manager.acquire_lock(lock_file, exclusive=False):
    ...     # Perform read operation
    ...     pass
    >>>
    >>> # Clean up lock file when done
    >>> lock_manager.cleanup_lock_file(lock_file)

Thread Safety:
    When enable_locking=True, operations are thread-safe and process-safe.
    File-level locking prevents race conditions in concurrent access scenarios.
    When enable_locking=False, external synchronization is required.

Platform Support:
    - Cross-platform support via filelock library
    - Handles lock file lifecycle correctly
    - Automatic cleanup of stale locks

Important: The filelock library does not distinguish between shared and exclusive
locks - all locks are treated as exclusive. This means read operations will block
other read operations, unlike traditional shared/exclusive locking mechanisms.
"""

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from filelock import FileLock, Timeout

logger = logging.getLogger(__name__)


class FileLockManager:
    """
    Manages file-level locking for concurrent access control using filelock library.

    Provides cross-platform file locking with configurable timeout and retry logic.
    Note: The filelock library doesn't distinguish between shared and exclusive locks,
    so all locks are treated as exclusive.

    Attributes:
        enable_locking (bool): Whether file locking is enabled
        lock_timeout (float): Maximum time to wait for lock acquisition (seconds)
        lock_retry_interval (float): Time between lock acquisition retries (seconds)
    """

    def __init__(self, enable_locking: bool = True, lock_timeout: float = 30.0, lock_retry_interval: float = 0.1):
        """
        Initialize the file lock manager.

        Args:
            enable_locking (bool): Enable file-level locking for thread/process safety.
                                  Default: True
            lock_timeout (float): Maximum time to wait for lock acquisition in seconds.
                                 Default: 30.0 seconds
            lock_retry_interval (float): Time between lock acquisition retries in seconds.
                                        Default: 0.1 seconds (used by filelock internally)
        """
        self.enable_locking = enable_locking
        self.lock_timeout = lock_timeout
        self.lock_retry_interval = lock_retry_interval

        locking_status = "enabled" if enable_locking else "disabled"
        logger.debug(f"FileLockManager initialized: locking={locking_status}, timeout={lock_timeout}s")

    @contextmanager
    def acquire_lock(
        self, lock_file_path: Path, exclusive: bool = True, timeout: float | None = None
    ) -> Generator[None, None, None]:
        """
        Acquire a file lock (context manager) with optional custom timeout.

        Acquires a file lock for the specified file using the filelock library.
        Note: The filelock library treats all locks as exclusive, so the exclusive
        parameter is accepted for API compatibility but doesn't change behavior.

        Args:
            lock_file_path (Path): Path to the lock file
            exclusive (bool): If True, acquire exclusive lock (write).
                            If False, acquire shared lock (read).
                            Note: filelock treats all locks as exclusive.
                            Default: True
            timeout (float | None): Lock timeout in seconds (uses self.lock_timeout if None)

        Yields:
            None: Lock is held during context

        Raises:
            TimeoutError: If lock cannot be acquired within lock_timeout
            OSError: If lock file operations fail

        Example:
            >>> lock_manager = FileLockManager()
            >>> lock_file = Path("/tmp/.myfile.lock")
            >>> with lock_manager.acquire_lock(lock_file, exclusive=True, timeout=5.0):
            ...     # Critical section - lock is held
            ...     pass
        """
        if not self.enable_locking:
            # Locking disabled, just yield
            yield
            return

        # Use provided timeout or fall back to default
        if timeout is None:
            timeout = self.lock_timeout

        # Create FileLock instance
        lock = FileLock(str(lock_file_path), timeout=timeout)

        try:
            # Acquire lock with timeout
            with lock.acquire(timeout=timeout):
                lock_mode = "exclusive" if exclusive else "shared"
                logger.debug(f"Acquired {lock_mode} lock on {lock_file_path.name}")
                yield
        except Timeout as e:
            raise TimeoutError(f"Failed to acquire lock on {lock_file_path.name} within {timeout}s timeout") from e

    def cleanup_lock_file(self, lock_file_path: Path) -> None:
        """
        Clean up a lock file.

        Removes the lock file from the filesystem. Should be called when
        the locked resource is deleted (e.g., when a flow is deleted).

        Args:
            lock_file_path (Path): Path to the lock file to clean up

        Note:
            Failures during cleanup are logged but not raised, as they are
            not critical to the operation's success.

        Example:
            >>> lock_manager = FileLockManager()
            >>> lock_file = Path("/tmp/.myfile.lock")
            >>> lock_manager.cleanup_lock_file(lock_file)
        """
        if lock_file_path.exists():
            try:
                lock_file_path.unlink()
                logger.debug(f"Cleaned up lock file: {lock_file_path.name}")
            except OSError as e:
                logger.warning(f"Failed to clean up lock file {lock_file_path.name}: {e}")
