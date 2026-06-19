"""
Operator Registry for Datasift OSS Operators.

This module provides a frozenset-based registry of all datasift (OSS) operators.
Operators are imported as class references for immediate access without runtime discovery.
The registry supports external operator providers through a plugin hook pattern,
allowing host applications to inject their own operators at runtime.
"""

# ACL Operator
from datasift.core.operators.acl.acl_operator import ACLOperator

# Storage Operators
from datasift.core.operators.document_sets.document_set_operator import DocumentSetOperator

# Extract Operators
from datasift.core.operators.extract.extract_operator import ExtractOperator
from datasift.core.operators.functional import EntityCurationOperator

# Functional Operators
from datasift.core.operators.functional.branching_operator import BranchingOperator
from datasift.core.operators.functional.chunker import ChunkerOperator
from datasift.core.operators.functional.doc_id_hash import DocIdHashOperator
from datasift.core.operators.functional.embeddings.embeddings_operator import EmbeddingsOperator
from datasift.core.operators.functional.merge import MergeOperator
from datasift.core.operators.functional.noop import NOOPOperator

# Ingest Operators
from datasift.core.operators.ingest.ingest_local import IngestLocalOperator
from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

# Quality Operators
from datasift.core.operators.quality.classification.document_classifier import DocumentClassifierOperator
from datasift.core.operators.quality.doc_quality import DocQuality
from datasift.core.operators.quality.ededup import EdedupOperator
from datasift.core.operators.quality.language_detection.lang_id import LanguageDetect
from datasift.core.operators.quality.ml_enrichment import MLEnrichmentOperator
from datasift.core.operators.quality.pii_and_hap.pii_and_hap_annotator import PIIAndHAPAnnotator
from datasift.core.operators.quality.readability import ReadabilityOperator
from datasift.core.operators.quality.redaction import RedactionOperator
from datasift.core.operators.quality.sql_filter import SQLFilterOperator

# VectorDB Operators
from datasift.core.operators.vectordb.vectordb_operator import VectorDBOperator

# Frozenset of all datasift (OSS) operators
# Contains direct class references for immediate access
DATASIFT_OPERATORS = frozenset(
    {
        # ACL
        ACLOperator,
        # Extract
        ExtractOperator,
        # Ingest
        IngestLocalOperator,
        IngestSourceOperator,
        # Functional
        BranchingOperator,
        ChunkerOperator,
        DocIdHashOperator,
        EmbeddingsOperator,
        MergeOperator,
        NOOPOperator,
        # Quality
        EntityCurationOperator,
        DocumentClassifierOperator,
        DocQuality,
        EdedupOperator,
        LanguageDetect,
        MLEnrichmentOperator,
        PIIAndHAPAnnotator,
        ReadabilityOperator,
        RedactionOperator,
        SQLFilterOperator,
        # VectorDB
        VectorDBOperator,
        # Storage
        DocumentSetOperator,
    }
)

# Global registry for external operator providers
# Each provider is a callable that accepts orchestrator parameter and returns a frozenset
_EXTERNAL_OPERATOR_PROVIDERS: list = []


def register_operator_provider(provider_func):
    """
    Register an external operator provider function.

    This allows external applications (that install datasift as a wheel) to inject
    their own operators into the registry. The provider function will be called
    when get_datasift_operators() is invoked.

    Args:
        provider_func: Callable that returns frozenset of operator classes
                      Signature: provider_func(orchestrator: str | None = None) -> frozenset

    Raises:
        TypeError: If provider_func is not callable

    Example:
        # In external application that installs datasift-opensource wheel:
        from datasift.core.operators.operator_registry import register_operator_provider

        def my_app_operators(orchestrator=None):
            from my_app.operators import APP_OPERATORS
            return APP_OPERATORS

        # Register at application startup
        register_operator_provider(my_app_operators)
    """
    if not callable(provider_func):
        raise TypeError(f"Provider must be callable, got {type(provider_func).__name__}")

    _EXTERNAL_OPERATOR_PROVIDERS.append(provider_func)


def clear_operator_providers():
    """
    Clear all registered operator providers.

    Useful for testing or resetting the registry state.
    """
    _EXTERNAL_OPERATOR_PROVIDERS.clear()


def get_registered_provider_count() -> int:
    """
    Get the number of registered external operator providers.

    Returns:
        int: Number of registered providers
    """
    return len(_EXTERNAL_OPERATOR_PROVIDERS)


def get_datasift_operators(*, orchestrator: str | None = None) -> frozenset:
    """
    Returns the frozenset of all datasift operators merged with external providers.

    This function collects operators from:
    1. Base DATASIFT_OPERATORS (OSS operators)
    2. All registered external provider functions

    Note: This function does NOT apply priority resolution or deduplication.
    That responsibility belongs to OperatorFactory, which handles operator
    loading and priority-based conflict resolution.

    Args:
        orchestrator: Optional orchestrator type (e.g., "python", "spark") for filtering

    Returns:
        frozenset: Combined set of all operator class references (may contain duplicates by short_name)

    Example:
        # Get all operators
        operators = get_datasift_operators()

        # Get operators for specific orchestrator
        python_operators = get_datasift_operators(orchestrator="python")
    """
    from datasift.utils.infrastructure.logging import get_logger

    logger = get_logger()

    # Start with base datasift operators
    operators = set(DATASIFT_OPERATORS)
    logger.debug(f"Starting with {len(operators)} base datasift operators")

    # Collect operators from all registered providers
    for idx, provider_func in enumerate(_EXTERNAL_OPERATOR_PROVIDERS):
        try:
            logger.debug(
                f"Calling external provider {idx + 1}/{len(_EXTERNAL_OPERATOR_PROVIDERS)}: {provider_func.__name__}"
            )
            external_ops = provider_func(orchestrator=orchestrator)

            if isinstance(external_ops, frozenset):
                operators.update(external_ops)
                logger.info(f"Added {len(external_ops)} operators from provider '{provider_func.__name__}'")
            else:
                logger.warning(
                    f"Provider '{provider_func.__name__}' returned {type(external_ops).__name__}, "
                    f"expected frozenset. Skipping."
                )
        except Exception as e:
            logger.error(f"Error calling operator provider '{provider_func.__name__}': {e}", exc_info=True)

    logger.info(f"Returning {len(operators)} total operators (base + external, before priority resolution)")
    return frozenset(operators)


def get_custom_operators() -> frozenset:
    """
    Returns the frozenset of custom operators.

    In the OSS version, this returns an empty frozenset.
    Custom operators are loaded dynamically via package paths.

    Returns:
        frozenset: Empty set (no custom operators in OSS)
    """
    return frozenset()


def get_all_operators() -> frozenset:
    """
    Returns the combined set of all operators (datasift + custom).

    Returns:
        frozenset: Combined set of all operator class references
    """
    return DATASIFT_OPERATORS | get_custom_operators()
