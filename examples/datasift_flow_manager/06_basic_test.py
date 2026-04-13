"""
DatasiftFlowManager Example 6: Basic Test with Auto-Generated Data

This example demonstrates a complete test workflow that creates its own test data,
executes a pipeline, and cleans up afterwards. Similar to 00_complete_example.py
but with more detailed logging and result inspection.

Prerequisites:
- Backend virtual environment activated: source src/datasift_opensource/backend/.venv/bin/activate
- PYTHONPATH set to backend directory: export PYTHONPATH="$(pwd)/src/datasift_opensource/backend:${PYTHONPATH}"
- Ollama running with granite4 model: http://localhost:11434

Setup (from repository root):
    cd src/datasift_opensource/backend
    python3.12 -m venv .venv
    source .venv/bin/activate
    uv sync --extra dev
    cd ../../..
    export PYTHONPATH="$(pwd)/src/datasift_opensource/backend:${PYTHONPATH}"

    # Pull the embedding model (first time only)
    ollama pull granite4

Run:
    source src/datasift_opensource/backend/.venv/bin/activate
    export PYTHONPATH="$(pwd)/src/datasift_opensource/backend:${PYTHONPATH}"
    python examples/datasift_flow_manager/06_basic_test.py
"""

import logging
import shutil
import sys
from pathlib import Path

# Add backend to path for imports
backend_path = Path(__file__).parent.parent / "src" / "datasift_opensource" / "backend"
sys.path.insert(0, str(backend_path))

from lib.datasift_flow_manager import DatasiftFlowManager  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_test_data():
    """Create test directory and sample text file"""
    test_dir = Path("./test_data")
    test_dir.mkdir(exist_ok=True)

    # Create a sample text file
    sample_file = test_dir / "sample_document.txt"
    sample_content = """
# Sample Document for Testing

This is a test document to validate the DatasiftFlowManager functionality.

## Introduction
The datasift-opensource project is a modular, operator-based data processing framework
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
The DatasiftFlowManager provides a simple interface to execute complex data processing
workflows defined in JSON configuration files.
"""

    sample_file.write_text(sample_content)
    logger.info(f"Created test data directory: {test_dir}")
    logger.info(f"Created sample file: {sample_file}")

    return test_dir


def cleanup_test_data(test_dir):
    """Remove test directory and files"""
    if test_dir.exists():
        shutil.rmtree(test_dir)
        logger.info(f"Cleaned up test directory: {test_dir}")


def main():
    """Main test execution function"""
    test_dir = None

    try:
        logger.info("=" * 80)
        logger.info("Starting DatasiftFlowManager Test")
        logger.info("=" * 80)

        # Step 1: Create test data
        logger.info("\n[Step 1] Creating test data...")
        test_dir = create_test_data()

        # Step 2: Initialize DatasiftFlowManager
        logger.info("\n[Step 2] Initializing DatasiftFlowManager...")
        flow_file = Path(__file__).parent / "06_basic_test_flow.json"

        if not flow_file.exists():
            raise FileNotFoundError(f"Flow file not found: {flow_file}")

        logger.info(f"Loading flow from: {flow_file}")
        manager = DatasiftFlowManager(flow_file=str(flow_file))

        # Step 3: Execute the flow
        logger.info("\n[Step 3] Executing flow...")
        logger.info("Flow: ingest -> extract -> chunk -> embeddings")
        logger.info("This may take a few moments...")

        result = manager.execute()

        # Step 4: Print execution results
        logger.info("\n[Step 4] Execution Results:")
        logger.info("=" * 80)

        if result:
            logger.info("Execution Status: SUCCESS")

            # Print metadata
            if hasattr(result, "metadata") and result.metadata:
                logger.info("\nExecution Metadata:")
                for key, value in result.metadata.items():
                    logger.info(f"  {key}: {value}")

            # Print result data info
            if hasattr(result, "data") and result.data is not None:
                logger.info(f"\nResult Data Type: {type(result.data)}")
                if hasattr(result.data, "num_rows"):
                    logger.info(f"Number of rows: {result.data.num_rows}")
                if hasattr(result.data, "column_names"):
                    logger.info(f"Columns: {result.data.column_names}")

            # Print logs if available
            if hasattr(result, "logs") and result.logs:
                logger.info("\nExecution Logs:")
                for log_entry in result.logs[-10:]:  # Last 10 log entries
                    logger.info(f"  {log_entry}")
        else:
            logger.warning("Execution returned no result")

        logger.info("\n" + "=" * 80)
        logger.info("Test completed successfully!")
        logger.info("=" * 80)

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)

    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error(
            "Make sure all dependencies are installed and PYTHONPATH is set correctly"
        )
        sys.exit(1)

    except ConnectionError as e:
        logger.error(f"Connection error: {e}")
        logger.error("Make sure Ollama is running on http://localhost:11434")
        logger.error("You can start it with: ollama serve")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Unexpected error during execution: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Step 5: Cleanup
        if test_dir:
            logger.info("\n[Step 5] Cleaning up test data...")
            cleanup_test_data(test_dir)


if __name__ == "__main__":
    main()
