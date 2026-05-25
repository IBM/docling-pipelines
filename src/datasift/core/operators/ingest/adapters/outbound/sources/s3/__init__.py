"""S3 source adapter for document ingestion."""

from datasift.core.operators.ingest.adapters.outbound.sources.s3.adapter import S3SourceAdapter
from datasift.core.operators.ingest.adapters.outbound.sources.s3.config import S3SourceConfig

__all__ = ["S3SourceAdapter", "S3SourceConfig"]
