# datasift-operators

This repository contains the datasift operators with FastAPI server, CLI orchestrator, and UI components.

## Table of Contents

- [datasift-operators](#datasift-operators)
  - [Table of Contents](#table-of-contents)
  - [Documentation](#documentation)
    - [Getting Started](#getting-started)
    - [Flow Authoring](#flow-authoring)
    - [Architecture \& Design](#architecture--design)
    - [API \& Reference](#api--reference)
    - [Operator Documentation](#operator-documentation)
      - [Operator Configuration Guides](#operator-configuration-guides)
    - [Additional Resources](#additional-resources)
  - [Available Operators](#available-operators)
    - [Vector Database Operators](#vector-database-operators)
    - [Ingest Operators](#ingest-operators)
    - [Extract Operators](#extract-operators)
    - [Chunking Operators](#chunking-operators)
    - [Language Operators](#language-operators)
    - [Quality Operators](#quality-operators)
    - [Utility Operators](#utility-operators)
    - [Storage Operators](#storage-operators)
    - [Custom Operators](#custom-operators)
  - [Project Structure](#project-structure)
  - [Job Runs and Execution Tracking](#job-runs-and-execution-tracking)
    - [Job Stats Components](#job-stats-components)
    - [Supported Backends](#supported-backends)
    - [API Surface](#api-surface)
    - [User Configuration](#user-configuration)
  - [Setup](#setup)
  - [Running the Application](#running-the-application)
    - [FastAPI Server (TODO)](#fastapi-server-todo)
    - [CLI Orchestrator](#cli-orchestrator)
      - [Executing Flows](#executing-flows)
      - [Validating Flows](#validating-flows)
      - [Listing Operators](#listing-operators)
    - [DatasiftFlowManager API](#datasiftflowmanager-api)
  - [Distributed Execution](#distributed-execution)
    - [Execution Modes](#execution-modes)
    - [Quick Start](#quick-start)
    - [Batch Storage](#batch-storage)
    - [Setup Work Pools](#setup-work-pools)
  - [Docker Deployment](#docker-deployment)
    - [Build Docker Image](#build-docker-image)
    - [Local Development](#local-development)
    - [Distributed Execution with Docker](#distributed-execution-with-docker)
    - [Build Wheel](#build-wheel)
  - [Development](#development)
    - [Adding Dependencies](#adding-dependencies)
    - [Testing](#testing)
      - [Quick Start](#quick-start-2)
      - [Test Organization](#test-organization)
      - [Filtering Tests by Speed](#filtering-tests-by-speed)
      - [Coverage Reports](#coverage-reports)
      - [Test Configuration](#test-configuration)
    - [Code Quality](#code-quality)
      - [Pre-commit Hooks](#pre-commit-hooks)
      - [Manual Code Quality Tools](#manual-code-quality-tools)
  - [API Development](#api-development)
    - [Adding New Routes](#adding-new-routes)
  - [Environment Variables](#environment-variables)
  - [Operator Specific Setup](#operator-specific-setup)
    - [Embeddings Operator Setup](#embeddings-operator-setup)
      - [Step 1 — Install Ollama](#step-1--install-ollama)
      - [Step 2 — Start the Ollama server](#step-2--start-the-ollama-server)
      - [Step 3 — Pull a model](#step-3--pull-a-model)
      - [Step 4 — Install the Python package](#step-4--install-the-python-package)
    - [OpenSearch Vector Store](#opensearch-vector-store)
      - [Step 1 — Start OpenSearch](#step-1--start-opensearch)
      - [Step 2 — Verify it's running](#step-2--verify-its-running)
      - [Step 3 — Configure environment variables](#step-3--configure-environment-variables)
      - [Step 4 — Stop OpenSearch](#step-4--stop-opensearch)
    - [Milvus Vector Store](#milvus-vector-store)
      - [Step 1 — Start Milvus](#step-1--start-milvus)
      - [Step 2 — Verify it's running](#step-2--verify-its-running-1)
      - [Step 3 — Configure in flow](#step-3--configure-in-flow)
      - [Step 4 — Stop Milvus](#step-4--stop-milvus)
  - [Contributing](#contributing)

---

## Documentation

### Getting Started

**New to datasift-operators?** Start here:

- **[Quick Start Guide](QUICKSTART.md)** - Fast-track setup and first pipeline execution
- **[Complete Pipeline Setup Guide](USER_GUIDE_PIPELINE_SETUP.md)** - Comprehensive guide for new users covering:
  - Prerequisites and installation (Python 3.12, uv, dependencies)
  - Ollama setup for LLM operations and embeddings
  - OpenSearch setup with Podman/Docker for vector storage
  - Flow configuration structure and operator examples
  - Step-by-step pipeline execution
  - Verification, testing, and troubleshooting

### Flow Authoring

- **[Flow Authoring Format Guide](docs/guides/FLOW_AUTHORING_FORMAT.md)** - Create DataSift flows with a simplified format:
  - Define operators and dependencies declaratively
  - Automatic dependency resolution
  - Usage with CLI, Python API, and HTTP API
  - Complete pipeline examples and best practices

### Architecture & Design

- **[Architecture Documentation](ARCHITECTURE.md)** - System design and architectural decisions
- **[Job Stats Metadata Aggregation Guide](docs/internals/NODE_METADATA_AGGREGATION_STRATEGY.md)** - Batch metadata aggregation rules and maintainer update requirements

### API & Reference

- **[Operator Reference](docs/reference/OPERATORS.md)** - Complete API documentation for operators and core components
- **[LDAP Server Setup](examples/LDAP/README.md)** - Set up LDAP server for authentication
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions

### Operator Documentation

- **[OpenSearch Documentation](docs/opensearch/)** - Complete setup and usage guide for vector search
- **[OpenSearch Operator Reference](docs/operators/vectordb/opensearch.md)** - Technical API documentation
- **[Integration Examples](examples/opensearch_example_README.md)** - Code examples and patterns

#### Operator Configuration Guides

| Category      | Operator                | Configuration Guide                                                                     |
|---------------|-------------------------|-----------------------------------------------------------------------------------------|
| **Extract**   | Extract                 | [Configuration Guide](docs/operators/extract/extract_operator_config.md)                |
| **Ingest**    | Ingest Local            | [Configuration Guide](docs/operators/ingest_local/ingest_local_config.md)               |
| **Ingest**    | Ingest Source           | [Configuration Guide](docs/operators/ingest_source/ingest_source_config.md)             |
| **Functional**| Branching               | [Configuration Guide](docs/operators/branching_operator/branching_operator_config.md)   |
| **Functional**| Chunker                 | [Configuration Guide](docs/operators/chunker/chunker_config.md)                         |
| **Functional**| Doc ID Hash             | [Configuration Guide](docs/operators/doc_id_hash/doc_id_hash_config.md)                 |
| **Functional**| Embeddings              | [Configuration Guide](docs/operators/embeddings/embeddings_config.md)                   |
| **Functional**| Entity Curation         | [Configuration Guide](docs/operators/entity_curation/entity_curation_config.md)         |
| **Functional**| Merge                   | [Configuration Guide](docs/operators/merge/merge_operator_config.md)                    |
| **Functional**| NOOP                    | [Configuration Guide](docs/operators/noop/noop_config.md)                               |
| **Quality**   | PII & HAP Detection     | [Configuration Guide](docs/operators/pii_and_hap/pii_and_hap_config.md)                 |
| **Quality**   | Language Detection      | [Configuration Guide](docs/operators/language_detection/language_detection_config.md)   |
| **Quality**   | Document Classifier     | [Configuration Guide](docs/operators/document_classifier/document_classifier_config.md) |
| **Quality**   | SQL Filter              | [Configuration Guide](docs/operators/sql_filter/sql_filter_config.md)                   |
| **Quality**   | Readability             | [Configuration Guide](docs/operators/readability/readability_config.md)                 |
| **Quality**   | Redaction               | [Configuration Guide](docs/operators/redaction/redaction_config.md)                     |
| **Quality**   | Deduplication           | [Configuration Guide](docs/operators/ededup/ededup_config.md)                           |
| **Quality**   | ML Enrichment           | [Configuration Guide](docs/operators/ml_enrichment/ml_enrichment_config.md)             |
| **Quality**   | Document Quality        | [Configuration Guide](docs/operators/doc_quality/doc_quality_config.md)                 |
| **VectorDB**  | VectorDB                | [Configuration Guide](docs/operators/vectordb/vectordb_operator_config.md)              |
| **Storage**   | Document Set            | [Configuration Guide](docs/operators/document_set/document_set_config.md)               |

### Additional Resources

- **[Example Flows](examples/)** - Sample flow configurations and use cases
- **[DatasiftFlowManager Examples](examples/datasift_flow_manager/)** - Programmatic flow execution guide

---

## Available Operators

### Vector Database Operators

- **OpenSearch** - Vector similarity search with multiple KNN engines (FAISS, Lucene, nmslib, jVector)
  - See [OpenSearch Documentation](docs/opensearch/) - Complete setup and usage guide
  - See [Operator Reference](docs/operators/vectordb/opensearch.md) - Technical API documentation
  - See [Integration Example](examples/opensearch_example_README.md) - Code examples
- **Milvus** - High-performance vector database with multiple index types (HNSW, IVF_FLAT, FLAT)
  - Supports both standalone Milvus and wx.data deployments
  - Configurable similarity metrics (L2, IP, COSINE)

### Ingest Operators

- **Local Folder** - Ingest documents from local filesystem
- **Cloud/Object Storage** - Ingest documents from multiple cloud providers ([see full list](docs/operators/ingest_source/ingest_source.md#supported-providers)):
  - Amazon S3 (supports both folder and file-level ingestion)
  - IBM Cloud Object Storage (COS)
  - Microsoft SharePoint
  - Microsoft OneDrive
  - Google Drive
  - Box
  - Custom LangChain-compatible loaders
- **CSV** - Ingest structured data from CSV files
- **Web Pages** - Ingest web content with the `WebPageSourceAdapter`, backed by LangChain `RecursiveUrlLoader` for recursive crawling

**Note:** Amazon S3 is the only provider that supports file-level ingestion (e.g., `prefix: "documents/report.pdf"`). Other providers only support folder-level ingestion.

For detailed configuration and usage of each provider, see the [Ingest Source Operator documentation](docs/operators/ingest_source/ingest_source.md).

### Extract Operators

- **ExtractOperator** - Document text and entity extraction with multiple provider support
  - Text extraction: Docling (local/remote), OCR, VLM, ASR pipelines
  - Entity extraction: LiteLLM (100+ providers), WatsonX.ai, Docling templates
  - Hexagonal architecture with pluggable adapters

### Chunking Operators

- **Docling Chunker** - Chunk documents using Docling's chunking capabilities
- **Semantic Chunker** - Semantic-aware document chunking

### Language Operators

- **Language Detection** - Detect document language
- **Readability** - Assess document readability scores

### Quality Operators

- **PII and HAP Detection** - Detect Personally Identifiable Information and Hate/Abuse/Profanity content
  - See [PII and HAP Documentation](docs/operators/pii_and_hap/pii_and_hap.md) - Complete setup and usage guide
  - Multiple provider support: Ollama (local), WatsonX.ai (enterprise), LiteLLM (100+ providers)
  - Hexagonal architecture with pluggable adapters

### Utility Operators

- **Branching** - Conditional flow branching
- **No-op** - Pass-through operator for testing

### Storage Operators

- **Document Set** - Persistent storage for pipeline data using DuckDB
  - Store PyArrow tables in named document collections
  - Automatic schema evolution and metrics computation
  - Incremental updates with soft-delete cleanup
  - Pass-through design for downstream operator chaining
  - REST API for document set management


### Custom Operators

Datasift supports loading custom operators from external locations, enabling you to extend the framework with your own operators without modifying the core codebase.

**Supported Sources:**
- Python packages (installed via pip or in PYTHONPATH)
- Local filesystem (single files or directories)
- S3 buckets (with local caching)

**Configuration:**
```bash
export DATASIFT_CUSTOM_OPERATORS="my_operators,/path/to/operators,s3://bucket/operators"
```

**Documentation:**
- [Custom Operator Guide](examples/custom_operators/README.md) - Complete guide with examples
- [Test Flow](tests/sample_test_flows/custom_operators/) - Working example flow

Custom operators are automatically discovered, validated, and registered at runtime. Custom operators can override built-in datasift operators based on priority resolution.

## Project Structure

```
datasift-opensource/
├── src/datasift/              # Main Python package
│   ├── api/                   # FastAPI application
│   │   ├── routes/           # API route handlers
│   │   ├── dto/              # Data transfer objects
│   │   ├── middleware/       # API middleware
│   │   ├── auth/             # Authentication
│   │   └── main.py           # FastAPI app entry point
│   ├── cli/                   # CLI tools
│   │   └── datasift_cli.py   # Command-line interface
│   ├── core/                  # Core framework
│   │   ├── operators/        # Operator implementations
│   │   ├── orchestration/    # Workflow orchestration
│   │   ├── flows/            # Flow management
│   │   └── job_management/   # Job tracking
│   ├── integrations/          # External service integrations
│   │   ├── ollama/           # Ollama LLM integration
│   │   ├── watsonx/          # IBM watsonx.ai integration
│   │   ├── docling/          # Docling document processing
│   │   └── litellm/          # LiteLLM multi-provider
│   ├── storage/               # Storage backends
│   ├── utils/                 # Utility functions
│   └── lib/                   # Library components
├── src/datasift_opensource/   # UI components
│   └── ui/                    # Gradio and Reflex UIs
├── tests/                     # Test suites
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── fixtures/              # Test fixtures
├── docs/                      # Documentation
├── examples/                  # Example flows
├── Dockerfile                 # Docker configuration
└── README.md
```

## Job Runs and Execution Tracking

datasift-opensource includes a pluggable job-management subsystem for tracking job runs, node execution state, micro-batch progress, and terminal outcomes.

### Job Stats Components

- **[`JobStatsService`](src/datasift/core/job_management/domain/ports/job_stats_service.py)** - orchestration-facing service contract
- **[`JobStatsStore`](src/datasift/core/job_management/domain/ports/job_stats_store.py)** - pluggable persistence contract for job and node stats
- **[`JobTrackerService`](src/datasift/core/job_management/adapters/services/job_tracker_service.py)** - production implementation built on the new hexagonal architecture
- **[`NodeStatsAggregator`](src/datasift/core/job_management/application/services/node_stats_aggregator.py)** - read-side aggregation of batch node stats
- **[`JobManagementFactory`](src/datasift/core/job_management/adapters/config/job_management_factory.py)** - backend selection and dependency wiring

### Supported Backends

- **In-memory** - useful for tests and local development
- **JSON storage** - simple persistent storage for single-host setups
- **PostgreSQL** - durable storage with stronger concurrency behavior for multi-process and distributed execution

### API Surface

Job run APIs are exposed through [`job_runs.py`](src/datasift/api/routes/job_runs.py) for:
- creating job runs
- listing job runs
- reading current job run status
- canceling job runs
- deleting job runs

### User Configuration

The primary user-facing runtime configuration lives in [`datasift-config.yaml`](datasift-config.yaml), including:

- `assets_management.flow_repository` for the flow repository location
- `job_management.storage.type` for the job stats storage backend (`filesystem`, `duckdb`, `postgresql`, `inmemory`)
- `job_management.storage.config` for backend-specific job stats settings
- `incremental_metadata.storage.type` for incremental metadata backend selection (`filesystem`, `postgresql`)
- `incremental_metadata.storage.config` for backend-specific incremental metadata settings
- `incremental_metadata.postgres` for PostgreSQL connection details when the incremental metadata backend is `postgresql`

Incremental metadata configuration is centralized in `datasift-config.yaml`. Flow-level `incremental_metadata` configuration is no longer the supported configuration source.

Environment overrides can replace config values at runtime, including:

- `DATASIFT_CONFIG_PATH`
- `DATASIFT_STORAGE_BACKEND`
- `DATASIFT_FRAMEWORK_TYPE`
- `DATASIFT_JOB_STATS_BASE_DIR`

Sensitive values such as PostgreSQL passwords should be supplied through environment variable substitution in `datasift-config.yaml`, for example `${POSTGRES_PASSWORD}` or `${INCR_META_DB_PASSWORD}`.

When using distributed Prefect workers, all workers must resolve job stats storage and incremental metadata storage consistently. File-based backends such as Filesystem (for incremental metadata) require a shared filesystem path for submitters and workers. PostgreSQL storage requires matching backend configuration and connection settings in worker environments. If work-pool env values are not set explicitly, worker runtime inherits the submitter's effective configuration resolved from environment variables and [`datasift-config.yaml`](datasift-config.yaml). See [USER_GUIDE_PIPELINE_SETUP.md](USER_GUIDE_PIPELINE_SETUP.md#incremental-metadata-configuration) for backend examples.

## Setup

**For complete setup instructions, see:**
- **[Quick Start Guide](QUICKSTART.md)** - Fast-track setup (5 minutes)
- **[Complete Pipeline Setup Guide](USER_GUIDE_PIPELINE_SETUP.md)** - Detailed setup with troubleshooting

---

## Running the Application

**Quick Links:**

- [CLI Orchestrator](#cli-orchestrator) - Command-line flow execution (recommended for new users)
- [DatasiftFlowManager API](#datasiftflowmanager-api) - Programmatic Python API

### CLI Orchestrator

Run the CLI orchestrator:

```bash
# Using uv
uv run datasift-orchestrator --help

# Or with activated venv
datasift-orchestrator --help
```

**See also:**

- [Complete Pipeline Setup Guide](USER_GUIDE_PIPELINE_SETUP.md) - Step-by-step flow execution examples
- [Example Flows](examples/) - Sample flow configurations
- [Operator Reference](docs/reference/OPERATORS.md) - Operator parameters and configuration options

#### Executing Flows

Execute a flow definition from a JSON file:

```bash
datasift-orchestrator --flow-file path/to/flow.json
```

**Controlling Output Verbosity:**

Use the `DS_LOG_LEVEL` environment variable to control console output detail:

```bash
# Clean summaries with operator progress (recommended)
DS_LOG_LEVEL=INFO datasift-orchestrator --flow-file flow.json

# Detailed debugging information
DS_LOG_LEVEL=DEBUG datasift-orchestrator --flow-file flow.json

# Minimal output (warnings and errors only)
DS_LOG_LEVEL=WARNING datasift-orchestrator --flow-file flow.json
```

The default INFO level provides formatted output showing:
- Flow execution header with operator count
- Per-operator progress with document counts and duration
- Schema changes (new columns added by each operator)
- Operator-specific metrics and metadata
- Final flow summary with per-operator statistics

#### Validating Flows

Validate a flow definition without executing it:

```bash
# Using --validate flag
datasift-orchestrator --flow-file flow.json --validate

# Using validate-flow command
datasift-orchestrator validate-flow flow.json
```

#### Listing Operators

List all available operators:

```bash
# Summary view - shows table with Owner, Attributes, Features columns
# Operators sorted by category: Ingest, Extract, Quality, Functional, VectorDB, Storage
datasift-orchestrator --list-operators

# Detailed view - shows full operator details with all parameters
datasift-orchestrator --list-operators --verbose
```

**Summary table format:**
- **Owner**: Operator name
- **Attributes**: Count of configurable parameters
- **Features**: Count of special features/capabilities
- **Categories**: Ingest, Extract, Quality, Functional, VectorDB, Storage

### DatasiftFlowManager API

Execute datasift flows programmatically using Python:

```python
from datasift.lib.datasift_flow_manager import DatasiftFlowManager

# Execute flow from file
manager = DatasiftFlowManager(
    flow_file="path/to/flow.json"
)
result = manager.execute()

# Execute flow from dictionary
flow_dict = {
    "flow_name": "my-pipeline",
    "flow": [
        {
            "name": "ingest",
            "type": "ingest_local",
            "config": {"paths": "./data"}
        },
        {
            "name": "extract",
            "type": "extract_operator",
            "depends_on": ["ingest"],
            "config": {}
        }
    ]
}
manager = DatasiftFlowManager(flow_def=flow_dict)
result = manager.execute()

# List available operators
operators = DatasiftFlowManager.list_operators()
```

**See also:**

- [DatasiftFlowManager Examples](examples/datasift_flow_manager/) - Complete usage guide with code samples
- [Quick Start Example](examples/datasift_flow_manager/01_execute_from_file.py) - Basic flow execution
- [CLI Orchestrator](#cli-orchestrator) - Alternative command-line interface
- [Operator Reference](docs/reference/OPERATORS.md) - Complete API documentation

---

## Distributed Execution

Datasift-opensource supports multiple execution modes for scaling from local development to enterprise production deployments.

### Execution Modes

| Mode             | Use Case               | Infrastructure        | Scalability  |
| ---------------- | ---------------------- | --------------------- | ------------ |
| **Thread Pool**  | Development, testing   | Single machine        | Limited      |
| **Process Pool** | Single-node production | Single machine        | CPU cores    |
| **Docker**       | Multi-host deployments | Docker infrastructure | Horizontal   |

### Quick Start

**Local Development (Default):**

```bash
# No configuration needed - uses thread pool by default
datasift-orchestrator --flow-file my-flow.json
```

**Process Pool:**

```json
{
  "work_pool": {
    "enabled": true,
    "type": "process",
    "name": "datasift-process-pool",
    "max_workers": 4
  }
}
```

**Docker:**

```json
{
  "work_pool": {
    "enabled": true,
    "type": "docker",
    "name": "datasift-docker-pool",
    "image": "datasift-opensource:latest",
    "batch_storage": {
      "type": "local",
      "base_path": "/app/data/batches"
    }
  }
}
```

### Batch Storage

Distributed execution requires serializing batches for cross-process/container communication:

- **Inline Storage**: In-memory (thread pool only)
- **Local Filesystem**: Parquet files on shared storage (process pool, Docker)

**Note:** Cloud storage backends (S3, etc.) are not currently supported.

### Setup Work Pools

**Docker:**

```bash
# Create work pool
prefect work-pool create datasift-docker-pool --type docker

# Start workers
docker-compose -f docker/docker-compose.worker.yml up -d
```

**See also:**

- [Architecture Documentation](ARCHITECTURE.md#distributed-execution-architecture) - Detailed architecture and design
- [Deployment Patterns](ARCHITECTURE.md#deployment-patterns) - Complete deployment guides
- [Docker Deployment](#docker-deployment) - Docker setup and configuration

---

## Docker Deployment

### Build Docker Image

Build the Docker image for distributed execution:

```bash
docker build -t datasift-opensource:latest -f docker/Dockerfile .
```

### Local Development

Run the FastAPI server:

```bash
docker run -p 8000:8000 datasift-opensource:latest
```

Run the CLI orchestrator:

```bash
docker run datasift-opensource:latest datasift-orchestrator --help
```

### Distributed Execution with Docker

**1. Create Work Pool:**

```bash
prefect work-pool create datasift-docker-pool --type docker
```

**2. Start Workers with Docker Compose:**

Create `docker-compose.worker.yml`:

```yaml
version: "3.8"
services:
  worker:
    image: datasift-opensource:latest
    command: prefect worker start --pool datasift-docker-pool
    volumes:
      - datasift-batches:/app/data/batches
    environment:
      - PREFECT_API_URL=http://prefect-server:4200/api
    deploy:
      replicas: 3

volumes:
  datasift-batches:
```

Start workers:

```bash
docker-compose -f docker-compose.worker.yml up -d
```

**3. Configure Flow for Docker Execution:**

Add work pool configuration to your flow JSON:

```json
{
  "work_pool": {
    "enabled": true,
    "type": "docker",
    "name": "datasift-docker-pool",
    "image": "datasift-opensource:latest",
    "batch_storage": {
      "type": "local",
      "base_path": "/app/data/batches"
    }
  }
}
```

**4. Execute Flow:**

```bash
datasift-orchestrator --flow-file my-flow.json
```

### Build Wheel

Build a wheel distribution:

```bash
# From project root
uv build --wheel
```

The wheel file will be created in the `dist/` directory.

**See also:**

- [Distributed Execution](#distributed-execution) - Overview of execution modes
- [Docker Deployment](#docker-deployment) - Docker setup
- [Architecture Documentation](ARCHITECTURE.md#deployment-patterns) - Detailed deployment patterns
- [Development](#development) - Development workflow and tools
- [Testing](#testing) - Running tests and coverage

---

## Development

**Quick Links:**

- [Adding Dependencies](#adding-dependencies) - Managing project dependencies
- [Testing](#testing) - Running tests and coverage
- [Code Quality](#code-quality) - Pre-commit hooks and linting

### Adding Dependencies

Add a new dependency (from project root):

```bash
# From project root
uv add <package-name>==<version>  # Always specify a fixed version
```

Add a development dependency:

```bash
# From project root
uv add --dev <package-name>==<version>  # Always specify a fixed version
```

**Important**: After adding any new package, always follow these steps:

1. Sync dependencies and update lock file:

```bash
# From project root
uv sync --extra dev
```

2. Generate updated requirements.txt:

```bash
# From project root
uv pip compile pyproject.toml -o requirements.txt
```

3. Install package in editable mode and run tests:

```bash
# From project root
uv pip install -e .
export TEST_CP4D_USERNAME=udp_unittest_user
export TEST_CP4D_PASSWORD="udp_unittest_pass@123"  # pragma: allowlist secret
uv run pytest tests/ -v
```

### Testing

The test suite uses pytest with colored output, coverage tracking, and test markers for easy filtering.

#### Quick Start

Run tests from the **project root** (recommended):

```bash
# Activate virtual environment (from project root)
source .venv/bin/activate

# Run all tests with colored output
uv run pytest -v

# Run with coverage report
uv run pytest -v --cov=src --cov-report=html

# Run only unit tests
uv run pytest -m unit -v

# Run only integration tests
uv run pytest -m integration -v

# Show 10 slowest tests
uv run pytest --durations=10

# Run specific test file
uv run pytest tests/unit/operators/embeddings/test_embeddings_operator.py -v
```

#### Test Organization

Tests are organized by type and automatically marked:

- **Unit tests**: `tests/unit/` - Fast, isolated tests
- **Integration tests**: `tests/integration/` - Tests with external dependencies

#### Filtering Tests by Speed

Tests can be filtered by execution speed using the `@pytest.mark.slow` marker:

```bash
# Run only fast tests (excludes @pytest.mark.slow)
uv run pytest -m "not slow" -v

# Run only slow tests
uv run pytest -m slow -v

# Run fast unit tests only
uv run pytest -m "unit and not slow" -v
```

**Note**: Jenkins CI automatically excludes slow tests to keep builds fast. Slow tests are available for local development and can be run manually when needed.

For detailed information on test markers, filtering strategies, and CI configuration, see the [Testing section in CONTRIBUTING.md](CONTRIBUTING.md#testing).

#### Coverage Reports

After running tests with coverage, open the HTML report:

```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

Coverage configuration is in `.coveragerc` at the project root.

#### Test Configuration

- **pytest.ini**: Main pytest configuration (project root)
- **tests/conftest.py**: Shared fixtures and automatic path setup
- **.coveragerc**: Coverage configuration

**Note**: Python path setup is automatic via `tests/conftest.py`. No manual `PYTHONPATH` configuration needed.

**See also:**

- [Code Quality](#code-quality) - Pre-commit hooks and linting tools
- [Complete Pipeline Setup Guide](USER_GUIDE_PIPELINE_SETUP.md#7-verification-and-testing) - Testing best practices
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common test failures and solutions

### Code Quality

#### Pre-commit Hooks

This project uses pre-commit hooks to automatically check and format code before commits. The hooks include:

- **Ruff**: Python linting and formatting
- **detect-secrets**: Prevent committing secrets
- **uv-export**: Keep requirements.txt in sync with pyproject.toml

**Setup pre-commit hooks:**

```bash
# Install pre-commit hooks (one-time setup, from project root)
uv run pre-commit install
```

**Run hooks manually:**

```bash
# Run on all files
uv run pre-commit run --all-files

# Run on staged files only
uv run pre-commit run

# Run specific hook
uv run pre-commit run ruff --all-files
uv run pre-commit run ruff-format --all-files
```

**Update hook versions:**

```bash
uv run pre-commit autoupdate
```

Once installed, the hooks will automatically run on `git commit`. If any hook fails, the commit will be blocked until issues are fixed.

#### Manual Code Quality Tools

Format code with black:

```bash
uv run black .
```

Check code style with flake8:

```bash
uv run flake8 .
```

Type checking with mypy:

```bash
uv run mypy .
```

Run Ruff manually:

```bash
# Check for issues
uv run ruff check .

# Fix issues automatically
uv run ruff check --fix .

# Format code
uv run ruff format .
```

**See also:**

- [Testing](#testing) - Running tests before committing
- [Adding Dependencies](#adding-dependencies) - Managing dependencies

---

## API Development

### Adding New Routes

1. Create a new route file in `src/datasift/app/routes/`
2. Define your route handlers
3. Import and include the router in `src/datasift/app/main.py`

Example:

```python
# src/datasift/app/routes/example.py
from fastapi import APIRouter

router = APIRouter(prefix="/example", tags=["example"])

@router.get("/")
async def get_example():
    return {"message": "Example endpoint"}
```

Then in `main.py`:

```python
from .routes import example
app.include_router(example.router)
```

**See also:**

- [FastAPI Server](#fastapi-server-todo) - Running the API server
- [Environment Variables](#environment-variables) - Configuration options
- [Operator Reference](docs/reference/OPERATORS.md) - Operator API documentation

---

## Environment Variables

Create a `.env` file in the project root for environment-specific configuration:

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true

# Job Stats Storage Configuration
DATASIFT_STORAGE_BACKEND=json  # Options: inmemory, json, postgresql
DATASIFT_POSTGRES_HOST=localhost
DATASIFT_POSTGRES_PORT=5432
DATASIFT_POSTGRES_DB=datasift
DATASIFT_POSTGRES_USER=datasift_user
DATASIFT_POSTGRES_PASSWORD=your_password  # Required for postgresql backend

# Add other environment variables as needed
```

**See also:**

- [Complete Pipeline Setup Guide](USER_GUIDE_PIPELINE_SETUP.md) - Environment setup examples
- [Operator Specific Setup](#operator-specific-setup) - Required services configuration
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Configuration issues

---

## Operator Specific Setup

**For operator-specific configuration (Ollama, OpenSearch, Milvus), see:**
- **[Quick Start Guide](QUICKSTART.md)** - Quick setup instructions
- **[Complete Pipeline Setup Guide](USER_GUIDE_PIPELINE_SETUP.md)** - Detailed configuration guides

---

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for detailed information on:

- Code of conduct and contribution guidelines
- Development setup and workflow
- Testing requirements and best practices
- Code style and quality standards
- Pull request process

**Quick start for contributors:**

1. Create a new branch for your feature
2. Make your changes
3. Run tests and code quality checks
4. Submit a pull request

**See also:**

- [Development](#development) - Development workflow
- [Testing](#testing) - Running tests
- [Code Quality](#code-quality) - Pre-commit hooks and linting
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common issues and solutions
