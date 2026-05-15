"""
Operator Registry for Datasift OSS Operators.

This module provides a frozenset-based registry of all datasift (OSS) operators.
Operators are imported as class references for immediate access without runtime discovery.
"""

# Extract Operators
# Storage Operators
from datasift.core.operators.document_sets.document_set_operator import DocumentSetOperator
from datasift.core.operators.extract.extract_operator import ExtractOperator

# Functional Operators
from datasift.core.operators.functional.branching_operator import BranchingOperator
from datasift.core.operators.functional.chunker import ChunkerOperator
from datasift.core.operators.functional.doc_id_hash import DocIdHashOperator
from datasift.core.operators.functional.embeddings.embeddings_operator import EmbeddingsOperator
from datasift.core.operators.functional.merge import MergeOperator
from datasift.core.operators.functional.noop import NOOPOperator

# Ingest Operators
from datasift.core.operators.ingest.ingest_local_folder import IngestLocalOperator
from datasift.core.operators.ingest.ingest_source import IngestSourceOperator

# Quality Operators
from datasift.core.operators.quality.classification.document_classifier import DocumentClassifierOperator
from datasift.core.operators.quality.ededup import EdedupOperator
from datasift.core.operators.quality.language_detection.lang_id import LanguageDetect
from datasift.core.operators.quality.ml_enrichment import MLEnrichmentOperator
from datasift.core.operators.quality.readability import ReadabilityOperator
from datasift.core.operators.quality.redaction import RedactionOperator
from datasift.core.operators.quality.sql_filter import SQLFilterOperator

# VectorDB Operators
from datasift.core.operators.vectordb.vectordb_operator import VectorDBOperator

# Frozenset of all datasift (OSS) operators
# Contains direct class references for immediate access
DATASIFT_OPERATORS = frozenset(
    {
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
        DocumentClassifierOperator,
        EdedupOperator,
        LanguageDetect,
        MLEnrichmentOperator,
        ReadabilityOperator,
        RedactionOperator,
        SQLFilterOperator,
        # VectorDB
        VectorDBOperator,
        # Storage
        DocumentSetOperator,
    }
)


def get_datasift_operators() -> frozenset:
    """
    Returns the frozenset of all datasift (OSS) operators.

    Returns:
        frozenset: Set of operator class references
    """
    return DATASIFT_OPERATORS


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
