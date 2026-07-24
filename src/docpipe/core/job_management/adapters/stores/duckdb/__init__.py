"""
DuckDB storage adapter for job statistics.

Provides embedded database storage without requiring a separate database server.
"""

from .duckdb_job_stats_store import DuckDBJobStatsStore

__all__ = ["DuckDBJobStatsStore"]
