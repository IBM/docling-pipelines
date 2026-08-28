# DocpipeFlowManager Examples

This directory contains comprehensive examples demonstrating how to use the DocpipeFlowManager class for programmatic execution of docpipe flows.

## Quick Start

**Start here:** Run the complete example that demonstrates all key features:

```bash
# From repository root, with venv activated:
source .venv/bin/activate
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"

# Make sure Ollama is running with the required model
ollama pull nomic-embed-text

# Run the complete example
python examples/docpipe_flow_manager/00_complete_example.py
```

This example creates test data, executes a full pipeline, shows results, and cleans up automatically.

## Examples Overview

### Core Examples
- **`00_complete_example.py`** - **START HERE!** Complete working example with auto-generated test data
- `01_execute_from_file.py` - Execute a flow from a JSON file
- `02_execute_from_dict.py` - Execute a flow from a Python dictionary
- `03_list_operators.py` - List all available operators and their configurations
- `04_custom_configuration.py` - Advanced usage with custom job IDs and error handling
- `05_notebook_usage.py` - Jupyter notebook usage patterns
- `06_basic_test.py` - Detailed test with logging and result inspection

### Flow Definitions
- `sample_flow.json` - Complete working flow: Ingest -> Extract -> Chunk -> Embeddings
- `06_basic_test_flow.json` - Alternative flow configuration for testing

## Prerequisites

### Required Software
- Python 3.12 (as specified in `.python-version`)
- Ollama running on `http://localhost:11434` (for local LLM operations and embeddings)
- OpenSearch running on `http://localhost:9200` (optional, for vector storage examples)

### Required Models
```bash
# Pull embedding models (choose one or both)
ollama pull nomic-embed-text  # Used in sample_flow.json
ollama pull granite4          # Used in 06_basic_test_flow.json
```

**Note:** The examples use Ollama locally via LiteLLM, so **no real API keys are required** (no OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.). The flow configuration includes a dummy `api_key: "ollama"` parameter to satisfy LiteLLM's validation, but this value is not actually used by Ollama. All processing happens on your local machine.

## Setup Instructions

### 1. Create and Activate Virtual Environment

```bash
# From project root

# Activate virtual environment
source .venv/bin/activate  # On macOS/Linux
# OR
.venv\Scripts\activate     # On Windows

# Install dependencies using uv (recommended)
uv sync --extra dev
```

### 2. Set PYTHONPATH

The docpipe directory must be in PYTHONPATH for imports to work correctly:

```bash
# From repository root
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
```

### 3. Start Required Services

```bash
# Start Ollama (in a separate terminal)
ollama serve

# Verify Ollama is running
curl http://localhost:11434/api/tags

# (Optional) Start OpenSearch for vector storage examples
docker-compose -f docker/docker-compose.opensearch.yml up -d
```

## Running Examples

**Important:** Always activate the virtual environment and set PYTHONPATH before running examples.

```bash
# From repository root:
source .venv/bin/activate
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"

# Run examples
python examples/docpipe_flow_manager/00_complete_example.py
python examples/docpipe_flow_manager/01_execute_from_file.py
python examples/docpipe_flow_manager/02_execute_from_dict.py
python examples/docpipe_flow_manager/03_list_operators.py
python examples/docpipe_flow_manager/04_custom_configuration.py
python examples/docpipe_flow_manager/05_notebook_usage.py
python examples/docpipe_flow_manager/06_basic_test.py
```

## Example Descriptions

### 00_complete_example.py (Recommended Starting Point)
A comprehensive, self-contained example that:
- Creates test data automatically
- Executes a complete pipeline (Ingest -> Extract -> Chunk -> Embeddings)
- Displays execution metadata and results
- Cleans up test data after execution
- Includes detailed error handling and helpful error messages

**Use this to verify your setup is working correctly.**

### 01_execute_from_file.py
Demonstrates the simplest way to use DocpipeFlowManager - just provide a path to your flow definition JSON file.

```python
executor = DocpipeFlowManager(flow_file="path/to/flow.json")
result = executor.execute()
```

### 02_execute_from_dict.py
Shows how to programmatically construct or modify flow definitions before execution using a Python dictionary.

```python
flow_def = {
    "flow_name": "My Flow",
    "flow": [...]
}
executor = DocpipeFlowManager(flow_def=flow_def)
result = executor.execute()
```

### 03_list_operators.py
Demonstrates how to discover available operators and their configuration options.

```python
# List operators with summary
summary = DocpipeFlowManager.list_operators(verbose=False)

# List operators with details
details = DocpipeFlowManager.list_operators(verbose=True)
```

### 04_custom_configuration.py
Advanced usage with custom job IDs, error handling, and metadata extraction.

```python
executor = DocpipeFlowManager(
    flow_file=flow_file,
    job_id="custom-job-001",
    job_run_id="custom-run-12345"
)
metadata = executor.get_execution_metadata()
```

### 05_notebook_usage.py
Shows the typical pattern for using DocpipeFlowManager in Jupyter notebooks, including setup and step-by-step execution.

### 06_basic_test.py
A detailed test example with comprehensive logging, result inspection, and automatic test data creation/cleanup.

## Flow Configuration

### Flow Structure
Flow JSON files accept the flow definition at the root level (no nested "flow" key required):

```json
{
  "flow_name": "Flow Name",
  "description": "Flow description",
  "global_config": {
    "doc_column": "content",
    "disable_validation": true,
    "force_ingest": true,
    "storage": "in-memory",
    "execute_type": "local"
  },
  "flow": [
    {
      "name": "operator-name",
      "type": "operator_type",
      "depends_on": ["upstream-operator"],
      "config": { ... }
    }
  ]
}
```


### Available Operators

The framework includes 17+ operators organized into categories:

**Ingest Operators:**
- `ingest_source` - Multi-provider ingest (filesystem, S3, IBM COS, SharePoint, OneDrive, and more)

**Extract Operators:**
- `extract_operator` - Extract structured content from documents
- `extract_operator` - LLM-based entity extraction

**Chunking Operators:**
- `chunker` - Chunk documents (hybrid, semantic, fixed-size)
- `docling_chunker` - Hierarchical chunking with Docling

**Embeddings Operator:**
- `embeddings` - Generate vector embeddings (Ollama, Sentence Transformers)

**Vector Database Operator:**
- `opensearch_operator` - Store/retrieve vectors in OpenSearch

**Utility Operators:**
- `branching_operator` - Conditional workflow branching
- `sql_filter` - Filter data using SQL expressions
- `doc_id_hash` - Generate document identifiers
- `noop` - Pass-through for testing

**Quality Operators:**
- `lang_id` - Language detection
- `readability` - Readability scoring
- `pii_and_hap_annotator` - PII/HAP detection
- And more...

Use `03_list_operators.py` to see all available operators and their configurations.

## Common Workflows

### Document Processing Pipeline
```
Ingest -> Extract -> Chunk -> Embeddings -> Store
```

### Entity Extraction
```
Ingest -> Extract -> ExtractEntitiesOllama
```

### RAG Preparation
```
Ingest -> Extract -> Chunk -> Embeddings -> OpenSearch
```

## Troubleshooting

### Import Errors
```
ImportError: No module named 'docpipe'
```
**Solution:** Make sure PYTHONPATH is set correctly:
```bash
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
```

### Connection Errors
```
ConnectionError: Failed to connect to Ollama
```
**Solution:** Start Ollama and pull required models:
```bash
ollama serve
ollama pull nomic-embed-text
```

### File Not Found
```
FileNotFoundError: Flow file not found
```
**Solution:** Run examples from repository root:
```bash
# From repository root
python examples/docpipe_flow_manager/00_complete_example.py
```

### Virtual Environment Issues
```
ModuleNotFoundError: No module named 'docpipe'
```
**Solution:** Activate the virtual environment:
```bash
source .venv/bin/activate
uv sync --extra dev
```

## Next Steps

1. **Start with `00_complete_example.py`** to verify your setup
2. **Explore other examples** to learn different usage patterns
3. **Modify `sample_flow.json`** to experiment with different operators
4. **Create your own flows** based on the examples
5. **Check operator documentation** in `src/docpipe/core/operators/`

## Additional Resources

- **Main Documentation:** `README.md`
- **Operator Documentation:** `src/docpipe/core/operators/*/README.md`
- **CLI Usage:** `docling-pipelines --help`
- **Architecture:** `AGENTS.md` in repository root

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review operator-specific README files
3. Examine the example code for similar use cases
4. Check logs for detailed error messages
