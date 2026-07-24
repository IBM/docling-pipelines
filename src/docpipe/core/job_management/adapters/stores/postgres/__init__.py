"""
PostgreSQL adapter for job stats storage.

This package provides PostgreSQL-backed storage for job and node statistics,
following the enterprise DAL/DAO pattern adapted for open-source.
"""

from .postgres_job_stats_store import PostgresJobStatsStore

__all__ = ["PostgresJobStatsStore"]
