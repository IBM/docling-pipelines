# DataSift Pipeline User Guide: Complete Setup and Execution

This comprehensive guide walks you through setting up and executing a complete DataSift pipeline from document ingestion to vector storage in OpenSearch.

## Table of Contents

1. [Introduction](#1-introduction)
2. [Prerequisites and Installation](#2-prerequisites-and-installation)
3. [Ollama Setup](#3-ollama-setup)
4. [OpenSearch Setup with Podman](#4-opensearch-setup-with-podman)
5. [Understanding Flow Configuration](#5-understanding-flow-configuration)
6. [Creating Your First Flow](#6-creating-your-first-flow)
7. [Running the Pipeline](#7-running-the-pipeline)
8. [Verification and Testing](#8-verification-and-testing)
9. [Troubleshooting](#9-troubleshooting)
10. [Next Steps](#10-next-steps)
11. [Programmatic Usage (Python API)](#11-programmatic-usage-python-api)
    - [11.1 Introduction](#111-introduction)
    - [11.2 Setup Requirements](#112-setup-requirements)
    - [11.3 Basic Usage: Execute Flow from File](#113-basic-usage-execute-flow-from-file)
    - [11.4 Execute Flow from Dictionary](#114-execute-flow-from-dictionary)
    - [11.5 Jupyter Notebook Integration](#115-jupyter-notebook-integration)
    - [11.6 Validation Before Execution](#116-validation-before-execution)
    - [11.7 Advanced Features](#117-advanced-features)
    - [11.8 Error Handling and Debugging](#118-error-handling-and-debugging)
12. [Execution Models](#12-execution-models)
13. [Job Stats Storage Configuration](#13-job-stats-storage-configuration)

---

## Quick Reference

> **⚠️ CRITICAL: Working Directory Requirements**
>
> All `datasift-orchestrator` commands **MUST** be run from the **project root directory** (`datasift-opensource/`).
>
> **Correct:**
> ```bash
> # From project root (datasift-opensource/)
> datasift-orchestrator --flow-file tests/sample_test_flows/invoice_processing/flow_invoice.json
> ```
>
> **Incorrect:**
> ```bash
> # From datasift directory - WILL FAIL with ModuleNotFoundError
> cd src/datasift
> datasift-orchestrator --flow-file ...  # ERROR: No module named 'datasift'
> ```
>
> **Why:** The PYTHONPATH must point to `src` as the source root. Running from subdirectories breaks Python imports.

---

## 1. Introduction

### Quick Start with Automated Setup

**New users can now use the automated setup script to install all prerequisites automatically!**

The `setup_datasift_environment.sh` script automates the entire setup process, including Python verification, uv installation, Ollama setup, OpenSearch configuration, and Python environment creation.

#### Basic Usage

```bash
# Run with default settings (installs everything)
./scripts/setup_datasift_environment.sh
```

This single command will:
- Verify Python 3.12 installation
- Install uv package manager
- Install and start Ollama
- Download default models (granite4, llama3.2, nomic-embed-text)
- Install Podman/Docker
- Start OpenSearch with Dashboards
- Create Python virtual environment and install dependencies

#### Interactive Mode

For more control over what gets installed:

```bash
# Interactive mode - prompts for each component
./scripts/setup_datasift_environment.sh --interactive
```

#### Custom Configuration

```bash
# Install only specific Ollama models
./scripts/setup_datasift_environment.sh --models granite4,nomic-embed-text

# Skip specific components
./scripts/setup_datasift_environment.sh --skip-ollama
./scripts/setup_datasift_environment.sh --skip-opensearch
./scripts/setup_datasift_environment.sh --skip-python

# Combine options
./scripts/setup_datasift_environment.sh --interactive --models granite4
```

#### Available Options

| Option | Description |
|--------|-------------|
| `--interactive` | Enable interactive mode with prompts for each step |
| `--models MODEL1,MODEL2` | Specify Ollama models (comma-separated). Default: granite4,llama3.2,nomic-embed-text |
| `--skip-ollama` | Skip Ollama installation and setup |
| `--skip-opensearch` | Skip OpenSearch installation and setup |
| `--skip-python` | Skip Python environment setup |
| `--help` | Show help message with all options |

#### What the Script Installs

**Python Environment:**
- Verifies Python 3.12 is installed
- Installs uv package manager
- Creates virtual environment in `src/datasift/.venv`
- Installs all project dependencies

**Ollama (for LLM operations):**
- Installs Ollama server
- Starts Ollama service on `http://localhost:11434`
- Downloads specified models (default: granite4, llama3.2, nomic-embed-text)

**OpenSearch (for vector storage):**
- Installs Podman or uses existing Docker
- Installs podman-compose
- Starts OpenSearch on `http://localhost:9200`
- Starts OpenSearch Dashboards on `http://localhost:5601`
- Default credentials: admin / MyStrongPass123!

#### After Setup Completes

The script creates two files:
- `.datasift_setup_config` - Configuration settings
- `datasift_setup.log` - Detailed setup log

Flow repository storage location is configured in `src/datasift/config/datasift.yaml`:

```yaml
assets_management:
  flow_repository:
    type: local
    config:
      base_dir: ./sample_flows
```

Override precedence for flow storage:
1. `LOCAL_FLOWS_DIR` environment variable
2. `assets_management.flow_repository.config.base_dir` in `datasift.yaml`
3. Default fallback: `~/Documents/pipeline/assets`

**Next steps:**

1. Set PYTHONPATH from project root:
   ```bash
   export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
   ```
   
   > **Warning:** This must be run from the project root directory (`datasift-opensource`), not from the datasift subdirectory. The PYTHONPATH must point to the datasift directory as the source root for Python imports to work correctly.

2. Activate the virtual environment:
   ```bash
   # From project root
   source .venv/bin/activate
   ```

3. Verify installation:
   ```bash
   datasift-orchestrator --help
   ```

4. Run your first flow:
   ```bash
   datasift-orchestrator --flow-file sample_flows/complete_pipeline_flow.json
   ```

#### Troubleshooting the Setup Script

**Script fails with "Python 3.12 not found":**
- Install Python 3.12 manually (see [Prerequisites](#2-prerequisites-and-installation))
- Run the script again

**Ollama fails to start:**
- Check if port 11434 is already in use: `lsof -i :11434`
- Start manually: `ollama serve`

**OpenSearch fails to start:**
- Check if ports 9200 or 5601 are in use
- View logs: `podman-compose -f docker-compose.opensearch.yml logs`
- Ensure you're in the project root directory

**Permission denied errors:**
- Make script executable: `chmod +x scripts/setup_datasift_environment.sh`
- Some operations may require sudo (script will prompt)

**Want to start fresh?**
```bash
# Stop services
podman-compose -f docker-compose.opensearch.yml down
pkill -f "ollama serve"

# Remove configuration
rm .datasift_setup_config datasift_setup.log

# Run setup again
./scripts/setup_datasift_environment.sh
```

---

### Manual Setup

If you prefer manual control or the automated script doesn't work for your environment, follow the detailed manual setup instructions below.

---

## 1. Introduction (continued)

### What is DataSift?

DataSift is a modular, operator-based data processing framework designed for building flexible data pipelines. It enables you to:

- Ingest documents from various sources
- Extract structured content using AI-powered tools
- Chunk documents for optimal processing
- Generate embeddings for semantic search
- Store vectors in OpenSearch for similarity search

### What This Guide Covers

This guide demonstrates the complete **Ingest → Extract → Chunk → Embeddings → OpenSearch** pipeline, which is the foundation for building Retrieval-Augmented Generation (RAG) systems and semantic search applications.

### Pipeline Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Ingest    │───▶│   Extract   │───▶│    Chunk    │───▶│ Embeddings  │───▶│ OpenSearch  │
│   Local     │    │   Docling   │    │   Hybrid    │    │   Ollama    │    │   Vector    │
│   Folder    │    │             │    │             │    │             │    │   Storage   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Prerequisites Overview

Before starting, you'll need:

- **Python 3.12** - Required for DataSift
- **uv package manager** - Fast Python package management
- **Ollama** - Local LLM server for embeddings
- **Podman or Docker** - For running OpenSearch
- **Basic command-line knowledge** - For running commands

---

## Job Stats Storage Configuration

datasift-opensource supports pluggable job stats storage for job runs, node execution state, and micro-batch progress tracking.

### Available Backends

- **In-memory** - test and development scenarios
- **JSON storage** - local file-backed persistence
- **PostgreSQL** - durable storage for concurrent and distributed execution

### Backend Selection

Job-management components are wired through [`JobManagementFactory`](src/datasift/core/job_management/adapters/config/job_management_factory.py). Backend selection is controlled by [`datasift.yaml`](src/datasift/config/datasift.yaml) and environment overrides.

The main user-facing configuration lives under [`job_management`](src/datasift/config/datasift.yaml:8) in [`datasift.yaml`](src/datasift/config/datasift.yaml):

```yaml
job_management:
  framework:
    type: default
    config: {}
  store:
    type: json
    config:
      base_dir: ./data/job_stats_store_data
```

This allows users to configure:
- the job framework type under [`job_management.framework.type`](src/datasift/config/datasift.yaml:9)
- the job stats store backend under [`job_management.store.type`](src/datasift/config/datasift.yaml:12)
- the job stats store runtime config under [`job_management.store.config`](src/datasift/config/datasift.yaml:15)
- the flow repository separately under [`assets_management.flow_repository`](src/datasift/config/datasift.yaml:1)

Common overrides include:
- `DATASIFT_CONFIG_PATH`
- `DATASIFT_STORAGE_BACKEND`
- `DATASIFT_FRAMEWORK_TYPE`
- `DATASIFT_JOB_STATS_BASE_DIR`
- `DATASIFT_POSTGRES_HOST`
- `DATASIFT_POSTGRES_PORT`
- `DATASIFT_POSTGRES_DB`
- `DATASIFT_POSTGRES_USER`
- `DATASIFT_POSTGRES_PASSWORD`

Effective precedence for job-management runtime selection is:
1. explicit environment overrides
2. values from [`datasift.yaml`](src/datasift/config/datasift.yaml)
3. built-in defaults in [`JobManagementFactory`](src/datasift/core/job_management/adapters/config/job_management_factory.py)

### JSON Storage Guidance

JSON storage is useful for single-host execution and simple local testing.

Important requirements:
- the job stats base directory must be writable
- for distributed Prefect workers, the configured path must resolve to the same shared filesystem location for the submitter and workers
- local-only paths on the submitter machine are not sufficient for distributed workers
- when JSON storage is selected from config, worker propagation resolves `base_dir` to an absolute path before injecting it into the worker environment

### PostgreSQL Guidance

PostgreSQL is the recommended backend for multi-process and distributed execution because it provides durable shared storage and stronger concurrency behavior than file-backed JSON storage.

Use PostgreSQL when:
- multiple workers need to update job stats concurrently
- workers do not share a reliable filesystem path
- you need a single durable backend for job status APIs
- you want workers on different containers, pods, or machines to share a single backend without filesystem coupling

### Metadata Aggregation Maintenance

Node stats are aggregated on the read path, not in the storage adapter. When operators add new metadata fields, maintainers must review [`DEFAULT_STRATEGIES`](src/datasift/core/job_management/application/aggregation/strategies.py) and update it if the field should not use the default `LAST` aggregation behavior.

See [`docs/job_stats_management/NODE_METADATA_AGGREGATION_STRATEGY.md`](docs/job_stats_management/NODE_METADATA_AGGREGATION_STRATEGY.md) for the maintainer workflow.

### Distributed Execution and Work Pool Environment Inheritance

For distributed Prefect execution, work pool runtime configuration is modeled in [`work_pool_config.py`](src/datasift/core/orchestrator/prefect/config/work_pool_config.py) and applied by [`WorkPoolAdapter`](src/datasift/core/orchestrator/prefect/adapters/work_pool_adapter.py).

Important behavior:
- worker `env` values configured directly in the work pool take highest precedence
- if job-management env values are omitted from the work pool config, workers inherit the submitter's effective job-management configuration
- the inherited effective configuration is resolved from:
  - submitter environment variables
  - [`datasift.yaml`](src/datasift/config/datasift.yaml)
  - code defaults

This makes it possible to keep a single source of truth in [`datasift.yaml`](src/datasift/config/datasift.yaml) while still overriding specific values per environment or per deployment.

For full distributed execution examples and work-pool-specific configuration, see [`docs/prefect/DISTRIBUTED_EXECUTION_GUIDE.md`](docs/prefect/DISTRIBUTED_EXECUTION_GUIDE.md).

---

## 2. Prerequisites and Installation

### Python 3.12 Requirement

DataSift requires Python 3.12. Check your version:

```bash
python --version
# Should output: Python 3.12.x
```

If you need to install Python 3.12:

**macOS (using Homebrew):**
```bash
brew install python@3.12
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv
```

### Installing uv Package Manager

uv is a fast Python package manager that DataSift uses for dependency management.

**Install uv:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Verify installation:**
```bash
uv --version
```

### Cloning and Setting Up the Project

**1. Clone the repository:**
```bash
git clone https://github.ibm.com/wdp-gov/datasift-opensource.git
cd datasift-opensource
```

> **Note:** If you already have the repository cloned, simply navigate to it:
> ```bash
> cd datasift-opensource
> ```

**2. Create virtual environment and install dependencies:**
```bash
# From project root
uv sync --extra dev
```

This command:
- Installs CPython 3.12.13 in a virtual environment (`.venv/` at project root)
- Installs all project dependencies
- Installs development dependencies

**3. Activate the virtual environment:**

**macOS/Linux:**
```bash
# From project root
source .venv/bin/activate
```

**Windows:**
```bash
# From project root
.venv\Scripts\activate
```

### Verify Installation

Check that the CLI tool is available:

```bash
datasift-orchestrator --help
```

You should see the help message with available commands.

---

## 3. Ollama Setup

Ollama provides local LLM capabilities for generating embeddings. The DataSift pipeline uses Ollama by default for the embeddings operator.

### Installing Ollama

**macOS:**
```bash
brew install ollama
```

Or download from: https://ollama.ai/download

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Windows:**
Download the installer from: https://ollama.ai/download

### Starting the Ollama Server

**Start Ollama in the background:**
```bash
ollama serve
```

The server will run on `http://localhost:11434` by default.

**Tip:** Keep this terminal open, or run Ollama as a system service.

### Downloading Models

DataSift supports multiple Ollama models. For this guide, we'll use three models:

**1. Download granite4 (recommended for general use):**
```bash
ollama pull granite4
```

**2. Download llama3.2 (optional - alternative model):**
```bash
ollama pull llama3.2
```

**3. Download nomic-embed-text (optimized for embeddings):**
```bash
ollama pull nomic-embed-text
```

**Model sizes and download times:**
- `granite4`: ~2.5GB (5-10 minutes)
- `llama3.2`: ~2GB (5-10 minutes)
- `nomic-embed-text`: ~274MB (1-2 minutes)

### Verifying Ollama is Running

**Check server status:**
```bash
curl http://localhost:11434/api/tags
```

You should see a JSON response listing your downloaded models:

```json
{
  "models": [
    {
      "name": "granite4:latest",
      "modified_at": "2024-01-15T10:30:00Z",
      "size": 2500000000
    },
    {
      "name": "llama3.2:latest",
      "modified_at": "2024-01-15T10:45:00Z",
      "size": 2000000000
    },
    {
      "name": "nomic-embed-text:latest",
      "modified_at": "2024-01-15T11:00:00Z",
      "size": 274000000
    }
  ]
}
```

### Troubleshooting Common Ollama Issues

**Issue: "Connection refused" error**
```bash
# Solution: Start the Ollama server
ollama serve
```

**Issue: "Model not found" error**
```bash
# Solution: Pull the model first
ollama pull granite4
```

**Issue: Ollama using too much memory**
```bash
# Solution: Use a smaller model
ollama pull nomic-embed-text  # Only 274MB
```

**Issue: Slow model downloads**
```bash
# Solution: Download smaller models first, or use a faster internet connection
ollama pull nomic-embed-text  # Fastest download
```

---

## 4. OpenSearch Setup with Podman

OpenSearch is a vector database that stores embeddings and enables similarity search. We'll use Podman (or Docker) to run OpenSearch locally.

### Installing Podman

**macOS:**
```bash
brew install podman
podman machine init
podman machine start
```

**Linux (Fedora/RHEL/CentOS):**
```bash
sudo dnf install podman
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install podman
```

**Verify installation:**
```bash
podman --version
```

**Install podman-compose:**
```bash
pip install podman-compose
```

### Starting OpenSearch Using podman-compose

DataSift includes a pre-configured `docker-compose.opensearch.yml` file.

**1. Start OpenSearch:**

Using Podman:
```bash
podman compose -f docker-compose.opensearch.yml up -d
```

Using Docker:
```bash
docker compose -f docker-compose.opensearch.yml up -d
```

**2. Wait for services to start (30-60 seconds):**

The compose file starts two services:
- **opensearch-node**: The OpenSearch server
- **opensearch-dashboards**: Web UI for OpenSearch

### Verifying OpenSearch is Running

**Check cluster health:**
```bash
curl -u admin:MyStrongPass123! "http://localhost:9200/_cluster/health?pretty"
```

**Expected response:**
```json
{
  "cluster_name": "opensearch-cluster",
  "status": "green",
  "timed_out": false,
  "number_of_nodes": 1,
  "number_of_data_nodes": 1,
  "active_primary_shards": 0,
  "active_shards": 0,
  "relocating_shards": 0,
  "initializing_shards": 0,
  "unassigned_shards": 0
}
```

**Status meanings:**
- `green`: All shards allocated, cluster healthy
- `yellow`: Primary shards allocated, some replicas missing (normal for single-node)
- `red`: Some primary shards not allocated, cluster unhealthy

### Accessing OpenSearch Dashboards

OpenSearch Dashboards provides a web interface for managing and querying your data.

**1. Open in browser:**
```
http://localhost:5601
```

**2. Login with default credentials:**
- **Username:** `admin`
- **Password:** `MyStrongPass123!`

**3. Explore the interface:**
- **Dev Tools**: Run queries and commands
- **Index Management**: View and manage indices
- **Discover**: Search and visualize data

### Default Credentials and Security

**Default credentials (from docker-compose.opensearch.yml):**
- **Username:** `admin`
- **Password:** `MyStrongPass123!`
- **Port:** `9200` (API), `5601` (Dashboards)

**Security notes:**
- SSL is **disabled** for local development (`opensearch_use_ssl: false`)
- Certificate verification is **disabled** (`opensearch_verify_certs: false`)
- **Do not use these settings in production!**

**For production:**
- Enable SSL/TLS
- Use strong passwords
- Enable certificate verification
- Configure proper authentication

### Stopping and Cleaning Up OpenSearch

**Stop services (keeps data):**
```bash
podman-compose -f docker-compose.opensearch.yml down
```

**Stop and remove data:**
```bash
podman-compose -f docker-compose.opensearch.yml down -v
```

**View logs:**
```bash
podman-compose -f docker-compose.opensearch.yml logs -f
```

**Restart services:**
```bash
podman-compose -f docker-compose.opensearch.yml restart
```

---

## 5. Understanding Flow Configuration (flow.json)

DataSift pipelines are defined using JSON configuration files. Let's understand the structure using the example from [`sample_flows/complete_pipeline_flow.json`](sample_flows/complete_pipeline_flow.json).

### Complete flow.json Structure

```json
{
  "flow": {
    "name": "invoice processing flow",
    "flow_id": "55578a6c-96b0-4f51-af8f-3aa63c575141",
    "description": "a flow to demonstrate invoice processing with datasift pipeline",
    "storage": "in-memory",
    "execute_type": "local",
    "global_config": {
      "doc_column": "content",
      "disable_validation": "true",
      "force_ingest": true
    },
    "dag": [
      // Operator nodes go here
    ]
  }
}
```

### Required Top-Level Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `name` | string | Human-readable flow name | `"invoice processing flow"` |
| `flow_id` | string | Unique identifier (UUID) | `"55578a6c-96b0-4f51-af8f-3aa63c575141"` |
| `description` | string | Flow purpose description | `"a flow to demonstrate..."` |
| `storage` | string | Data storage type | `"in-memory"` or `"disk"` |
| `execute_type` | string | Execution environment | `"local"` or `"distributed"` |
| `global_config` | object | Global configuration | See below |
| `dag` | array | Operator nodes | See operator sections |

### Operator Configuration Examples

#### Operator 1: ingest_local

Reads files from a local directory:

```json
{
  "id": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd",
  "name": "ingest",
  "operator": "ingest_local",
  "config": {
    "input_folder": "./tests/fixtures/invoices",
    "include_filter": ".pdf",
    "max_workers": 2
  },
  "input_edges": [],
  "output_edges": [{"node_id_ref": "7cfd7577-b061-4fc9-92d5-120ae0fbde89"}]
}
```

**Note:** Extension names should include the dot prefix and be comma-separated (e.g., `".pdf,.txt,.docx"` not `"*.pdf,*.txt"` or `"pdf,txt"`). The operator will also accept extensions without dots for backward compatibility.

#### Operator 2: extract_operator

The `extract_operator` handles both text extraction and entity extraction.

**Supported text extraction modes:**
- `docling_library`
- `docling_serve`

**Supported entity extraction modes:**
- `ollama`
- `docling`
- `litellm`
- `none`

**Basic Text Extraction (DEFAULT):**
```json
{
  "id": "7cfd7577-b061-4fc9-92d5-120ae0fbde89",
  "name": "extract",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "none",
    "doc_column": "content"
  },
  "input_edges": [{"node_id_ref": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd"}],
  "output_edges": [{"node_id_ref": "6101c752-523e-4a4a-84e2-81e0b2109129"}]
}
```

**Optional: Advanced Template-Based Extraction**
For structured data extraction with predefined schemas, use `entity_extraction_mode: "docling"`

```json
{
  "id": "7cfd7577-b061-4fc9-92d5-120ae0fbde89",
  "name": "extract",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "docling",
    "doc_column": "content",
    "expand_extracted_data": true,
    "custom_schema": {
      "invoice_number": "string",
      "invoice_date": "string",
      "vendor_name": "string",
      "total": "float"
    }
  },
  "input_edges": [{"node_id_ref": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd"}],
  "output_edges": [{"node_id_ref": "6101c752-523e-4a4a-84e2-81e0b2109129"}]
}
```

This advanced approach is useful when you need to extract specific fields from structured documents like invoices, forms, or receipts.

#### Operator 3: chunker

Splits documents into chunks:

```json
{
  "id": "6101c752-523e-4a4a-84e2-81e0b2109129",
  "name": "chunk",
  "operator": "chunker",
  "config": {
    "chunk_type": "hybrid",
    "doc_column": "content",
    "chunk_size": 512,
    "chunk_overlap": 128,
    "retain_original_content": "true"
  },
  "input_edges": [{"node_id_ref": "7cfd7577-b061-4fc9-92d5-120ae0fbde89"}],
  "output_edges": ["6de879bd-bbe0-4d60-998f-031f65472a02"]
}
```

#### Operator 4: embeddings

Generates vector embeddings:

```json
{
  "id": "6de879bd-bbe0-4d60-998f-031f65472a02",
  "name": "embeddings",
  "operator": "embeddings",
  "config": {
    "embeddings_type": "ollama",
    "embeddings_model_id": "granite4:latest",
    "embeddings_column": "embeddings",
    "overlap_ratio": 0.2,
    "doc_column": "content"
  },
  "input_edges": [{"node_id_ref": "6101c752-523e-4a4a-84e2-81e0b2109129"}],
  "output_edges": ["87249dbf-4a1a-433a-91da-ee5fb3244284"]
}
```

**Note:** Use `ollama list` to see available models on your system. Common embedding models include `granite4:latest`, `nomic-embed-text`, and `mxbai-embed-large`.

#### Operator 5: vectordb

Stores documents and embeddings in OpenSearch for vector similarity search.

**Configuration:**

```json
{
  "id": "opensearch_node",
  "operator": "vectordb",
  "config": {
    "provider": "opensearch",
    "index_name": "documents",
    "doc_id_column": "doc_id_hash",
    "embeddings_column": "embeddings",
    "create_index": true,
    "vector_dimension": 768,
    "provider_config": {
      "host": "localhost",
      "port": 9200,
      "username": "admin",
      "password": "MyStrongPass123!", # pragma: allowlist secret
      "use_ssl": false,
      "verify_certs": false,
      "engine": "faiss",
      "algorithm": "hnsw",
      "space_type": "l2",
      "batch_size": 100
    },
    "feature_mappings": {
      "content": "content",
      "doc_name": "doc_name",
      "file_path": "file_path",
      "doc_id_hash": "doc_id_hash",
      "chunk_id": "chunk_id",
      "chunk_index": "chunk_index"
    },
    "available_features": {
      "embeddings": {
        "type": "vector",
        "available_for_vector_db": true
      },
      "content": {
        "type": "string",
        "available_for_vector_db": true
      },
      "doc_name": {
        "type": "string",
        "available_for_vector_db": true
      },
      "file_path": {
        "type": "string",
        "available_for_vector_db": true
      },
      "doc_id_hash": {
        "type": "string",
        "available_for_vector_db": true
      },
      "chunk_id": {
        "type": "string",
        "available_for_vector_db": true
      },
      "chunk_index": {
        "type": "integer",
        "available_for_vector_db": true
      }
    }
  }
}
```

**Required Parameters:**

- **provider**: Type of vector database (uses "opensearch" by default)
- **index_name**: Name of the OpenSearch index
- **available_features**: Defines which columns to store and their types. **Embeddings field is mandatory.**
  - Must include `embeddings` with `"type": "vector"` and `"available_for_vector_db": true`
  - Other fields are optional but recommended: content, doc_name, doc_id_hash
  - Supported types: vector, string, integer, float, boolean
- **feature_mappings**: Maps PyArrow column names to OpenSearch field names
  - Format: `{"pyarrow_column": "opensearch_field"}`
  - Must include all fields defined in available_features

**Optional Provider Configurations (provider_config):**

- **host**: OpenSearch server address (default: "localhost")
- **port**: Server port (default: 9200)
- **username/password**: Authentication credentials
- **use_ssl**: Enable SSL (default: true)
- **verify_certs**: Verify SSL certificates (default: true)
- **create_index**: Auto-create index if missing (default: true)
- **vector_dimension**: Embedding dimension (default: 384, auto-detected from data)
  - **Must match the embedding model's output dimension**
  - Common dimensions: `nomic-embed-text`: 768, `llama3.2`: 4096, `granite-embedding`: 384
  - The dimension in this configuration must exactly match the dimension produced by your embeddings operator
- **engine**: KNN engine - faiss, lucene, nmslib (default: faiss)
- **algorithm**: KNN algorithm - hnsw, ivf (default: hnsw)
- **space_type**: Distance metric - l2, cosine, inner_product (default: l2)
- **batch_size**: Documents per batch (default: 100)
- **engine_parameters**: Optional engine-specific parameters (e.g., {"ef_construction": 512, "m": 16} for HNSW)

> **⚠️ Important**: The embeddings column is mandatory. The operator validates embeddings exist in the input table and will fail if missing. You must explicitly configure embeddings in `available_features` for them to be stored in OpenSearch.

### How to Connect Operators Using Edges

Operators are connected using `input_edges` and `output_edges`. Each operator's `id` must match the `node_id_ref` in connected operators.

---

## 6. Creating Your First Flow

### Testing with the Sample Flow

**Before creating your own flow**, you can test your setup using the provided sample flow:

The repository includes a complete, ready-to-run pipeline in [`sample_flows/complete_pipeline_flow.json`](sample_flows/complete_pipeline_flow.json) that demonstrates the full document processing workflow:

- **Ingest** → Reads documents from `./sample_documents`
- **Extract** → Extracts content using Docling
- **Chunk** → Splits documents using semantic chunking (512 tokens, 50 overlap)
- **Embed** → Generates embeddings using Ollama's `nomic-embed-text` model
- **Store** → Saves vectors to OpenSearch index `sample-documents-index`

**To test your setup:**

> **⚠️ Important:** Commands must be run from the **project root directory** (`datasift-opensource/`), not from subdirectories.

1. Ensure you have sample documents in `./sample_documents/` directory (create it if needed)
2. Run the sample flow:
   ```bash
   # From project root (datasift-opensource/)
   datasift-orchestrator --flow-file sample_flows/complete_pipeline_flow.json
   ```

**Additional sample flows for testing:**

```bash
# Invoice processing pipeline
# From project root (datasift-opensource/)
datasift-orchestrator --flow-file tests/sample_test_flows/invoice_processing/flow_invoice.json
```

This validates that Ollama, OpenSearch, and all operators are working correctly before you create custom flows.

For more sample flows and details, see [`sample_flows/README.md`](sample_flows/README.md) and [`tests/sample_test_flows/README.md`](tests/sample_test_flows/README.md).

### Creating a Custom Flow

### Generating Operator IDs

Each operator in your flow must have a unique UUID identifier. These IDs are used to connect operators via `input_edges` and `output_edges` in the flow configuration.

**UUID Requirements:**
- Each operator's `id` field must be a valid UUID (format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
- IDs must be unique across all operators in the flow
- IDs are used to reference operators in edge connections

**Helper Function:**

You can use this Python script to generate UUIDs for your operators:

```python
import uuid

def generate_operator_ids(count=5):
    """Generate unique UUIDs for operator node IDs"""
    return [str(uuid.uuid4()) for _ in range(count)]

# Generate 5 UUIDs for a 5-operator pipeline
ids = generate_operator_ids(5)
for i, operator_id in enumerate(ids, 1):
    print(f"Operator {i} ID: {operator_id}")
```

**Example Output:**
```
Operator 1 ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
Operator 2 ID: b2c3d4e5-f6a7-8901-bcde-f12345678901
Operator 3 ID: c3d4e5f6-a7b8-9012-cdef-123456789012
Operator 4 ID: d4e5f6a7-b8c9-0123-def1-234567890123
Operator 5 ID: e5f6a7b8-c9d0-1234-ef12-345678901234
```

**Usage:**
1. Run the helper script before creating your flow.json
2. Copy the generated UUIDs
3. Replace placeholder IDs (like `ingest-uuid`, `extract-uuid`) in your flow configuration with the generated UUIDs
4. Ensure the same UUID is used consistently in both the operator's `id` field and any edge references


### Step-by-Step Guide

**1. Prepare test documents:**

**Option A: Use sample test data from the repository**

The repository includes sample invoice PDFs for testing in `tests/fixtures/invoices/`. This directory contains 3 sample invoice PDFs that you can use to test your first pipeline.

**Option B: Create your own test directory**

```bash
# Working directory: project root (datasift-opensource)

# Create test directory
mkdir -p test-documents

# Copy sample files from repository fixtures
cp tests/fixtures/invoices/*.pdf test-documents/

# Or copy your own PDFs
cp /path/to/your/pdfs/*.pdf test-documents/
```

> **Note:** The test-documents directory should be created in the project root (datasift-opensource). Ensure you have at least one PDF file in this directory before running the pipeline.

**2. Generate operator UUIDs:**

Before creating your flow configuration, generate unique UUIDs for your operators using the helper function from the "Generating Operator IDs" section above:

```bash
# Working directory: project root (datasift-opensource)

python3 << 'EOF'
import uuid

def generate_operator_ids(count=5):
    """Generate unique UUIDs for operator node IDs"""
    return [str(uuid.uuid4()) for _ in range(count)]

# Generate 5 UUIDs for our 5-operator pipeline
ids = generate_operator_ids(5)
print("\nGenerated UUIDs for your pipeline:")
print(f"Ingest operator:     {ids[0]}")
print(f"Extract operator:    {ids[1]}")
print(f"Chunk operator:      {ids[2]}")
print(f"Embeddings operator: {ids[3]}")
print(f"OpenSearch operator: {ids[4]}")
print("\nCopy these UUIDs and use them in your flow.json below.\n")
EOF
```

**Note:** Replace the placeholder UUIDs (`ingest-uuid`, `extract-uuid`, etc.) in the flow configuration below with the actual UUIDs generated in step 2.

```

**3. Create flow.json:**
```bash
# Working directory: project root (datasift-opensource)

cat > my-first-flow.json << 'EOF'
{
  "flow": {
    "name": "My First Flow",
    "flow_id": "12345678-1234-1234-1234-123456789012",
    "description": "Process PDFs and store in OpenSearch",
    "storage": "in-memory",
    "execute_type": "local",
    "global_config": {
      "doc_column": "content",
      "force_ingest": true
    },
    "dag": [
      {
        "id": "ingest-uuid",
        "name": "ingest",
        "operator": "ingest_local",
        "config": {
          "input_folder": "./test-documents",
          "include_filter": ".pdf"
        },
        "note": "Use full/absolute path for input_folder in production (e.g., /Users/username/datasift-opensource/test-documents)",
        "input_edges": [],
        "output_edges": [{"node_id_ref": "extract-uuid"}]
      },
      {
        "id": "extract-uuid",
        "name": "extract",
        "operator": "extract_operator",
        "config": {
          "doc_column": "content"
        },
        "input_edges": [{"node_id_ref": "ingest-uuid"}],
        "output_edges": [{"node_id_ref": "chunk-uuid"}]
      },
      {
        "id": "chunk-uuid",
        "name": "chunk",
        "operator": "chunker",
        "config": {
          "chunk_type": "simple",
          "chunk_size": 512,
          "chunk_overlap": 128
        },
        "input_edges": [{"node_id_ref": "extract-uuid"}],
        "output_edges": [{"node_id_ref": "embeddings-uuid"}]
      },
      {
        "id": "embeddings-uuid",
        "name": "embeddings",
        "operator": "embeddings",
        "config": {
          "embeddings_type": "ollama",
          "embeddings_model_id": "granite4:latest"
        },
        "input_edges": [{"node_id_ref": "chunk-uuid"}],
        "output_edges": [{"node_id_ref": "opensearch-uuid"}]
      },
      {
        "id": "opensearch-uuid",
        "name": "vectordb",
        "operator": "vectordb",
        "config": {
          "provider": "opensearch",
          "index_name": "my_documents",
          "doc_id_column": "doc_id_hash",
          "embeddings_column": "embeddings",
          "vector_dimension": 768,
          "create_index": true,
          "provider_config": {
            "host": "localhost",
            "port": 9200,
            "username": "admin",
            "password": "MyStrongPass123!", # pragma: allowlist secret
            "use_ssl": false,
            "verify_certs": false,
            "engine": "faiss",
            "algorithm": "hnsw",
            "space_type": "l2",
            "batch_size": 100
          },
          "feature_mappings": {
            "content": "content",
            "doc_name": "doc_name",
            "file_path": "file_path",
            "doc_id_hash": "doc_id_hash",
            "chunk_id": "chunk_id",
            "chunk_index": "chunk_index"
          },
          "available_features": {
            "embeddings": {
              "type": "vector",
              "available_for_vector_db": true
            },
            "content": {
              "type": "string",
              "available_for_vector_db": true
            },
            "doc_name": {
              "type": "string",
              "available_for_vector_db": true
            },
            "file_path": {
              "type": "string",
              "available_for_vector_db": true
            },
            "doc_id_hash": {
              "type": "string",
              "available_for_vector_db": true
            },
            "chunk_id": {
              "type": "string",
              "available_for_vector_db": true
            },
            "chunk_index": {
              "type": "integer",
              "available_for_vector_db": true
            }
          }
        },
        "input_edges": [{"node_id_ref": "embeddings-uuid"}],
        "output_edges": []
      }
    ]
  }
}
EOF
```

**4. Validate JSON:**
```bash
# Working directory: project root (datasift-opensource)

python -m json.tool my-first-flow.json
```

---

## 7. Running the Pipeline

> **🚨 CRITICAL REQUIREMENT: Working Directory**
>
> **ALL commands in this section MUST be run from the project root directory (`datasift-opensource/`).**
>
> Running from any subdirectory (e.g., `src/datasift/`) will cause `ModuleNotFoundError: No module named 'datasift_opensource'`.

### Setting PYTHONPATH

Before running any datasift-orchestrator commands, you must set the PYTHONPATH from the project root:

```bash
# MUST be run from project root (datasift-opensource/)
# Current directory: datasift-opensource/
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
```

> **⚠️ Warning:** This command MUST be run from the project root directory (`datasift-opensource/`), not from a subdirectory. The PYTHONPATH must point to the datasift directory as the source root for Python imports to work correctly. If you run this from the wrong directory, you will get `ModuleNotFoundError` when executing flows.

### Activating the Virtual Environment

```bash
# From project root (datasift-opensource/)
source .venv/bin/activate
```

**Important:** Both PYTHONPATH and virtual environment activation are required every time you open a new terminal session. The virtual environment contains all the necessary dependencies for running DataSift pipelines.

### Executing the Flow

**1. Ensure services are running:**
```bash
# From project root (datasift-opensource/)
# Check Ollama
curl http://localhost:11434/api/tags

# Check OpenSearch
curl -u admin:MyStrongPass123! "http://localhost:9200/_cluster/health"
```

**2. Run the flow:**

**Option A: Run your custom flow**
```bash
# From project root (datasift-opensource/)
datasift-orchestrator --flow-file my-first-flow.json
```

**Option B: Test with the sample flow first**
```bash
# From project root (datasift-opensource/)
datasift-orchestrator --flow-file sample_flows/complete_pipeline_flow.json
```

> **Tip:** If this is your first time running a pipeline, use the sample flow to verify your setup before running custom flows.

**3. With debug logging:**
```bash
# From project root (datasift-opensource/)
datasift-orchestrator --flow-file my-first-flow.json --log-level debug
```

### Understanding the Output

Successful execution shows progress through each operator:

```
Loading flow definition from my-first-flow.json
>>> Creating the orchestrator
>>> Starting flow execution
[INFO] Processing operator: ingest
[INFO] Processing operator: extract
[INFO] Processing operator: chunk
[INFO] Processing operator: embeddings
[INFO] Processing operator: opensearch
>>> Completed execution
```

---

## 8. Verification and Testing

### Verify Ollama Setup

```bash
# Check server
curl http://localhost:11434/api/tags

# Test embeddings
curl http://localhost:11434/api/embeddings -d '{
  "model": "nomic-embed-text",
  "prompt": "Test"
}'
```

### Verify OpenSearch Setup

```bash
# Check health
curl -u admin:MyStrongPass123! "http://localhost:9200/_cluster/health?pretty"

# List indices
curl -u admin:MyStrongPass123! http://localhost:9200/_cat/indices?v

# Count documents
curl -u admin:MyStrongPass123! http://localhost:9200/my_documents/_count?pretty
```

### Using OpenSearch Dashboards

1. Open http://localhost:5601
2. Login (admin / MyStrongPass123!)
3. Navigate to Dev Tools
4. Run queries:

```
GET /my_documents/_search
{
  "size": 10
}
```

---

## 9. Troubleshooting

### Common Issues

**ModuleNotFoundError: No module named 'datasift_opensource'**

This error occurs when running `datasift-orchestrator` from the wrong directory.

**Symptoms:**
```
ModuleNotFoundError: No module named 'datasift_opensource'
```

**Cause:** You are running the command from a subdirectory (e.g., `src/datasift/`) instead of the project root.

**Solution:**
```bash
# 1. Navigate to project root
cd /path/to/datasift-opensource/

# 2. Verify you're in the correct directory (should show pyproject.toml, src/, tests/, etc.)
ls

# 3. Set PYTHONPATH from project root
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"

# 4. Run datasift-orchestrator from project root
datasift-orchestrator --flow-file tests/sample_test_flows/invoice_processing/flow_invoice.json
```

**Why this happens:** The PYTHONPATH must point to `src` as the source root. When you run commands from subdirectories, the relative path calculation breaks, causing Python to be unable to find the `datasift` module.

---

**Ollama connection error:**
```bash
# Start Ollama
ollama serve
```

**OpenSearch connection error:**
```bash
# Start OpenSearch
podman-compose -f docker-compose.opensearch.yml up -d
```

**Import errors:**
```bash
# Set PYTHONPATH from project root
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
```

**Model not found:**
```bash
# Pull model
ollama pull nomic-embed-text
```

**Setup Script: "externally-managed-environment" Error (macOS):**

If you encounter this error when running `./scripts/setup_datasift_environment.sh` on macOS:
```
error: externally-managed-environment
× This environment is externally managed
```

This is due to PEP 668 protection in Homebrew's Python. The updated script (as of 2026-04-13) now handles this automatically by using `pipx` or Homebrew instead of `pip` for installing `podman-compose`.

**Solutions:**

1. **Re-run the setup script** (recommended) - The updated script automatically uses the correct installation method:
   ```bash
   ./scripts/setup_datasift_environment.sh
   ```

2. **Manual installation using Homebrew:**
   ```bash
   brew install podman-compose
   ```

3. **Manual installation using pipx:**
   ```bash
   brew install pipx
   pipx install podman-compose
   ```

After installation, verify podman-compose is available:
```bash
podman-compose --version
```

**Setup Script: Python 3.14 libexpat Error (macOS):**

If you encounter this error when running the setup script on macOS with Python 3.14 installed:
```
ImportError: dlopen(...pyexpat.cpython-314-darwin.so, 0x0002): 
Symbol not found: _XML_SetAllocTrackerActivationThreshold
```

This is a known compatibility issue between Python 3.14 and the `libexpat` library on macOS. Even if Python 3.12 is installed, `pip3` may default to Python 3.14.

**Solutions:**

1. **Re-run the setup script** (recommended) - The updated script (as of 2026-04-13) now explicitly uses Python 3.12 with pipx:
   ```bash
   ./scripts/setup_datasift_environment.sh
   ```

2. **Manual installation with Python 3.12:**
   ```bash
   brew install pipx
   export PIPX_DEFAULT_PYTHON=python3.12
   pipx install --python python3.12 podman-compose
   ```

3. **Alternative: Use Homebrew (avoids Python version issues):**
   ```bash
   brew install podman-compose
   ```

After installation, verify podman-compose is available:
```bash
podman-compose --version
```



### Debug Logging

```bash
datasift-orchestrator --flow-file my-first-flow.json --log-level debug
```

---

## 10. Next Steps

### Explore More Operators

```bash
# List all operators
datasift-orchestrator --list-operators

# View detailed info
datasift-orchestrator --list-operators --verbose
```

### Customize Your Pipeline

- Add quality checks (language detection, readability)
- Use different chunking strategies
- Try different embedding models
- Configure OpenSearch engine parameters

### Performance Tuning

- Adjust batch sizes
- Use smaller models for faster processing
- Enable parallel processing
- Optimize chunk sizes

## 11. Programmatic Usage (Python API)

### 11.1 Introduction

The [`DatasiftFlowManager`](src/datasift/datasift_flow_manager.py) class provides a Python API for programmatic flow execution, offering greater flexibility than the CLI for integration scenarios.

**When to Use the Programmatic API:**
- **Jupyter Notebooks**: Interactive data exploration and pipeline development
- **Custom Workflows**: Integration with existing Python applications
- **Dynamic Flow Generation**: Creating flows programmatically based on runtime conditions
- **Automated Testing**: Programmatic validation and execution in test suites
- **Multi-tenant Systems**: Generating and executing flows per tenant or dataset

**Key Benefits:**
- **Flexibility**: Define flows as Python dictionaries or load from JSON files
- **Error Handling**: Programmatic access to validation results and execution logs
- **Metadata Access**: Retrieve execution metadata, job IDs, and flow information
- **Integration**: Seamlessly integrate with pandas, PyArrow, and ML pipelines

### 11.2 Setup Requirements

Before using the programmatic API, ensure your environment is properly configured:

**1. Set PYTHONPATH**

The `PYTHONPATH` must include the datasift directory as the source root:

```bash
# From repository root
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
```

**2. Activate Virtual Environment**

```bash
# From project root
source .venv/bin/activate
```

**3. Import Statement**

```python
from lib.datasift_flow_manager import DatasiftFlowManager
```

**4. Verify Prerequisites**

Ensure Ollama and OpenSearch are running (see Sections 3 and 4).

### 11.3 Basic Usage: Execute Flow from File

The simplest way to use the programmatic API is to execute an existing flow JSON file.

**Example: Basic Flow Execution**

```python
from pathlib import Path
from lib.datasift_flow_manager import DatasiftFlowManager

def execute_flow():
    """Execute a flow file with basic error handling."""
    flow_file = Path("sample_flows/complete_pipeline_flow.json")
    
    try:
        # Initialize the manager with a flow file
        manager = DatasiftFlowManager(
            flow_file=str(flow_file),
            log_level="info",
        )
        
        print(f"Loaded flow file: {flow_file}")
        
        # Execute the flow
        result = manager.execute()
        
        # Access execution metadata
        metadata = manager.get_execution_metadata()
        print(f"Flow executed successfully")
        print(f"Job ID: {metadata.get('job_id')}")
        print(f"Flow Name: {metadata.get('name')}")
        
    except FileNotFoundError as exc:
        print(f"Flow file not found: {exc}")
    except ValueError as exc:
        print(f"Invalid configuration: {exc}")
    except Exception as exc:
        print(f"Execution failed: {exc}")

if __name__ == "__main__":
    execute_flow()
```


### 11.4 Execute Flow from Dictionary

For dynamic flow generation, define flows as Python dictionaries instead of JSON files.

**Example: Inline Flow Definition**

```python
from lib.datasift_flow_manager import DatasiftFlowManager

def build_flow_definition(input_folder: str, index_name: str) -> dict:
    """Build a complete flow definition as a Python dictionary."""
    return {
        "name": "programmatic-inline-pipeline",
        "flow_id": "inline-flow-001",
        "description": "Inline flow for document processing",
        "storage": "in-memory",
        "execute_type": "local",
        "global_config": {
            "doc_column": "content",
            "disable_validation": "true",
            "force_ingest": True,
        },
        "dag": [
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "name": "ingest_local_folder",
                "operator": "ingest_local",
                "config": {
                    "input_folder": input_folder,
                    "include_filter": "pdf,txt,docx"
                },
                "input_edges": [],
                "output_edges": [{"node_id_ref": "22222222-2222-4222-8222-222222222222"}],
            },
            {
                "id": "22222222-2222-4222-8222-222222222222",
                "name": "extract_operator",
                "operator": "extract_operator",
                "config": {"doc_column": "content"},
                "input_edges": [{"node_id_ref": "11111111-1111-4111-8111-111111111111"}],
                "output_edges": [{"node_id_ref": "33333333-3333-4333-8333-333333333333"}],
            },
            {
                "id": "33333333-3333-4333-8333-333333333333",
                "name": "chunk_documents",
                "operator": "chunker",
                "config": {
                    "chunk_type": "semantic",
                    "chunk_size": 512,
                    "chunk_overlap": 50,
                },
                "input_edges": [{"node_id_ref": "22222222-2222-4222-8222-222222222222"}],
                "output_edges": [{"node_id_ref": "44444444-4444-4444-8444-444444444444"}],
            },
            {
                "id": "44444444-4444-4444-8444-444444444444",
                "name": "generate_embeddings",
                "operator": "embeddings",
                "config": {
                    "embeddings_type": "ollama",
                    "embeddings_model_id": "nomic-embed-text",
                    "embeddings_column": "content",
                },
                "input_edges": [{"node_id_ref": "33333333-3333-4333-8333-333333333333"}],
                "output_edges": [{"node_id_ref": "55555555-5555-4555-8555-555555555555"}],
            },
            {
                "id": "55555555-5555-4555-8555-555555555555",
                "name": "store_vectors",
                "operator": "vectordb",
                "config": {
                    "provider": "opensearch",
                    "index_name": index_name,
                    "doc_id_column": "doc_id_hash",
                    "embeddings_column": "embeddings",
                    "vector_dimension": 768,
                    "create_index": True,
                    "provider_config": {
                        "host": "localhost",
                        "port": 9200,
                        "username": "admin",
                        "password": "MyStrongPass123!", # pragma: allowlist secret
                        "use_ssl": False,
                        "verify_certs": False,
                        "engine": "faiss",
                        "algorithm": "hnsw",
                        "space_type": "l2",
                        "batch_size": 100
                    },
                },
                "input_edges": [{"node_id_ref": "44444444-4444-4444-8444-444444444444"}],
                "output_edges": [],
            },
        ],
    }

def execute_inline_flow():
    """Execute a flow defined as a Python dictionary."""
    flow_def = build_flow_definition(
        input_folder="./sample_documents",
        index_name="inline-documents-index"
    )
    
    try:
        manager = DatasiftFlowManager(
            flow_def=flow_def,
            log_level="info",
        )
        
        result = manager.execute()
        print("Inline flow executed successfully")
        
    except Exception as exc:
        print(f"Execution failed: {exc}")

if __name__ == "__main__":
    execute_inline_flow()
```

**Use Cases:**
- **Dynamic Flow Generation**: Create flows based on runtime parameters (tenant ID, dataset type, etc.)
- **Template-Based Flows**: Build flow templates and customize per execution
- **Configuration Management**: Generate flows from external configuration systems


### 11.5 Jupyter Notebook Integration

The programmatic API integrates seamlessly with Jupyter notebooks for interactive pipeline development.

**Notebook Workflow Pattern:**

```python
# Cell 1: Setup and imports
from pathlib import Path
from pprint import pprint
from lib.datasift_flow_manager import DatasiftFlowManager

print('Imports loaded successfully.')

# Cell 2: Define flow file path
flow_file = Path('sample_flows/complete_pipeline_flow.json')
print(f'Using flow file: {flow_file}')

# Cell 3: List available operators
operators_summary = DatasiftFlowManager.list_operators()
print(operators_summary)

# Cell 4: Create flow manager with explicit IDs
manager = DatasiftFlowManager(
    flow_file=str(flow_file),
    log_level='info',
    job_id='notebook-job-doc-pipeline',
    job_run_id='notebook-run-001',
    flow_id='notebook-flow-complete-pipeline',
)
print('Manager created.')

# Cell 5: Validate before execution
validation_result = manager.validate()
pprint(validation_result)

if not validation_result['valid']:
    raise RuntimeError('Flow validation failed.')

# Cell 6: Execute the flow
try:
    result = manager.execute()
    print('Flow executed successfully.')
    print(f'Result type: {type(result).__name__}')
except Exception as exc:
    print(f'Execution failed: {exc}')
    raise

# Cell 7: Access execution metadata
metadata = manager.get_execution_metadata()
pprint(metadata)

# Cell 8: Retrieve execution logs
logs = manager.get_execution_logs()
print(f'Captured log lines: {len(logs)}')

if logs:
    print('Last 10 log lines:')
    for line in logs[-10:]:
        print(line)

# Cell 9: Interactive inspection
print('Inspect these objects: result, metadata, logs')
```

**Benefits in Notebooks:**
- **Cell-by-Cell Execution**: Run validation, execution, and analysis in separate cells
- **Interactive Debugging**: Inspect results, metadata, and logs interactively
- **Visualization**: Combine with pandas/matplotlib for result visualization
- **Documentation**: Embed explanations and results in notebook format


### 11.6 Validation Before Execution

Always validate flows before execution to catch configuration errors early.

**Example: Validation Pattern**

```python
from lib.datasift_flow_manager import DatasiftFlowManager

def validate_and_execute(flow_file: str):
    """Validate flow before execution."""
    manager = DatasiftFlowManager(
        flow_file=flow_file,
        log_level="info",
    )
    
    # Validate the flow
    validation_result = manager.validate()
    
    print("Validation Results:")
    print(f"  Valid: {validation_result['valid']}")
    print(f"  Errors: {validation_result['errors']}")
    print(f"  Warnings: {validation_result['warnings']}")
    
    # Only execute if validation passes
    if not validation_result["valid"]:
        print("Validation failed. Aborting execution.")
        for error in validation_result["errors"]:
            print(f"  ERROR: {error}")
        return None
    
    # Show warnings but continue
    if validation_result["warnings"]:
        print("Warnings detected:")
        for warning in validation_result["warnings"]:
            print(f"  WARNING: {warning}")
    
    # Execute after successful validation
    print("Validation passed. Executing flow...")
    result = manager.execute()
    print("Execution completed successfully.")
    
    return result
```

**Validation Checks:**
- **Operator Configuration**: Validates operator parameters and types
- **Edge Connectivity**: Ensures proper connections between operators
- **Required Fields**: Checks for missing required configuration fields
- **Data Flow**: Validates data flow through the pipeline

### 11.7 Advanced Features

The programmatic API provides advanced features for production use cases.

**Custom Job and Flow IDs**

```python
manager = DatasiftFlowManager(
    flow_file="my_flow.json",
    log_level="debug",
    job_id="production-job-2024-01",
    job_run_id="run-20240113-001",
    flow_id="prod-document-pipeline-v2",
)
```

**Accessing Execution Metadata**

```python
# Execute the flow
result = manager.execute()

# Retrieve detailed metadata
metadata = manager.get_execution_metadata()

print(f"Job ID: {metadata.get('job_id')}")
print(f"Job Run ID: {metadata.get('job_run_id')}")
print(f"Flow ID: {metadata.get('flow_id')}")
print(f"Flow Name: {metadata.get('name')}")
print(f"Description: {metadata.get('description')}")
print(f"Number of Operators: {metadata.get('num_operators')}")
print(f"Flow File: {metadata.get('flow_file')}")
```

**Retrieving Execution Logs**

```python
# Get all captured logs
logs = manager.get_execution_logs()

print(f"Total log lines: {len(logs)}")

# Filter logs by level (if needed)
error_logs = [log for log in logs if 'ERROR' in log]
warning_logs = [log for log in logs if 'WARNING' in log]

print(f"Errors: {len(error_logs)}")
print(f"Warnings: {len(warning_logs)}")
```

**Listing Available Operators**

```python
# Get operator summary
operators_summary = DatasiftFlowManager.list_operators()
print(operators_summary)

# Get detailed operator information
operators_detailed = DatasiftFlowManager.list_operators(verbose=True)
print(operators_detailed)
```


### 11.8 Error Handling and Debugging

Implement robust error handling for production deployments.

**Comprehensive Error Handling Pattern**

```python
import traceback
from lib.datasift_flow_manager import DatasiftFlowManager

def execute_with_error_handling(flow_file: str):
    """Execute flow with comprehensive error handling."""
    try:
        # Initialize with debug logging for troubleshooting
        manager = DatasiftFlowManager(
            flow_file=flow_file,
            log_level="debug",  # Use "debug" for detailed logs
        )
        
        # Validate first
        validation_result = manager.validate()
        if not validation_result["valid"]:
            print("Validation failed:")
            for error in validation_result["errors"]:
                print(f"  - {error}")
            return None
        
        # Execute the flow
        result = manager.execute()
        
        # Log success
        metadata = manager.get_execution_metadata()
        print(f"Success: {metadata.get('name')} completed")
        
        return result
        
    except FileNotFoundError as exc:
        print(f"Flow file not found: {exc}")
        print("Check the file path and ensure it exists.")
        
    except ValueError as exc:
        print(f"Invalid configuration value: {exc}")
        print("Review operator parameters in the flow definition.")
        
    except ConnectionError as exc:
        print(f"Connection error: {exc}")
        print("Check Ollama (port 11434) and OpenSearch (port 9200) are running.")
        
    except Exception as exc:
        print(f"Unexpected error: {exc}")
        print("\nFull traceback:")
        print(traceback.format_exc())
        
        # Retrieve logs for debugging
        try:
            logs = manager.get_execution_logs()
            print(f"\nCaptured logs ({len(logs)} lines):")
            for line in logs[-20:]:  # Last 20 lines
                print(line)
        except:
            print("Could not retrieve execution logs.")
    
    return None
```

**Log Level Configuration**

```python
# Development: Detailed debugging information
manager = DatasiftFlowManager(flow_file="flow.json", log_level="debug")

# Production: Standard information logging
manager = DatasiftFlowManager(flow_file="flow.json", log_level="info")

# Quiet: Only warnings and errors
manager = DatasiftFlowManager(flow_file="flow.json", log_level="warning")

# Critical only: Only critical errors
manager = DatasiftFlowManager(flow_file="flow.json", log_level="error")
```

**Debugging Failed Executions**

```python
# After a failed execution, inspect logs
logs = manager.get_execution_logs()

# Search for specific errors
for i, line in enumerate(logs):
    if 'ERROR' in line or 'Exception' in line:
        # Print context around the error
        start = max(0, i - 3)
        end = min(len(logs), i + 4)
        print(f"\nError context (lines {start}-{end}):")
        for j in range(start, end):
            print(f"  {logs[j]}")
```


---

### Production Considerations

- Enable SSL for OpenSearch
- Use strong passwords
- Implement error handling
- Add monitoring and logging
- Scale with distributed execution

---

## 12. Execution Models

DataSift uses Prefect as its orchestration engine and supports two Prefect execution modes:

### Ephemeral Mode (Default)

By default, DataSift runs Prefect in **ephemeral mode** with a temporary in-memory server. This mode is ideal for:

- Development and testing
- Small to medium workloads (< 1000 documents)
- Single-machine processing
- Quick prototyping and learning

**How it works:**
- Prefect server runs temporarily in-memory
- No external Prefect server setup required
- Automatic cleanup after execution
- Zero configuration needed

**Usage:**
```bash
# Simply run your flow - Prefect ephemeral mode is automatic
datasift-orchestrator --flow-file sample_flows/complete_pipeline_flow.json
```

### Distributed Execution with Prefect Work Pools (Optional)

For production workloads and large-scale processing, DataSift supports **Prefect's distributed execution** using work pools and workers.

**When to use:**
- Processing large document collections (1000+ documents)
- Horizontal scaling across multiple machines
- Production deployments with high availability
- Resource-intensive operations requiring distributed processing

**Deployment options:**
1. **Local POC**: Test distributed patterns with Prefect server and workers on a single machine
2. **Docker Compose**: Multi-worker setup with containerized Prefect infrastructure
3. **Kubernetes**: Production-grade Prefect deployment with auto-scaling

For complete setup instructions, work pool configuration, and deployment guides, see:

**[Prefect Distributed Execution Guide](docs/prefect/DISTRIBUTED_EXECUTION_GUIDE.md)**

This guide covers:
- Prefect server and work pool setup
- Worker deployment for different environments
- Batch storage strategies (inline and local filesystem)
- Docker and Kubernetes deployment configurations
- Troubleshooting and performance tuning

---

## Additional Resources

- [DataSift README](../README.md) - Project overview
- [OpenSearch Documentation](../examples/opensearch_example_README.md) - Detailed OpenSearch guide
- [Operator Documentation](../src/datasift/core/operators/) - Operator source code
- [Example Flows](../tests/) - More flow examples

---

**Need Help?**

- Check the [Troubleshooting](#9-troubleshooting) section
- Review operator documentation with `--list-operators --verbose`
- Examine example flows in the `tests/` directory
- Enable debug logging for detailed information