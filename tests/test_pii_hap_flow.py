#!/usr/bin/env python3
"""Test script for PII and HAP detection operator."""

import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src" / "datasift_opensource" / "backend"))

from core.orchestrator.cmdline.cmd_line_orchestrator import run_command_line_executor


def test_pii_hap_with_ollama():
    """Test PII and HAP detection with Ollama."""

    # Set environment variables
    os.environ["test_mode"] = "True"
    os.environ["DATA_FOLDER"] = "/tmp/datasift_test"

    # Load the flow definition
    flow_file = project_root / "tests" / "flow_pii_hap_example.json"

    with open(flow_file, "r") as f:
        flow_config = json.load(f)

    flow_def = flow_config["flow"]

    print("=" * 80)
    print("Testing PII and HAP Detection Operator")
    print("=" * 80)
    print(f"\nFlow: {flow_def['name']}")
    print(f"Description: {flow_def['description']}")
    print(f"\nNodes in flow:")
    for node in flow_def["dag"]:
        print(f"  - {node['name']} ({node['operator']})")
    print("\n" + "=" * 80)
    print("Starting flow execution...")
    print("=" * 80 + "\n")

    try:
        # Run the flow
        result = run_command_line_executor(flow_def=flow_def)

        print("\n" + "=" * 80)
        print("Flow execution completed successfully!")
        print("=" * 80)

        return result

    except Exception as e:
        print("\n" + "=" * 80)
        print(f"Flow execution failed: {str(e)}")
        print("=" * 80)
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    test_pii_hap_with_ollama()

# Made with Bob
