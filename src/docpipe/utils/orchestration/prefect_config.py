"""Prefect configuration and environment setup utilities."""

import os
import shutil
import tempfile
from pathlib import Path

from docpipe.utils.infrastructure.logging import get_logger

PREFECT_HOME_PREFIX = "prefect_"
PREFECT_HOME = "PREFECT_HOME"
PREFECT_API_DATABASE_CONNECTION_URL = "PREFECT_API_DATABASE_CONNECTION_URL"
PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED = "PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED"
PREFECT_CLOUD_ENABLE_ORCHESTRATION_TELEMETRY = "PREFECT_CLOUD_ENABLE_ORCHESTRATION_TELEMETRY"
PREFECT_SERVER_ANALYTICS_ENABLED = "PREFECT_SERVER_ANALYTICS_ENABLED"
PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS = "PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS"
PREFECT_API_URL = "PREFECT_API_URL"
# Set to "true" to use SQLite with persistent storage and the default Prefect home directory.
# Allows accessing Prefect dashboard for flows review.
PREFECT_DEBUG = "PREFECT_DEBUG"
# Set to "server" to use persistent Prefect server with PostgreSQL backend
PREFECT_MODE = "PREFECT_MODE"


def set_prefect_env_variables() -> None:
    """
    Configure Prefect environment variables for optimal operation.

    Supports two modes:
    1. Ephemeral mode (default): In-memory SQLite, temporary directory
    2. Server mode: Persistent PostgreSQL, connects to external Prefect server

    Mode is determined by PREFECT_MODE environment variable:
    - "server": Use persistent Prefect server (requires PREFECT_API_URL)
    - "ephemeral" or unset: Use in-memory ephemeral mode
    """
    logger = get_logger()

    # Always disable telemetry and analytics
    os.environ[PREFECT_CLOUD_ENABLE_ORCHESTRATION_TELEMETRY] = "false"
    os.environ[PREFECT_SERVER_ANALYTICS_ENABLED] = "false"
    os.environ[PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS] = "120"

    # Route custom DOCPIPE application logs into Prefect Task/Flow Runs natively
    os.environ["PREFECT_LOGGING_EXTRA_LOGGERS"] = "DOCPIPE"

    prefect_mode = os.getenv(PREFECT_MODE, "ephemeral").lower()

    if prefect_mode == "server":
        # SERVER MODE: Use persistent Prefect server
        prefect_api_url = os.getenv(PREFECT_API_URL)

        if not prefect_api_url:
            logger.warning(
                "PREFECT_MODE=server but PREFECT_API_URL not set. "
                "Falling back to ephemeral mode. "
                "Set PREFECT_API_URL to use persistent Prefect server."
            )
            _configure_ephemeral_mode()
        else:
            logger.info(f"Using Prefect server mode with API URL: {prefect_api_url}")
            # In server mode, PREFECT_API_URL is already set
            # No need to set database connection or home directory
            # The server handles all persistence

    else:
        # EPHEMERAL MODE: In-memory SQLite (default)
        _configure_ephemeral_mode()


def _configure_ephemeral_mode() -> None:
    """Configure Prefect for ephemeral in-memory mode."""
    logger = get_logger()

    if not os.getenv(PREFECT_DEBUG):
        logger.info("Using Prefect ephemeral mode (in-memory SQLite)")
        # See https://github.com/PrefectHQ/prefect/issues/10188
        os.environ[PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED] = "False"
        # Create a temporary directory for Prefect Home
        os.environ[PREFECT_HOME] = tempfile.mkdtemp(prefix=PREFECT_HOME_PREFIX)
        os.environ[PREFECT_API_DATABASE_CONNECTION_URL] = "sqlite+aiosqlite:///:memory:"
    else:
        logger.info("Using Prefect debug mode (persistent SQLite)")


def clean_up_prefect_home() -> None:
    """
    Clean up temporary Prefect home directory.

    Removes the temporary directory created for Prefect unless PREFECT_DEBUG is set.
    Only cleans up in ephemeral mode.
    """
    prefect_mode = os.getenv(PREFECT_MODE, "ephemeral").lower()

    # Only cleanup in ephemeral mode
    if prefect_mode == "ephemeral":
        prefect_home = os.getenv(PREFECT_HOME)
        if prefect_home and not os.getenv(PREFECT_DEBUG):
            _safe_rmtree(path=prefect_home, prefix=PREFECT_HOME_PREFIX)


def _safe_rmtree(path: str, prefix: str | None = None) -> bool:
    """
    Safely remove a directory if it's inside the system temp directory
    and optionally matches a given prefix.

    Args:
        path (str): Directory to remove.
        prefix (str, optional): Require the basename of the directory
                                to start with this prefix (e.g., "prefect_").

    Returns:
        bool: True if the directory was removed, False otherwise.
    """
    logger = get_logger()
    path_obj = Path(path).resolve()
    temp_root_obj = Path(tempfile.gettempdir()).resolve()

    # Check: must be under system temp directory
    if temp_root_obj not in path_obj.parents and path_obj != temp_root_obj:
        logger.warning("Refusing to delete %s: not inside %s", path_obj, temp_root_obj)
        return False

    # Check: prefix (if given)
    if prefix and not path_obj.name.startswith(prefix):
        logger.warning("Refusing to delete %s: does not start with '%s'", path_obj, prefix)
        return False

    # Perform safe removal
    if path_obj.exists():
        shutil.rmtree(path_obj, ignore_errors=True)
        logger.info("Deleted tempdir: %s", path_obj)
        return True
    logger.info("Path does not exist: %s", path_obj)
    return False


__all__ = [
    "PREFECT_API_DATABASE_CONNECTION_URL",
    "PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED",
    "PREFECT_API_URL",
    "PREFECT_CLOUD_ENABLE_ORCHESTRATION_TELEMETRY",
    "PREFECT_DEBUG",
    "PREFECT_HOME",
    "PREFECT_HOME_PREFIX",
    "PREFECT_MODE",
    "PREFECT_SERVER_ANALYTICS_ENABLED",
    "PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS",
    "clean_up_prefect_home",
    "set_prefect_env_variables",
]
