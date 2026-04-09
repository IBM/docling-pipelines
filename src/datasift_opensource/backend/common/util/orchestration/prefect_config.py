"""Prefect configuration and environment setup utilities."""

import os
import shutil
import tempfile

from common.util.infrastructure.logging import get_logger

PREFECT_HOME_PREFIX = "prefect_"
PREFECT_HOME = "PREFECT_HOME"
PREFECT_API_DATABASE_CONNECTION_URL = "PREFECT_API_DATABASE_CONNECTION_URL"
PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED = "PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED"
PREFECT_CLOUD_ENABLE_ORCHESTRATION_TELEMETRY = "PREFECT_CLOUD_ENABLE_ORCHESTRATION_TELEMETRY"
PREFECT_SERVER_ANALYTICS_ENABLED = "PREFECT_SERVER_ANALYTICS_ENABLED"
PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS = "PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS"
# Set to "true" to use SQLite with persistent storage and the default Prefect home directory.
# Allows accessing Prefect dashboard for flows review.
PREFECT_DEBUG = "PREFECT_DEBUG"


def set_prefect_env_variables() -> None:
    """
    Configure Prefect environment variables for optimal operation.

    Sets up Prefect to use in-memory SQLite database and disables telemetry
    unless PREFECT_DEBUG is set.
    """
    os.environ[PREFECT_CLOUD_ENABLE_ORCHESTRATION_TELEMETRY] = "false"
    os.environ[PREFECT_SERVER_ANALYTICS_ENABLED] = "false"
    os.environ[PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS] = "120"
    if not os.getenv(PREFECT_DEBUG):
        # See https://github.com/PrefectHQ/prefect/issues/10188
        os.environ[PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED] = "False"
        # Create a temporary directory for Prefect Home
        os.environ[PREFECT_HOME] = tempfile.mkdtemp(prefix=PREFECT_HOME_PREFIX)
        # force Prefect to use an in-memory SQLite DB
        os.environ[PREFECT_API_DATABASE_CONNECTION_URL] = "sqlite+aiosqlite:///:memory:"


def clean_up_prefect_home() -> None:
    """
    Clean up temporary Prefect home directory.

    Removes the temporary directory created for Prefect unless PREFECT_DEBUG is set.
    """
    prefect_home = os.getenv(PREFECT_HOME)
    if prefect_home and not os.getenv(PREFECT_DEBUG):
        _safe_rmtree(path=prefect_home, prefix=PREFECT_HOME_PREFIX)


def _safe_rmtree(path: str, prefix: str = None) -> bool:
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
    path = os.path.abspath(path)
    temp_root = os.path.abspath(tempfile.gettempdir())

    # Check: must be under system temp directory
    if os.path.commonpath([path, temp_root]) != temp_root:
        logger.warning(f"Refusing to delete {path}: not inside {temp_root}")
        return False

    # Check: prefix (if given)
    if prefix and not os.path.basename(path).startswith(prefix):
        logger.warning(f"Refusing to delete {path}: does not start with '{prefix}'")
        return False

    # Perform safe removal
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)
        logger.info(f"Deleted tempdir: {path}")
        return True
    else:
        logger.info(f"Path does not exist: {path}")
        return False


__all__ = [
    "PREFECT_API_DATABASE_CONNECTION_URL",
    "PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED",
    "PREFECT_CLOUD_ENABLE_ORCHESTRATION_TELEMETRY",
    "PREFECT_DEBUG",
    "PREFECT_HOME",
    "PREFECT_HOME_PREFIX",
    "PREFECT_SERVER_ANALYTICS_ENABLED",
    "PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS",
    "clean_up_prefect_home",
    "set_prefect_env_variables",
]

# Made with Bob
