"""
Data Access Layer (DAL) for PostgreSQL job stats storage.

Provides CRUD operations for JobRunStats and NodeStats models.
"""

from .base_dao import BaseDAO
from .job_stats_dal import JobStatsDAL
from .node_stats_dal import NodeStatsDAL

__all__ = ["BaseDAO", "JobStatsDAL", "NodeStatsDAL"]
