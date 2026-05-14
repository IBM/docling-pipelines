# datasift-operators

This repository contains the datasift operators with FastAPI server, CLI orchestrator, and UI components.

## Table of Contents

- [datasift-operators](#datasift-operators)
  - [Table of Contents](#table-of-contents)
  - [Documentation](#documentation)
    - [Getting Started](#getting-started)
    - [Architecture \& Design](#architecture--design)
    - [API \& Reference](#api--reference)
    - [Operator Documentation](#operator-documentation)
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
  - [Project Structure](#project-structure)
  - [Setup](#setup)
    - [Quick Start (Automated Setup)](#quick-start-automated-setup)
    - [Manual Setup](#manual-setup)
      - [Prerequisites](#prerequisites)
      - [Installation](#installation)
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
  - [Kubernetes Deployment](#kubernetes-deployment)
    - [Prerequisites](#prerequisites-1)
    - [Quick Start](#quick-start-1)
    - [Kubernetes Manifests](#kubernetes-manifests)
    - [Resource Requirements](#resource-requirements)
    - [Monitoring and Scaling](#monitoring-and-scaling)
    - [Storage Configuration](#storage-configuration)
    - [Security](#security)
    - [Troubleshooting](#troubleshooting)
  - [Development](#development)
    - [Adding Dependencies](#adding-dependencies)
    - [Testing](#testing)
      - [Quick Start](#quick-start-2)
      - [Test Organization](#test-organization)
      - [Coverage Reports](#coverage-reports)
      - [Test Configuration](#test-configuration)
    - [Code Quality](#code-quality)
      - [Pre-commit Hooks](#pre-commit-hooks)
      - [Manual Code Quality Tools](#manual-code-quality-tools)
  - [API Development](#api-development)
    - [Adding New Routes](#adding-new-routes)
  - [Environment Variables](#environment-variables)
  - [Operator Specific Setup](#operator-specific-setup)
    - [Embeddings Operator — Ollama Setup](#embeddings-operator--ollama-setup)
      - [Step 1 — Install Ollama](#step-1--install-ollama)
      - [Step 2 — Start the Ollama server](#step-2--start-the-ollama-server)
      - [Step 3 — Pull a model](#step-3--pull-a-model)
      - [Step 4 — Install the Python package](#step-4--install-the-python-package)
    - [OpenSearch Vector Store](#opensearch-vector-store)
      - [Step 1 — Start OpenSearch](#step-1--start-opensearch)
      - [Step 2 — Verify it's running](#step-2--verify-its-running)
      - [Step 3 — Configure environment variables](#step-3--configure-environment-variables)
      - [Step 4 — Stop OpenSearch](#step-4--stop-opensearch)
  - [Contributing](#contributing)
    - [Step 4 — Stop OpenSearch](#step-4--stop-opensearch-1)
  - [Contributing](#contributing-1)

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

### Architecture & Design

- **[Architecture Documentation](ARCHITECTURE.md)** - System design and architectural decisions
- **[Job Stats Metadata Aggregation Guide](docs/job_stats_management/NODE_METADATA_AGGREGATION_STRATEGY.md)** - Batch metadata aggregation rules and maintainer update requirements

### API & Reference

- **[Operator Reference](OPERATOR_REFERENCE.md)** - Complete API documentation for operators and core components
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions

### Operator Documentation

- **[OpenSearch Documentation](docs/opensearch/)** - Complete setup and usage guide for vector search
- **[OpenSearch Operator Reference](docs/operators/opensearch.md)** - Technical API documentation
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
  - See [Operator Reference](docs/operators/opensearch.md) - Technical API documentation
  - See [Integration Example](examples/opensearch_example_README.md) - Code examples

### Ingest Operators

- **Local Folder** - Ingest documents from local filesystem
- **Cloud/Object Storage** - Ingest documents from multiple cloud providers ([see full list](docs/operators/ingest_source/ingest_source.md#supported-providers)):
  - Amazon S3
  - IBM Cloud Object Storage (COS)
  - Microsoft SharePoint
  - Microsoft OneDrive
  - Google Drive
  - Box
  - Custom LangChain-compatible loaders
- **CSV** - Ingest structured data from CSV files
- **Web Pages** - Ingest web content with the `WebPageSourceAdapter`, backed by LangChain `RecursiveUrlLoader` for recursive crawling

For detailed configuration and usage of each provider, see the [Ingest Source Operator documentation](docs/operators/ingest_source/ingest_source.md).

### Extract Operators

- **ExtractOperator** - Unified extraction operator with multiple adapters
  - **Text Extraction Modes**:
    - `docling_library`: Local Docling extraction with optional VLM (Vision-Language Model) and ASR (Automatic Speech Recognition) pipelines
    - `docling_serve`: Remote extraction via Docling Serve API with OCR support
  - **Entity Extraction Modes**:
    - `ollama`: LLM-based entity extraction using Ollama models
    - `docling`: Template-based entity extraction using Docling templates
    - `litellm`: Multi-provider LLM extraction (OpenAI, Anthropic, Cohere, etc.)
  - Includes estimated page count output and aggregate page metadata
    - `none`: No entity extraction (default)
  - Supports dual-mode operation: text and entity extraction in a single operator

### Chunking Operators

- **Docling Chunker** - Chunk documents using Docling's chunking capabilities
- **Semantic Chunker** - Semantic-aware document chunking

### Language Operators

- **Language Detection** - Detect document language
- **Readability** - Assess document readability scores

### Quality Operators

- **PII and HAP Detection** - Detect Personally Identifiable Information and Hate/Abuse/Profanity content
  - See [PII and HAP Documentation](docs/operators/pii_and_hap.md) - Complete setup and usage guide
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
- [`assets_management.flow_repository`](datasift-config.yaml#L1) for the flow repository location
- [`job_management.framework.type`](datasift-config.yaml#L9) for the job framework type
- [`job_management.store.type`](datasift-config.yaml#L12) for the job stats store backend (inmemory, json, duckdb, postgresql)
- [`job_management.store.config`](datasift-config.yaml#L15) for backend-specific settings such as JSON `base_dir`, DuckDB `database_path`, or PostgreSQL connection details

Environment overrides can replace config values at runtime, including:
- `DATASIFT_CONFIG_PATH`
- `DATASIFT_STORAGE_BACKEND`
- `DATASIFT_FRAMEWORK_TYPE`
- `DATASIFT_JOB_STATS_BASE_DIR`
- `DATASIFT_POSTGRES_HOST`
- `DATASIFT_POSTGRES_PORT`
- `DATASIFT_POSTGRES_DB`
- `DATASIFT_POSTGRES_USER`
- `DATASIFT_POSTGRES_PASSWORD`

When using distributed Prefect workers, all workers must resolve job stats storage consistently. JSON storage requires a shared filesystem path. PostgreSQL storage requires matching backend configuration and connection settings in worker environments. If work-pool env values are not set explicitly, worker runtime inherits the submitter's effective job-management configuration resolved from environment variables and [`datasift-config.yaml`](datasift-config.yaml).

## Setup

### Quick Start (Automated Setup)

**New users: Use the automated setup script to install everything in one command!**

```bash
./scripts/setup_datasift_environment.sh
```

This script automatically installs and configures:

- Python 3.12 verification
- uv package manager
- Ollama with default models (granite4, llama3.2, nomic-embed-text)
- OpenSearch with Dashboards
- Python virtual environment and dependencies

**For detailed setup options and troubleshooting, see [Complete Pipeline Setup Guide](USER_GUIDE_PIPELINE_SETUP.md#quick-start-with-automated-setup)**

**See also:**

- [Manual Setup](#manual-setup) - Step-by-step manual installation
- [Operator Specific Setup](#operator-specific-setup) - Configure Ollama and OpenSearch
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common setup issues and solutions

---

### Manual Setup

**Prefer automated setup?** See [Quick Start (Automated Setup)](#quick-start-automated-setup) above.

This project uses [uv](https://docs.astral.sh/uv/) for fast Python package management.

#### Prerequisites

Install uv if you haven't already:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd datasift-opensource
```

2. Create a virtual environment and install dependencies:

```bash
# From project root
uv sync --extra dev
```

This will:

- Create a virtual environment in `.venv/` at project root
- Install all project dependencies
- Install development dependencies

3. Activate the virtual environment:

```bash
# From project root
source .venv/bin/activate
```

**See also:**

- [Complete Pipeline Setup Guide](USER_GUIDE_PIPELINE_SETUP.md) - Detailed setup with troubleshooting
- [Operator Specific Setup](#operator-specific-setup) - Configure Ollama and OpenSearch
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common installation issues

---

## Running the Application

**Quick Links:**

- [CLI Orchestrator](#cli-orchestrator) - Command-line flow execution (recommended for new users)
- [DatasiftFlowManager API](#datasiftflowmanager-api) - Programmatic Python API
- [FastAPI Server](#fastapi-server-todo) - REST API (under development)

### FastAPI Server (TODO)

<details> FASTApi Server 
<summary>Start the FastAPI server with uvicorn:</summary>

```bash
# Using uvicorn from project root
uvicorn datasift.api.main:app --reload --host 0.0.0.0 --port 8000

# Or using uv from project root
uv run uvicorn datasift.api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc

</details>

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
- [Operator Reference](OPERATOR_REFERENCE.md) - Operator parameters and configuration options

#### Executing Flows

Execute a flow definition from a JSON file:

```bash
datasift-orchestrator --flow-file path/to/flow.json
```

With custom log level:

```bash
datasift-orchestrator --flow-file flow.json --log-level debug
```

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
    flow_file="path/to/flow.json",
    log_level="info",
)
result = manager.execute()

# Execute flow from dictionary
flow_dict = {
    "nodes": [...],
    "edges": [...]
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
- [Operator Reference](OPERATOR_REFERENCE.md) - Complete API documentation

---

## Distributed Execution

Datasift-opensource supports multiple execution modes for scaling from local development to enterprise production deployments.

### Execution Modes

| Mode             | Use Case               | Infrastructure        | Scalability  |
| ---------------- | ---------------------- | --------------------- | ------------ |
| **Thread Pool**  | Development, testing   | Single machine        | Limited      |
| **Process Pool** | Single-node production | Single machine        | CPU cores    |
| **Docker**       | Multi-host deployments | Docker infrastructure | Horizontal   |
| **Kubernetes**   | Enterprise production  | Kubernetes cluster    | Auto-scaling |

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

**Kubernetes:**

```json
{
  "work_pool": {
    "enabled": true,
    "type": "kubernetes",
    "name": "datasift-k8s-pool",
    "namespace": "datasift-production",
    "image": "myregistry.io/datasift-opensource:v1.0.0",
    "batch_storage": {
      "type": "local",
      "base_path": "/shared/batches"
    }
  }
}
```

### Batch Storage

Distributed execution requires serializing batches for cross-process/container communication:

- **Inline Storage**: In-memory (thread pool only)
- **Local Filesystem**: Parquet files on shared storage (process pool, Docker, Kubernetes)

**Note:** Cloud storage backends (S3, etc.) are not currently supported.

### Setup Work Pools

**Docker:**

```bash
# Create work pool
prefect work-pool create datasift-docker-pool --type docker

# Start workers
docker-compose -f docker/docker-compose.worker.yml up -d
```

**Kubernetes:**

```bash
# Create work pool
prefect work-pool create datasift-k8s-pool --type kubernetes

# Deploy workers
kubectl apply -f k8s-deployment-examples/prefect-worker.yaml
```

**See also:**

- [Architecture Documentation](ARCHITECTURE.md#distributed-execution-architecture) - Detailed architecture and design
- [Deployment Patterns](ARCHITECTURE.md#deployment-patterns) - Complete deployment guides
- [Docker Deployment](#docker-deployment) - Docker setup and configuration
- [Kubernetes Deployment](#kubernetes-deployment) - Kubernetes setup and configuration

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

---

## Kubernetes Deployment

Deploy datasift-opensource on Kubernetes for enterprise-scale production workloads with auto-scaling and high availability.

### Prerequisites

- Kubernetes cluster (1.19+)
- kubectl configured
- Prefect server accessible from cluster
- Container registry access

### Quick Start

**1. Create Namespace:**

```bash
kubectl create namespace datasift-production
```

**2. Deploy Persistent Volume:**

Create shared storage for batch processing:

```bash
kubectl apply -f k8s-deployment-examples/persistent-volume.yaml
```

**3. Create Work Pool:**

```bash
prefect work-pool create datasift-k8s-pool --type kubernetes
```

**4. Deploy Workers:**

```bash
kubectl apply -f k8s-deployment-examples/prefect-worker.yaml
```

**5. Configure Flow:**

Add work pool configuration to your flow JSON:

```json
{
  "work_pool": {
    "enabled": true,
    "type": "kubernetes",
    "name": "datasift-k8s-pool",
    "namespace": "datasift-production",
    "image": "myregistry.io/datasift-opensource:v1.0.0",
    "batch_storage": {
      "type": "local",
      "base_path": "/shared/batches"
    }
  }
}
```

**6. Execute Flow:**

```bash
datasift-orchestrator --flow-file my-flow.json
```

### Kubernetes Manifests

The `k8s-deployment-examples/` directory contains complete Kubernetes manifests:

**Core Components:**

- `persistent-volume.yaml` - Shared storage for batch data
- `prefect-worker.yaml` - Worker deployment with auto-scaling
- `configmap.yaml` - Configuration management
- `secrets.yaml` - Credentials management

**Example Deployment:**

```yaml
# prefect-worker.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: datasift-worker
  namespace: datasift-production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: datasift-worker
  template:
    metadata:
      labels:
        app: datasift-worker
    spec:
      containers:
        - name: worker
          image: myregistry.io/datasift-opensource:v1.0.0
          command: ["prefect", "worker", "start", "--pool", "datasift-k8s-pool"]
          volumeMounts:
            - name: batch-storage
              mountPath: /shared/batches
          resources:
            requests:
              memory: "4Gi"
              cpu: "2"
            limits:
              memory: "8Gi"
              cpu: "4"
      volumes:
        - name: batch-storage
          persistentVolumeClaim:
            claimName: datasift-batches-pvc
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: datasift-worker-hpa
  namespace: datasift-production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: datasift-worker
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### Resource Requirements

**Per Worker Pod:**

- **CPU**: 2-4 cores
- **Memory**: 4-8 GB
- **Storage**: 50-100 GB shared PVC

**Cluster Recommendations:**

- **Development**: 3 nodes, 8 GB RAM each
- **Production**: 5+ nodes, 16 GB RAM each
- **High-scale**: 10+ nodes with auto-scaling

### Monitoring and Scaling

**View Worker Status:**

```bash
kubectl get pods -n datasift-production -l app=datasift-worker
```

**View Logs:**

```bash
kubectl logs -n datasift-production -l app=datasift-worker --tail=100 -f
```

**Scale Workers Manually:**

```bash
kubectl scale deployment datasift-worker -n datasift-production --replicas=5
```

**Check Auto-scaling:**

```bash
kubectl get hpa -n datasift-production
```

### Storage Configuration

**Persistent Volume Options:**

1. **NFS**: Shared network filesystem
2. **Cloud Provider**: EBS (AWS), Persistent Disk (GCP), Azure Disk
3. **Distributed Storage**: Ceph, GlusterFS

**Example NFS Configuration:**

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: datasift-batches-pv
spec:
  capacity:
    storage: 100Gi
  accessModes:
    - ReadWriteMany
  nfs:
    server: nfs-server.example.com
    path: /exports/datasift-batches
```

### Security

**Create Secrets:**

```bash
kubectl create secret generic datasift-secrets \
  --from-literal=prefect-api-key=your-api-key \
  -n datasift-production
```

**Use in Deployment:**

```yaml
env:
  - name: PREFECT_API_KEY
    valueFrom:
      secretKeyRef:
        name: datasift-secrets
        key: prefect-api-key
```

### Troubleshooting

**Worker Not Starting:**

```bash
kubectl describe pod -n datasift-production -l app=datasift-worker
```

**Storage Issues:**

```bash
kubectl get pvc -n datasift-production
kubectl describe pvc datasift-batches-pvc -n datasift-production
```

**Network Issues:**

```bash
kubectl exec -it -n datasift-production <pod-name> -- curl http://prefect-server:4200/api/health
```

**See also:**

- [Distributed Execution](#distributed-execution) - Overview of execution modes
- [Docker Deployment](#docker-deployment) - Docker setup
- [Architecture Documentation](ARCHITECTURE.md#deployment-patterns) - Detailed deployment patterns
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common issues and solutions

The wheel file will be created in the `dist/` directory.

**See also:**

- [Distributed Execution](#distributed-execution) - Overview of execution modes
- [Kubernetes Deployment](#kubernetes-deployment) - Kubernetes setup
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
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
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

# Set PYTHONPATH (from project root)
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"

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
- [Complete Pipeline Setup Guide](USER_GUIDE_PIPELINE_SETUP.md#verification-testing-and-troubleshooting) - Testing best practices
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
- [Operator Reference](OPERATOR_REFERENCE.md) - Operator API documentation

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

**Required for pipeline execution:** Configure these services before running flows.

**Quick Links:**

- [Embeddings Operator — Ollama Setup](#embeddings-operator--ollama-setup) - LLM and embeddings
- [OpenSearch Vector Store](#opensearch-vector-store) - Vector database

### Embeddings Operator — Ollama Setup

The [`EmbeddingsOperator`](src/datasift/core/operators/functional/embeddings/embeddings_operator.py) uses Ollama as its **default** embeddings provider (`embeddings_type = "ollama"`). Before using this operator, you must complete the following setup steps.

#### Step 1 — Install Ollama

- **macOS**: `brew install ollama` or download from https://ollama.ai/download
- **Linux**: `curl -fsSL https://ollama.ai/install.sh | sh`
- **Windows**: Download from https://ollama.ai/download

#### Step 2 — Start the Ollama server

```bash
ollama serve
```

The server runs on `http://localhost:11434` by default.

#### Step 3 — Pull a model

```bash
ollama pull granite4
```

The default model used by the operator is `granite4`. Other supported models include: `llama3`, `llama3.1`, `llama3.2`, `mistral`, `mixtral`, `codellama`, `phi`, `gemma`, `qwen`, `granite3.2:2b`, `granite3.2:8b`.

#### Step 4 — Install the Python package

```bash
pip install ollama
```

> **Note**: If Ollama is not installed, the server is not running, or no model has been pulled, the operator will raise a [`DatasiftException`](src/datasift/common/exceptions/datasift_exceptions.py) at runtime.

**See also:**

- [Complete Pipeline Setup Guide](USER_GUIDE_PIPELINE_SETUP.md#3-ollama-setup) - Detailed Ollama configuration
- [EmbeddingsOperator Documentation](src/datasift/core/operators/functional/embeddings/embeddings_operator.py) - Operator reference
- [Operator Reference](OPERATOR_REFERENCE.md) - EmbeddingsOperator parameters
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Ollama connection issues

### OpenSearch Vector Store

The [`VectorDBOperator`](src/datasift/core/operators/vectordb/vectordb_operator.py) with OpenSearch adapter requires a running OpenSearch instance. The quickest way to get one locally is via the provided Compose file.

#### Step 1 — Start OpenSearch

**Docker:**

```bash
docker-compose -f docker/docker-compose.opensearch.yml up -d
```

**Podman:**

```bash
podman-compose -f docker/docker-compose.opensearch.yml up -d
```

This starts:

- OpenSearch API on `http://localhost:9200` (default credentials: `admin` / `MyStrongPass123!`)
- OpenSearch Dashboards on `http://localhost:5601`

#### Step 2 — Verify it's running

```bash
curl -u admin:MyStrongPass123! http://localhost:9200/_cluster/health?pretty
```

#### Step 3 — Configure environment variables

Copy the example env file and set your connection details:

```bash
cp .env.example .env
```

Key variables:
| Variable | Default | Description |
|---|---|---|
| `OPENSEARCH_HOST` | `localhost` | OpenSearch host |
| `OPENSEARCH_PORT` | `9200` | OpenSearch port |
| `OPENSEARCH_USERNAME` | — | Username |
| `OPENSEARCH_PASSWORD` | — | Password |
| `OPENSEARCH_INDEX_NAME` | `datasift_test` | Index to write to |
| `OPENSEARCH_USE_SSL` | `false` | Enable SSL |

#### Step 4 — Stop OpenSearch

```bash
# Docker
docker-compose -f docker/docker-compose.opensearch.yml down

# Podman
podman-compose -f docker/docker-compose.opensearch.yml down
```

**See also:**

- [Complete Pipeline Setup Guide](USER_GUIDE_PIPELINE_SETUP.md#opensearch-setup) - Detailed OpenSearch configuration
- [OpenSearch Documentation](docs/opensearch/) - Complete setup and usage guide
- [OpenSearch Operator Reference](docs/operators/opensearch.md) - Technical API documentation
- [VectorDBOperator Documentation](src/datasift/core/operators/vectordb/vectordb_operator.py) - Operator reference
- [Operator Reference](OPERATOR_REFERENCE.md) - VectorDBOperator parameters
- [Troubleshooting Guide](TROUBLESHOOTING.md) - OpenSearch connection issues

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
