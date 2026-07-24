"""
Operator Registry for Docpipe OSS Operators.

This module provides a frozenset-based registry of all docpipe (OSS) operators.
Operators are imported as class references for immediate access without runtime discovery.
"""

# ACL Operator
from docpipe.core.operators.acl.acl_operator import ACLOperator

# Storage Operators
from docpipe.core.operators.document_sets.document_set_operator import DocumentSetOperator

# Extract Operators
from docpipe.core.operators.extract.extract_operator import ExtractOperator

# Functional Operators
from docpipe.core.operators.functional.branching_operator import BranchingOperator
from docpipe.core.operators.functional.chunker import ChunkerOperator
from docpipe.core.operators.functional.doc_id_hash import DocIdHashOperator
from docpipe.core.operators.functional.embeddings.embeddings_operator import EmbeddingsOperator
from docpipe.core.operators.functional.entity_curation.entity_curation_operator import EntityCurationOperator
from docpipe.core.operators.functional.merge import MergeOperator
from docpipe.core.operators.functional.noop import NOOPOperator

# Ingest Operators
from docpipe.core.operators.ingest.ingest_local import IngestLocalOperator
from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

# Quality Operators
from docpipe.core.operators.quality.classification.document_classifier import DocumentClassifierOperator
from docpipe.core.operators.quality.doc_quality import DocQuality
from docpipe.core.operators.quality.ededup import EdedupOperator
from docpipe.core.operators.quality.language_detection.lang_id import LanguageDetect
from docpipe.core.operators.quality.ml_enrichment import MLEnrichmentOperator
from docpipe.core.operators.quality.pii_and_hap.pii_and_hap_annotator import PIIAndHAPAnnotator
from docpipe.core.operators.quality.readability import ReadabilityOperator
from docpipe.core.operators.quality.redaction import RedactionOperator
from docpipe.core.operators.quality.sql_filter import SQLFilterOperator

# VectorDB Operators
from docpipe.core.operators.vectordb.vectordb_operator import VectorDBOperator

# Frozenset of all docpipe (OSS) operators
# Contains direct class references for immediate access
DOCPIPE_OPERATORS = frozenset(
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
        EntityCurationOperator,
        MergeOperator,
        NOOPOperator,
        # Quality
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


def get_docpipe_operators() -> frozenset:
    """
    Returns the frozenset of all docpipe (OSS) operators.

    Returns:
        frozenset: Set of operator class references
    """
    return DOCPIPE_OPERATORS


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
    Returns the combined set of all operators (docpipe + custom).

    Returns:
        frozenset: Combined set of all operator class references
    """
    return DOCPIPE_OPERATORS | get_custom_operators()
