"""
DocpipeFlowManager Example 6: Basic Test with Auto-Generated Data

This example demonstrates a complete test workflow that creates its own test data,
executes a pipeline, and cleans up afterwards. Similar to 00_complete_example.py
but with more detailed logging and result inspection.

Prerequisites:
- Virtual environment activated: source .venv/bin/activate
- PYTHONPATH set: export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
- Ollama running with granite4 model: http://localhost:11434

Setup (from repository root):
    python3.12 -m venv .venv
    source .venv/bin/activate
    uv sync --extra dev
    export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"

    # Pull the embedding model (first time only)
    ollama pull granite4

Run:
    source .venv/bin/activate
    export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
    python examples/docpipe_flow_manager/06_basic_test.py
"""

import shutil
import sys
from pathlib import Path

from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager


def create_test_data():
    """Create test directory and sample text file"""
    test_dir = Path("./test_data")
    test_dir.mkdir(exist_ok=True)

    # Create a sample text file
    sample_file = test_dir / "sample_document.txt"
    sample_content = """
# Sample Document for Testing

This is a test document to validate the DocpipeFlowManager functionality.

## Introduction
The docling-pipelines project is a modular, operator-based data processing framework
designed for building flexible data pipelines. It provides a comprehensive set of operators
for ingesting, extracting, chunking, and embedding documents.

## Key Features
- Operator-based architecture with 17+ specialized operators
- PyArrow data format for efficient memory usage
- DAG-based workflow execution
- Prefect orchestration for parallel processing
- Modern AI/ML integrations with Ollama and OpenSearch

## Use Cases
This framework is ideal for:
1. Document processing pipelines
2. RAG (Retrieval-Augmented Generation) preparation
3. Entity extraction workflows
4. Vector search implementations

## Conclusion
The DocpipeFlowManager provides a simple interface to execute complex data processing
workflows defined in JSON configuration files.
"""

    sample_file.write_text(sample_content)
    print(f"Created test data directory: {test_dir}")
    print(f"Created sample file: {sample_file}")

    return test_dir


def cleanup_test_data(test_dir):
    """Remove test directory and files"""
    if test_dir.exists():
        shutil.rmtree(test_dir)
        print(f"Cleaned up test directory: {test_dir}")


def main():
    """Main test execution function"""
    test_dir = None

    try:
        print("=" * 80)
        print("Starting DocpipeFlowManager Test")
        print("=" * 80)

        # Step 1: Create test data
        print("\n[Step 1] Creating test data...")
        test_dir = create_test_data()

        # Step 2: Initialize DocpipeFlowManager
        print("\n[Step 2] Initializing DocpipeFlowManager...")
        flow_file = Path(__file__).parent / "06_basic_test_flow.json"

        if not flow_file.exists():
            raise FileNotFoundError(f"Flow file not found: {flow_file}")

        print(f"Loading flow from: {flow_file}")
        manager = DocpipeFlowManager(flow_file=str(flow_file))

        # Step 3: Get metadata before execution
        print("\n[Step 3] Flow Metadata:")
        metadata = manager.get_execution_metadata()
        print(f"  Flow Name: {metadata['flow_name']}")
        print(f"  Description: {metadata['flow_description']}")
        print(f"  Number of Operators: {metadata['num_operators']}")
        print(f"  Job ID: {metadata['job_id']}")
        print(f"  Job Run ID: {metadata['job_run_id']}")

        # Step 4: Execute the flow
        print("\n[Step 4] Executing flow...")
        print("Flow: ingest -> extract -> chunk -> embeddings")
        print("This may take a few moments...")

        manager.execute()

        # Step 5: Check execution status
        print("\n[Step 5] Execution Results:")
        print("=" * 80)

        # Get execution status from job stats service
        status = None
        if manager.orchestrator:
            job_stats_service = getattr(manager.orchestrator, "job_stats_service", None)
            if job_stats_service:
                try:
                    job_stats = job_stats_service.get_job_run_stats(job_run_id=manager.job_run_id)
                    if job_stats and hasattr(job_stats, "status"):
                        status = job_stats.status
                except Exception as e:
                    print(f"Warning: Could not retrieve job status: {e}")

        if status:
            print(f"Status: {status}")

            if status == "Completed":
                print("\nExecution completed successfully!")
                print(f"Job Run ID: {metadata['job_run_id']}")
                print(f"Results saved to: ./data/UDP_logs/{metadata['job_id']}/{metadata['job_run_id']}/")
            elif status == "Failed":
                print("\nExecution failed. Check logs for details.")
            else:
                print(f"\nExecution ended with status: {status}")
        else:
            print("Status: Unable to determine")

        print("\n" + "=" * 80)
        print("Test completed successfully!")
        print("=" * 80)

    except FileNotFoundError as e:
        print(f"File not found: {e}")
        sys.exit(1)

    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure all dependencies are installed and PYTHONPATH is set correctly")
        sys.exit(1)

    except ConnectionError as e:
        print(f"Connection error: {e}")
        print("Make sure Ollama is running on http://localhost:11434")
        print("You can start it with: ollama serve")
        sys.exit(1)

    except Exception as e:
        print(f"Unexpected error during execution: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    finally:
        # Step 6: Cleanup
        if test_dir:
            print("\n[Step 6] Cleaning up test data...")
            cleanup_test_data(test_dir)


if __name__ == "__main__":
    main()
