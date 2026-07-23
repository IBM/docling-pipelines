"""
BatchExecutionFactory - Factory for creating batch execution strategies.

This factory creates the appropriate strategy based on configuration, enabling
seamless switching between local (ThreadPool) and distributed (WorkPool) execution.

Features:
- Configuration-based strategy selection from flow JSON
- Auto-fallback: If distributed execution is requested but Prefect Server
  is unavailable, gracefully degrades to local ThreadPoolAdapter with a warning
- Supports Prefect work pool types (process, docker)
"""

from typing import Any

from docpipe.core.orchestration.prefect.adapters.thread_pool_adapter import ThreadPoolAdapter
from docpipe.core.orchestration.prefect.adapters.work_pool_adapter import WorkPoolAdapter
from docpipe.core.orchestration.prefect.domain.models import (
    BatchStrategyConstants,
    ExecutionStrategyType,
)
from docpipe.core.orchestration.prefect.ports.batch_execution_port import BatchExecutionPort
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class BatchExecutionFactory:
    """
    Factory for creating batch execution strategies.

    Supports configuration-based strategy selection with fallback to defaults.
    Configuration can come from multiple sources (in order of precedence):
    1. Flow JSON configuration (highest priority)
    2. Environment variables (DOCPIPE_PREFECT_*)
    3. docling-pipelines-config.yaml configuration file
    4. Code defaults (lowest priority)

    Example configurations:

    ThreadPool (local execution — default):
    {
        "prefect": {
            "batch_execution": {
                "strategy": "thread-pool"
            }
        }
    }

    WorkPool with shared filesystem (Docker Compose):
    {
        "prefect": {
            "batch_execution": {
                "strategy": "work-pool-process",
                "work_pool_name": "docpipe-pool",
                "batch_storage": {
                    "type": "local",
                    "path": "/data/batches"
                }
            }
        }
    }

    WorkPool with S3 (cross-machine distributed):
    {
        "prefect": {
            "batch_execution": {
                "strategy": "work-pool-process",
                "work_pool_name": "docpipe-pool",
                "batch_storage": {
                    "type": "s3",
                    "bucket": "my-docpipe-batches",
                    "prefix": "tmp/batches/"
                }
            }
        }
    }
    """

    @staticmethod
    def create_strategy(*, config: dict[str, Any], prefect_engine, batch_manager) -> BatchExecutionPort:
        """
        Create appropriate batch execution strategy based on configuration.

        Includes auto-fallback: if a work pool strategy is requested but
        Prefect Server is not accessible, falls back to ThreadPoolAdapter
        with a warning instead of failing.

        Args:
            config: Configuration dictionary containing Prefect settings
            prefect_engine: PrefectEngine instance
            batch_manager: BatchManager instance

        Returns:
            BatchExecutionPort instance (ThreadPoolAdapter or WorkPoolAdapter)

        Raises:
            ValueError: If strategy type is invalid or required config is missing
        """
        # Extract Prefect configuration
        prefect_config = config.get("prefect", {})
        batch_exec_config = prefect_config.get("batch_execution", {})

        # Get strategy type (default to thread-pool for backward compatibility)
        strategy_type = batch_exec_config.get("strategy", ExecutionStrategyType.THREAD_POOL.value)

        logger.info(f"Creating batch execution strategy: {strategy_type}", extra={"strategy_type": strategy_type})

        # Create strategy based on type
        if strategy_type == ExecutionStrategyType.THREAD_POOL.value:
            return BatchExecutionFactory._create_thread_pool_strategy(
                config=batch_exec_config, prefect_engine=prefect_engine, batch_manager=batch_manager
            )

        # Match any work-pool-* strategy type
        if strategy_type.startswith("work-pool-"):
            return BatchExecutionFactory._create_work_pool_strategy_with_fallback(
                config=batch_exec_config,
                strategy_type=strategy_type,
                prefect_engine=prefect_engine,
                batch_manager=batch_manager,
            )

        raise ValueError(
            f"Invalid batch execution strategy: {strategy_type}. "
            f"Valid options: {[e.value for e in ExecutionStrategyType]}"
        )

    @staticmethod
    def _create_thread_pool_strategy(*, config: dict[str, Any], prefect_engine, batch_manager) -> ThreadPoolAdapter:
        """
        Create ThreadPoolAdapter with configuration.

        Args:
            config: Strategy-specific configuration
            prefect_engine: PrefectEngine instance
            batch_manager: BatchManager instance

        Returns:
            ThreadPoolAdapter instance

        Note:
            ThreadPoolAdapter uses PrefectEngine's existing ThreadPoolTaskRunner
            configuration. The max_workers setting is controlled by PrefectEngine's
            task_runner configuration, not by the strategy itself.
        """
        logger.info("Creating ThreadPoolAdapter (uses PrefectEngine's task_runner config)")

        return ThreadPoolAdapter(prefect_engine=prefect_engine, batch_manager=batch_manager)

    @staticmethod
    def _create_work_pool_strategy_with_fallback(
        *, config: dict[str, Any], strategy_type: str, prefect_engine, batch_manager
    ) -> BatchExecutionPort:
        """
        Create WorkPoolAdapter with auto-fallback to ThreadPoolAdapter.

        If the WorkPoolAdapter cannot be created (e.g., Prefect Server is
        not accessible), falls back to ThreadPoolAdapter with a warning.

        Args:
            config: Strategy-specific configuration
            strategy_type: The work pool strategy type string
            prefect_engine: PrefectEngine instance
            batch_manager: BatchManager instance

        Returns:
            WorkPoolAdapter if Prefect Server is available, otherwise ThreadPoolAdapter
        """
        work_pool_name = config.get("work_pool_name")
        if not work_pool_name:
            raise ValueError(
                "work_pool_name is required for work pool strategies. "
                "Add 'work_pool_name' to prefect.batch_execution configuration."
            )

        # Extract work pool type from strategy name: "work-pool-docker" → "docker"
        work_pool_type = strategy_type.replace("work-pool-", "")

        # Build work pool configuration
        # The config dict is passed directly to WorkPoolAdapter, which uses
        # create_work_pool_config() to filter and create typed dataclass configs
        work_pool_config = {
            "type": work_pool_type,
            "work_pool_name": work_pool_name,
            "deployment_name": config.get("deployment_name", BatchStrategyConstants.DEFAULT_DEPLOYMENT_NAME),
            BatchStrategyConstants.CONFIG_KEY_BATCH_STORAGE: config.get(
                BatchStrategyConstants.CONFIG_KEY_BATCH_STORAGE, {}
            ),
            **config,  # Pass all config keys; create_work_pool_config() will filter to valid fields
        }

        logger.info(
            f"Creating WorkPoolAdapter: "
            f"type={work_pool_type}, "
            f"work_pool={work_pool_name}, "
            f"deployment={work_pool_config.get('deployment_name', 'default')}",
        )

        try:
            return WorkPoolAdapter(
                work_pool_config=work_pool_config, prefect_engine=prefect_engine, batch_manager=batch_manager
            )
        except (ValueError, Exception) as e:
            # Auto-fallback to ThreadPoolAdapter
            logger.warning(
                f"Could not create WorkPoolAdapter: {e}. "
                f"Falling back to ThreadPoolAdapter (local execution). "
                f"To enable distributed execution, ensure Prefect Server is "
                f"running and accessible. Run: "
                f"docker-compose -f docker/docker-compose.distributed.yml up -d",
                exc_info=True,
            )

            return ThreadPoolAdapter(prefect_engine=prefect_engine, batch_manager=batch_manager)

    @staticmethod
    def get_default_strategy(*, prefect_engine, batch_manager) -> BatchExecutionPort:
        """
        Get default strategy (ThreadPoolAdapter) for backward compatibility.

        Args:
            prefect_engine: PrefectEngine instance
            batch_manager: BatchManager instance

        Returns:
            ThreadPoolAdapter with default configuration
        """
        logger.info("Using default batch execution strategy: ThreadPoolAdapter")

        return ThreadPoolAdapter(prefect_engine=prefect_engine, batch_manager=batch_manager)
