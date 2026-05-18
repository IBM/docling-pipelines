#!/usr/bin/env python3
"""Test script for PII and HAP detection operator."""

import os
from pathlib import Path

# Path setup is now automatic via conftest.py
from datasift.cli.datasift_cli import load_flow_definition, run_command_line_executor


def test_pii_hap_with_ollama():
    """Test PII and HAP detection with Ollama."""

    # Set environment variables
    os.environ["test_mode"] = "True"
    os.environ["DATA_FOLDER"] = "/tmp/datasift_test"

    # Load and compile the flow definition (authoring format -> runtime DAG)
    # Navigate: tests/unit/operators/pii_and_hap -> tests (up 3 levels using resolve().parents)
    tests_root = Path(__file__).resolve().parents[3]
    flow_file = tests_root / "sample_test_flows" / "quality_and_enrichment" / "flow_pii_hap_example.json"

    # load_flow_definition compiles authoring format to runtime DAG format
    flow_def = load_flow_definition(file_path=str(flow_file))

    # Fix the input_folder path to be absolute
    project_root = Path(__file__).resolve().parents[4]
    for node in flow_def["dag"]:
        if node.get("operator") == "ingest_local" and "input_folder" in node.get("config", {}):
            relative_path = node["config"]["input_folder"]
            absolute_path = str(project_root / relative_path)
            node["config"]["input_folder"] = absolute_path
            print(f"Updated input_folder to: {absolute_path}")

    print("=" * 80)
    print("Testing PII and HAP Detection Operator")
    print("=" * 80)
    print(f"\nFlow: {flow_def.get('name', 'Unknown')}")
    print(f"Description: {flow_def.get('description', 'N/A')}")
    print("\nNodes in flow:")
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
        print(f"Flow execution failed: {e!s}")
        print("=" * 80)
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    test_pii_hap_with_ollama()
