#!/usr/bin/env python3
"""
Example: PII and HAP Detection

This example demonstrates how to detect Personally Identifiable Information (PII)
and Hate, Abuse, and Profanity (HAP) in text content.
"""

import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docpipe.core.operators.quality.local_pii_hap_detect import detect_pii_hap


def main():  # pragma: no cover
    """Test PII and HAP detection with sample text."""
    request_data = {
        "input": (
            "My name is John Doe and I live in New York. "
            "My email is john.doe@example.com and my phone number is 000000000000."
        ),
        "detectors": {"hap": {"threshold": 0.8}, "pii": {"threshold": 0.5}},
    }
    result = detect_pii_hap(request_data)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
