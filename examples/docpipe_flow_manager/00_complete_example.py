"""
DocpipeFlowManager Complete Example - START HERE!

This is the recommended starting point for learning DocpipeFlowManager.
It demonstrates a complete, working pipeline that:
1. Creates test data automatically
2. Executes a full pipeline (ingest -> extract -> chunk -> embeddings)
3. Shows execution metadata and results
4. Cleans up after execution

Prerequisites:
- Backend virtual environment activated: source src/docpipe_app/backend/.venv/bin/activate
- PYTHONPATH set to backend directory: export PYTHONPATH="$(pwd)/src/docpipe_app/backend:${PYTHONPATH}"
- Ollama running with nomic-embed-text model: http://localhost:11434

Setup (from repository root):
    cd src/docpipe_app/backend
    python3.12 -m venv .venv
    source .venv/bin/activate
    uv sync --extra dev
    cd ../../..
    export PYTHONPATH="$(pwd)/src/docpipe_app/backend:${PYTHONPATH}"

    # Pull the embedding model (first time only)
    ollama pull nomic-embed-text

Run:
    source src/docpipe_app/backend/.venv/bin/activate
    export PYTHONPATH="$(pwd)/src/docpipe_app/backend:${PYTHONPATH}"
    python examples/docpipe_flow_manager/00_complete_example.py

Note:
    This example uses Ollama locally for embeddings via LiteLLM.
    No real API keys are required (no OPENAI_API_KEY, etc.).
    The flow includes a dummy api_key: "ollama" for validation only.
    All processing happens on your local machine.
"""

import shutil
import sys
from pathlib import Path

from docpipe.lib.docpipe_flow_manager import DocpipeFlowManager


def create_test_data():
    """Create test directory and sample documents"""
    test_dir = Path("./test_data")
    test_dir.mkdir(exist_ok=True)

    # Create sample text file
    sample_file = test_dir / "sample_document.txt"
    sample_content = """
# Sample Document for Testing

This is a test document to validate the PipelineExecutor functionality.

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
The PipelineExecutor provides a simple interface to execute complex data processing
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
    """
    Complete example demonstrating DocpipeFlowManager usage

    This example shows the full workflow:
    1. Create test data
    2. Initialize executor
    3. Execute pipeline
    4. Display results
    5. Clean up
    """
    test_dir = None

    try:
        print("\n" + "=" * 80)
        print("PipelineExecutor Complete Example")
        print("=" * 80)

        # Step 1: Create test data
        print("\n[Step 1/5] Creating test data...")
        test_dir = create_test_data()

        # Step 2: Initialize DocpipeFlowManager
        print("\n[Step 2/5] Initializing DocpipeFlowManager...")
        flow_file = Path(__file__).parent / "sample_flow.json"

        if not flow_file.exists():
            raise FileNotFoundError(
                f"Flow file not found: {flow_file}\nMake sure you're running from the repository root."
            )

        print(f"Loading flow from: {flow_file}")
        manager = DocpipeFlowManager(flow_file=str(flow_file))

        # Step 3: Display metadata
        print("\n[Step 3/5] Flow Metadata:")
        metadata = manager.get_execution_metadata()
        print(f"  Flow Name: {metadata['flow_name']}")
        print(f"  Description: {metadata['flow_description']}")
        print(f"  Number of Operators: {metadata['num_operators']}")
        print(f"  Job ID: {metadata['job_id']}")
        print(f"  Job Run ID: {metadata['job_run_id']}")

        # Step 4: Execute the flow
        print("\n[Step 4/5] Executing pipeline...")
        print("  Pipeline: Ingest -> Extract -> Chunk -> Embeddings")
        print("  This may take a few moments...")

        manager.execute()

        # Step 5: Display results
        print("\n[Step 5/5] Execution Results:")
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
        print("Example completed successfully!")
        print("=" * 80)
        print("\nNext steps:")
        print("  - Try other examples: 01_execute_from_file.py, 02_execute_from_dict.py, etc.")
        print("  - Modify sample_flow.json to experiment with different operators")
        print("  - Check README.md for more information")

    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("\nMake sure you're running from the repository root:")
        print("  python examples/docpipe_flow_manager/00_complete_example.py")
        sys.exit(1)

    except ImportError as e:
        print(f"\nImport error: {e}")
        print("\nMake sure:")
        print("  1. Virtual environment is activated:")
        print("     source src/docpipe_app/backend/.venv/bin/activate")
        print("  2. PYTHONPATH is set:")
        print('     export PYTHONPATH="$(pwd)/src/docpipe_app/backend:${PYTHONPATH}"')
        print("  3. Dependencies are installed:")
        print("     cd src/docpipe_app/backend && uv sync --extra dev")
        sys.exit(1)

    except ConnectionError as e:
        print(f"\nConnection error: {e}")
        print("\nMake sure Ollama is running:")
        print("  1. Start Ollama: ollama serve")
        print("  2. Pull the model: ollama pull nomic-embed-text")
        print("  3. Verify: curl http://localhost:11434/api/tags")
        sys.exit(1)

    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    finally:
        # Cleanup
        if test_dir:
            print("\nCleaning up test data...")
            cleanup_test_data(test_dir)


if __name__ == "__main__":
    main()
