"""Thread-safe DuckDB connection manager."""

import logging
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import duckdb

logger = logging.getLogger(__name__)


class DuckDBConnectionManager:
    """Manage DuckDB connections with shared in-memory support."""

    _instance: "DuckDBConnectionManager | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "DuckDBConnectionManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._connections: dict[str, duckdb.DuckDBPyConnection] = {}
        logger.debug("DuckDB connection manager initialized")

    @contextmanager
    def get_connection(
        self,
        database_path: str,
        read_only: bool = False,
    ) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        """Yield a DuckDB connection."""
        if database_path == ":memory:":
            with self._lock:
                connection = self._connections.get(database_path)
                if connection is None:
                    connection = duckdb.connect(database_path)
                    self._connections[database_path] = connection
                    logger.debug("Created persistent in-memory DuckDB connection")
            yield connection
            return

        connection = None
        try:
            if not read_only:
                Path(database_path).parent.mkdir(parents=True, exist_ok=True)

            connection = duckdb.connect(database=database_path, read_only=read_only)
            logger.debug("Created DuckDB connection: %s (read_only=%s)", database_path, read_only)
            yield connection
        except Exception:
            logger.exception("Error with DuckDB connection %s", database_path)
            raise
        finally:
            if connection is not None:
                try:
                    connection.close()
                    logger.debug("Closed DuckDB connection: %s", database_path)
                except Exception:
                    logger.exception("Error closing connection %s", database_path)

    def close_all(self) -> None:
        """Close all persistent connections."""
        with self._lock:
            for connection_key, connection in list(self._connections.items()):
                try:
                    connection.close()
                    logger.debug("Closed connection: %s", connection_key)
                except Exception:
                    logger.exception("Error closing connection %s", connection_key)
            self._connections.clear()

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close_all()
            cls._instance = None
