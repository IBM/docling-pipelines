"""
Framework Adapters - Pluggable job execution frameworks

This module contains concrete implementations of the JobRunManager port.

Available Implementations:
- DefaultJobRunManager: Simple synchronous execution (development/testing)


- KubernetesJobRunManager: Execute jobs as Kubernetes Jobs (production)
- NomadJobRunManager: Execute jobs in Nomad (production)
- CeleryJobRunManager: Execute jobs via Celery tasks (distributed)
"""

from .default_job_run_manager import DefaultJobRunManager

__all__ = [
    "DefaultJobRunManager",
]
