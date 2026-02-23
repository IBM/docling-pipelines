# Operators

This package contains Python-based operator implementations for data processing tasks.

## Purpose
- Python operator implementations (non-Spark)
- Data transformation operators
- Validation operators
- Language processing operators
- Custom operator support

## Structure

### language/
Language processing operators:
- Language detection
- Text analysis
- NLP operations

### transform/
Data transformation operators:
- Data mapping
- Format conversion
- Data enrichment

### validation/
Data validation operators:
- Schema validation
- Data quality checks
- Business rule validation

### universal/
Universal operators that work across different contexts:
- **Ingest operators**: Document ingestion from cloud storage and collaboration platforms
  - [`IngestLangchainOperator`](universal/ingest/ingest_langchain_loader.py) - Multi-provider document ingestion (S3, IBM COS, SharePoint, OneDrive, Google Drive)
  - See [Ingest LangChain Loader Documentation](../../../docs/operators/ingest_langchain_loader.md)
- **Extract operators**: Content extraction and parsing
  - [`ExtractDoclingOperator`](universal/extract/extract_docling_operator.py) - Advanced document extraction
- Storage operations
- Data access
- Generic transformations

### custom/
Custom operator implementations:
- User-defined operators
- Plugin-based operators
- Extended functionality

## Note
This directory contains Python-only implementations. Spark-specific operators are excluded from this repository.