#!/usr/bin/env python3
"""
Sample script to test DatasiftFlowManager API.

This script demonstrates how to use the DatasiftFlowManager to:
1. List available operators
2. Validate a flow
3. Execute a flow
4. Access execution metadata and logs
"""

from pprint import pprint

from datasift_opensource.lib.datasift_flow_manager import DatasiftFlowManager  # type: ignore[import-not-found]


def main():
    # Example 1: List available operators
    print("=" * 80)
    print("LISTING AVAILABLE OPERATORS")
    print("=" * 80)
    operators = DatasiftFlowManager.list_operators(verbose=False)
    print(operators)
    print()

    # Example 2: Execute flow from file
    print("=" * 80)
    print("EXECUTING FLOW FROM FILE")
    print("=" * 80)
    
    # Update this path to point to your actual flow JSON file
    flow_file_path = "sample_flows/complete_pipeline_flow.json"
    
    try:
        # Initialize manager
        manager = DatasiftFlowManager(
            flow_file=flow_file_path,
            log_level="info",
        )

        # Validate flow before execution
        print("\nValidating flow...")
        validation = manager.validate()
        pprint(validation)

        if not validation.get("valid", False):
            raise RuntimeError(f"Flow validation failed: {validation}")

        print("\n✓ Flow validation passed!")

        # Execute the flow
        print("\nExecuting flow...")
        result = manager.execute()

        # Get execution metadata
        print("\n" + "=" * 80)
        print("EXECUTION METADATA")
        print("=" * 80)
        pprint(manager.get_execution_metadata())

        # Get execution logs
        print("\n" + "=" * 80)
        print("EXECUTION LOGS")
        print("=" * 80)
        logs = manager.get_execution_logs()
        if logs:
            for line in logs[:20]:  # Show first 20 lines
                print(line)
            if len(logs) > 20:
                print(f"\n... ({len(logs) - 20} more lines)")
        else:
            print("No logs available")

        # Access result data
        print("\n" + "=" * 80)
        print("RESULT DATA")
        print("=" * 80)
        print(f"Result object type: {type(result)}")
        if hasattr(result, "data") and result.data is not None:
            print(f"Result columns: {getattr(result.data, 'column_names', None)}")
            print(f"Result rows: {getattr(result.data, 'num_rows', None)}")
        else:
            print("No data available in result")

        print("\n✓ Flow execution completed successfully!")

    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
        print("\nPlease update the 'flow_file_path' variable to point to a valid flow JSON file.")
    except Exception as e:
        print(f"\n✗ Error during execution: {e}")
        import traceback
        traceback.print_exc()

    # Example 3: Validate flow from dictionary (without execution)
    print("\n" + "=" * 80)
    print("VALIDATING FLOW FROM DICTIONARY")
    print("=" * 80)
    
    # Simple example flow definition
    flow_dict = {
        "name": "Simple Ingest Flow",
        "description": "A simple flow that ingests documents from a folder",
        "storage": "in-memory",
        "execute_type": "local",
        "global_config": {
            "doc_column": "content",
            "disable_validation": "true",
            "force_ingest": True
        },
        "dag": [
            {
                "id": "f1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c",
                "name": "ingest",
                "operator": "ingest_local",
                "config": {
                    "input_folder": "./sample_documents",
                    "include_filter": "txt,pdf",
                    "store_binary_content": False
                },
                "input_edges": [],
                "output_edges": []
            }
        ]
    }
    
    try:
        manager = DatasiftFlowManager(flow_def=flow_dict, log_level="info")
        print("\nValidating flow from dictionary...")
        validation = manager.validate()
        pprint(validation)
        
        if validation.get("valid", False):
            print("\n✓ Flow validation passed!")
            print("Note: Execution skipped in this example. See Example 1 for full execution.")
        else:
            print("\n✗ Flow validation failed")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

