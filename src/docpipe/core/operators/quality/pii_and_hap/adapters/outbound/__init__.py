# Copyright IBM Corp. 2026
# SPDX-License-Identifier: Apache-2.0

"""Outbound adapters for PII and HAP detection.

Importing this package triggers auto-registration of all adapters with
PIIAndHAPDetectionFactory via the @register_pii_and_hap_detection_adapter decorator.
"""

from .litellm.adapter import LiteLLMPIIAndHAPAdapter
from .watsonx.adapter import WatsonxPIIAndHAPAdapter

__all__ = [
    "LiteLLMPIIAndHAPAdapter",
    "WatsonxPIIAndHAPAdapter",
]
