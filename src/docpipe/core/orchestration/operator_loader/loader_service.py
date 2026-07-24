"""Custom operator loader service.

This service coordinates the discovery and loading of custom operators from
multiple sources.
"""

import inspect
from typing import Any

from docpipe.core.operators.abstract_operator import AbstractOperator
from docpipe.core.orchestration.operator_loader.adapters.factories.operator_source_factory import (
    OperatorSourceFactory,
)
from docpipe.core.orchestration.operator_loader.ports.operator_source import (
    OperatorInfo,
    OperatorSourcePort,
)
from docpipe.core.orchestration.operator_loader.validator import OperatorValidator
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class CustomOperatorLoader:
    """Service for loading custom operators from multiple sources.

    This service coordinates operator discovery, validation, and loading
    from various sources (filesystem directories, S3 buckets, Python packages)
    while handling conflicts and ensuring operator quality.

    Supported sources:
    - Filesystem: Local directories or files containing operators
    - S3: Amazon S3 buckets with operator files
    - Package: Pip-installed Python packages with operators
    """

    def __init__(self, sources: list[OperatorSourcePort]):
        """Initialize the loader with operator sources.

        Args:
            sources: List of operator source adapters to use
        """
        self.sources = sources
        self.loaded_operators: dict[str, type[AbstractOperator]] = {}

    @classmethod
    def from_source_configs(cls, source_configs: list[dict[str, Any]]) -> "CustomOperatorLoader":
        """Create loader from source configuration dictionaries.

        Args:
            source_configs: List of source configurations, each containing:
                - adapter_name: Name of the adapter to use
                - **kwargs: Adapter-specific configuration

        Returns:
            Initialized CustomOperatorLoader instance

        Example:
            configs = [
                {"adapter_name": "filesystem", "path": "/path/to/operators"},
                {"adapter_name": "s3", "bucket": "my-bucket", "prefix": "operators/"}
            ]
            loader = CustomOperatorLoader.from_source_configs(configs)
        """
        sources = []
        for config in source_configs:
            adapter_name = config.pop("adapter_name")
            source = OperatorSourceFactory.create(adapter_name, **config)
            sources.append(source)

        return cls(sources)

    @classmethod
    def from_paths(cls, paths: list[str]) -> "CustomOperatorLoader":
        """Create loader from path strings (auto-detect adapter type).

        Args:
            paths: List of paths (local filesystem paths or S3 URIs)

        Returns:
            Initialized CustomOperatorLoader instance

        Example:
            paths = ["/local/path", "s3://bucket/path"]
            loader = CustomOperatorLoader.from_paths(paths)
        """
        import os

        sources = []
        for path in paths:
            if path.startswith("s3://"):
                # S3 URI
                source = OperatorSourceFactory.create("s3", uri=path)
                sources.append(source)
            elif os.path.isabs(path) or os.path.exists(path) or "/" in path or "\\" in path:
                # Local filesystem path (absolute, exists, or contains path separators)
                source = OperatorSourceFactory.create("filesystem", path=path)
                sources.append(source)
            else:
                # Treat as Python package name
                try:
                    source = OperatorSourceFactory.create("package", package_name=path)
                    sources.append(source)
                except ImportError:
                    logger.warning(f"Skipping path '{path}': not a valid filesystem path, S3 URI, or installed package")

        return cls(sources)

    def discover_operators(
        self, *, clear_cache: bool = False
    ) -> tuple[dict[str, OperatorInfo], dict[str, OperatorSourcePort]]:
        """Discover operators from all sources.

        Args:
            clear_cache: If True, clear adapter caches before discovering (for refresh)

        Returns:
            Tuple containing:
            - Dictionary mapping short_name to OperatorInfo
            - Dictionary mapping source_location to OperatorSourcePort

        Note:
            If multiple sources provide operators with the same short_name,
            the first one discovered is used.
        """
        discovered: dict[str, OperatorInfo] = {}
        source_map: dict[str, OperatorSourcePort] = {}

        # Clear caches if requested (for refresh operations)
        if clear_cache:
            for source in self.sources:
                source.clear_cache()

        for source in self.sources:
            try:
                operators = source.list_operators()
                logger.info(f"Discovered {len(operators)} operators from {source.ADAPTER_DISPLAY_NAME}")

                for op_info in operators:
                    if op_info.short_name in discovered:
                        logger.warning(
                            f"Operator '{op_info.short_name}' already discovered from "
                            f"{discovered[op_info.short_name].source_location}. "
                            f"Skipping duplicate from {op_info.source_location}"
                        )
                        continue

                    discovered[op_info.short_name] = op_info
                    source_map[op_info.source_location] = source

            except Exception as e:
                logger.error(
                    f"Failed to discover operators from {source.ADAPTER_DISPLAY_NAME}: {e}",
                    exc_info=True,
                )

        return discovered, source_map

    def load_and_validate_operator(
        self,
        op_info: OperatorInfo,
        source: OperatorSourcePort,
    ) -> type[AbstractOperator] | None:
        """Load and validate a single operator.

        Args:
            op_info: Operator metadata
            source: Source adapter to load from

        Returns:
            Loaded operator class if valid, None otherwise
        """
        try:
            # Load the module
            module = source.load_operator(operator_info=op_info)

            # Validate the module
            validation_result = source.validate_operator(module=module, operator_info=op_info)

            # Log warnings
            for warning in validation_result.warnings:
                logger.warning(f"Operator '{op_info.short_name}': {warning}")

            # Check for errors
            if not validation_result.valid:
                for error in validation_result.errors:
                    logger.error(f"Operator '{op_info.short_name}': {error}")
                return None

            # Extract operator class from module
            operator_class = self._extract_operator_class(module, op_info)
            if operator_class is None:
                logger.error(f"Could not extract operator class from module {op_info.module_path}")
                return None

            return operator_class

        except Exception as e:
            logger.error(
                f"Failed to load operator '{op_info.short_name}' from {op_info.source_location}: {e}",
                exc_info=True,
            )
            return None

    def _extract_operator_class(
        self,
        module: Any,
        op_info: OperatorInfo,
    ) -> type[AbstractOperator] | None:
        """Extract operator class from loaded module.

        Args:
            module: Loaded Python module
            op_info: Operator metadata

        Returns:
            Operator class if found, None otherwise
        """
        for _, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, AbstractOperator)
                and obj is not AbstractOperator
                and obj.__module__ == module.__name__
            ):
                return obj

        return None

    def validate_and_load(
        self,
        builtin_operators: dict[str, type[AbstractOperator]],
        *,
        clear_cache: bool = False,
    ) -> dict[str, type[AbstractOperator]]:
        """Discover, validate, and load all custom operators.

        Args:
            builtin_operators: Dictionary of built-in operators (for conflict detection)
            clear_cache: If True, clear adapter caches before loading (for refresh)

        Returns:
            Dictionary of successfully loaded custom operators (short_name -> class)
        """
        # Discover operators from all sources
        discovered, source_map = self.discover_operators(clear_cache=clear_cache)

        if not discovered:
            logger.info("No custom operators discovered")
            return {}

        logger.info(f"Discovered {len(discovered)} custom operators")

        # Load and validate each operator
        loaded: dict[str, type[AbstractOperator]] = {}

        for short_name, op_info in discovered.items():
            # Check for duplicates in current batch
            duplicate_validation = OperatorValidator.validate_no_duplicate_in_batch(short_name, loaded)

            if not duplicate_validation.valid:
                for error in duplicate_validation.errors:
                    logger.warning(f"Skipping custom operator '{short_name}': {error}")
                continue

            # Get the source that provided this operator from the mapping
            source = source_map.get(op_info.source_location)

            if source is None:
                logger.error(
                    f"Could not find source for operator '{short_name}' "
                    f"with source_location '{op_info.source_location}'"
                )
                continue

            # Load and validate the operator
            operator_class = self.load_and_validate_operator(op_info, source)

            if operator_class is not None:
                loaded[short_name] = operator_class
                logger.info(
                    f"Successfully loaded custom operator: {short_name} "
                    f"({operator_class.__name__}) from {op_info.source_location}"
                )

        self.loaded_operators = loaded
        logger.info(f"Loaded {len(loaded)} custom operators successfully")

        return loaded
