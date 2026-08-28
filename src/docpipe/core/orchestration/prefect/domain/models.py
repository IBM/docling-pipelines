"""
Domain models for Prefect batch execution.

Defines the core domain concepts for batch execution strategies,
including execution modes, work pool types, and storage configurations.
"""

import os
from enum import StrEnum

from docpipe.core.constants import EnvironmentVariables


class ExecutionStrategyType(StrEnum):
    """
    Enumeration of available batch execution strategies.

    Values are used for:
    - Strategy identification in logs
    - Configuration-based strategy selection (JSON config values)
    - Factory pattern strategy creation

    Values use lowercase-kebab-case to match JSON config convention.
    """

    # Local execution using ThreadPoolTaskRunner
    THREAD_POOL = "thread-pool"

    # Distributed execution via Prefect work pools
    WORK_POOL_PROCESS = "work-pool-process"
    WORK_POOL_DOCKER = "work-pool-docker"


class ExecutionMode(StrEnum):
    """
    High-level execution mode configuration.

    Used in configuration files and environment variables to specify
    whether to use local or distributed execution.
    """

    # Local execution (ThreadPoolStrategy)
    LOCAL = "local"

    # Distributed execution (WorkPoolStrategy)
    DISTRIBUTED = "distributed"


class WorkPoolType(StrEnum):
    """
    Prefect work pool types.

    Maps to Prefect's work pool infrastructure types.
    See: https://docs.prefect.io/concepts/work-pools/
    """

    PROCESS = "process"
    DOCKER = "docker"


class BatchStorageType(StrEnum):
    """
    Batch data storage type for transferring data between submitter and workers.

    Determines how batch data (PyArrow tables) is transferred:
    - INLINE: Serialized as JSON in Prefect parameters (small batches only, <512KB)
    - LOCAL: Written to shared local filesystem (Docker Compose / same machine)
    - S3: Written to S3-compatible object storage (cross-machine, production)
    """

    INLINE = "inline"
    LOCAL = "local"
    S3 = "s3"


class BatchStrategyConstants:
    """
    Constants for batch execution strategy configuration.
    """

    # Default deployment settings for batch subflows
    DEFAULT_DEPLOYMENT_NAME = "docpipe-batch-subflow"
    DEFAULT_DEPLOYMENT_PATH = "/opt/app-root/src"

    # Configuration keys
    CONFIG_KEY_TYPE = "type"
    CONFIG_KEY_WORK_POOL_NAME = "work_pool_name"
    CONFIG_KEY_DEPLOYMENT_NAME = "deployment_name"

    # Batch storage configuration keys
    CONFIG_KEY_BATCH_STORAGE = "batch_storage"
    CONFIG_KEY_BATCH_STORAGE_TYPE = "type"
    CONFIG_KEY_BATCH_STORAGE_PATH = "path"
    CONFIG_KEY_BATCH_STORAGE_BUCKET = "bucket"
    CONFIG_KEY_BATCH_STORAGE_PREFIX = "prefix"
    CONFIG_KEY_BATCH_STORAGE_ACCESS_KEY = "access_key"
    CONFIG_KEY_BATCH_STORAGE_SECRET_KEY = (
        "secret_key"  # pragma: allowlist secret  # nosec B105 — config key name string, not a real credential
    )
    CONFIG_KEY_BATCH_STORAGE_ENDPOINT_URL = "endpoint_url"
    CONFIG_KEY_BATCH_STORAGE_REGION = "region"

    # Flow names
    BATCH_SUBFLOW_NAME = "docpipe-batch-subflow"

    # Default Prefect parameter limit (512KB)
    DEFAULT_INLINE_SIZE_LIMIT_BYTES = 524288
    INLINE_SIZE_WARNING_THRESHOLD = 0.8  # Warn at 80% of limit

    @staticmethod
    def get_inline_size_limit() -> int:
        """
        Get the current Prefect server max parameter size limit.

        The limit can be configured via Prefect settings or the
        PREFECT_SERVER_API_MAX_PARAMETER_SIZE environment variable.
        Falls back to default (512 KB) if not configured.

        Returns:
            int: Maximum parameter size in bytes
        """
        from prefect.settings import get_current_settings

        # 1. Try to get from Prefect settings (if registered in this version)
        try:
            settings = get_current_settings()
            # Some versions might have it in server.api.max_parameter_size
            if hasattr(settings, "server") and hasattr(settings.server, "api"):
                limit = getattr(settings.server.api, "max_parameter_size", None)
                if limit is not None and isinstance(limit, int) and limit > 0:
                    return limit
        except Exception:  # nosec B110 — intentional: probing Prefect settings is best-effort; any version/attribute error falls through to next strategy
            pass

        # 2. Fallback to EnvironmentVariables constant (os.environ)
        try:
            env_value = os.environ.get(EnvironmentVariables.PREFECT_SERVER_API_MAX_PARAMETER_SIZE)
            if env_value is not None:
                limit = int(env_value)
                if limit > 0:
                    return limit
        except (ValueError, TypeError):
            pass

        return BatchStrategyConstants.DEFAULT_INLINE_SIZE_LIMIT_BYTES
