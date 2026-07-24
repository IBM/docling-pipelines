"""Feature propagation module for flow validation.

This module provides classes and utilities for tracking features as they
propagate through DAG flows during validation.
"""

from docpipe.core.orchestration.feature_propagation.features_propagator import FeaturePropagator
from docpipe.core.orchestration.feature_propagation.models import (
    FeatureMetadata,
    FeaturePropagationResult,
    OutputFeaturesToDrop,
)

__all__ = [
    "FeatureMetadata",
    "FeaturePropagationResult",
    "FeaturePropagator",
    "OutputFeaturesToDrop",
]
