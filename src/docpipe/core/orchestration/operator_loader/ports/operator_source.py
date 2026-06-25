"""Port interface for operator source adapters.

This port defines the contract that all operator source adapters must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import ModuleType


@dataclass
class OperatorInfo:
    """Metadata about a discovered operator.

    Attributes:
        name: Full class name of the operator
        short_name: Short identifier used in flow definitions
        module_path: Python module path where operator is defined
        category: Operator category (Extract, Ingest, etc.)
        source_location: Original location where operator was found
    """

    name: str
    short_name: str
    module_path: str
    category: str
    source_location: str


@dataclass
class ValidationResult:
    """Result of operator validation.

    Attributes:
        valid: Whether the operator passed validation
        errors: List of validation error messages
        warnings: List of validation warning messages
    """

    valid: bool
    errors: list[str]
    warnings: list[str]


class OperatorSourcePort(ABC):
    """Port interface for operator source adapters.

    This interface defines the contract for discovering and loading custom operators
    from various sources (filesystem, S3, etc.). Adapters implementing this port
    handle source-specific details while the loader service depends only on this
    abstraction.

    Attributes:
        ADAPTER_NAME: Unique identifier for the adapter (e.g., 'filesystem', 's3')
        ADAPTER_DISPLAY_NAME: Human-readable name for UI display
    """

    ADAPTER_NAME: str
    ADAPTER_DISPLAY_NAME: str

    @abstractmethod
    def list_operators(self) -> list[OperatorInfo]:
        """Discover and list all available operators from this source.

        Returns:
            List of OperatorInfo objects for discovered operators

        Raises:
            Exception: If discovery operation fails
        """
        pass

    def clear_cache(self):
        """Clear any cached modules to force reloading.

        Optional method for adapters that cache loaded modules.
        Called before refresh operations to ensure updated code is loaded.
        """
        pass

    @abstractmethod
    def load_operator(self, *, operator_info: OperatorInfo) -> ModuleType:
        """Load operator module from this source.

        Args:
            operator_info: Metadata about the operator to load

        Returns:
            Loaded Python module containing the operator class

        Raises:
            Exception: If loading operation fails
        """
        pass

    @abstractmethod
    def validate_operator(self, *, module: ModuleType, operator_info: OperatorInfo) -> ValidationResult:
        """Validate operator implementation.

        Args:
            module: Loaded operator module
            operator_info: Metadata about the operator

        Returns:
            ValidationResult with validation status and messages

        Raises:
            Exception: If validation check fails
        """
        pass
