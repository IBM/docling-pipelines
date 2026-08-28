"""
Prefect-specific orchestration components.

This package contains all Prefect-related functionality including:
- PrefectEngine: Core Prefect flow execution engine (implements FlowEnginePort)
- Batch Strategies: Different strategies for executing batches (local vs distributed)

Note: ExecuteStepResults has been moved to docpipe.core.orchestration.ports.flow_engine
      for proper hexagonal architecture separation.
"""

# Re-export ExecuteStepResults from ports for backward compatibility
from docpipe.core.orchestration.ports.flow_engine import ExecuteStepResults
from docpipe.core.orchestration.prefect.prefect_engine import PrefectEngine

__all__ = [
    "ExecuteStepResults",
    "PrefectEngine",
]
