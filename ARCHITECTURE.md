---
title: Datasift Architecture
---

# Datasift Architecture

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Core Concepts](#core-concepts)
4. [Component Deep Dive](#component-deep-dive)
5. [Distributed Execution Architecture](#distributed-execution-architecture)
6. [Operator Lifecycle](#operator-lifecycle)
7. [Data Flow Architecture](#data-flow-architecture)
8. [Integration Patterns](#integration-patterns)
9. [Design Decisions](#design-decisions)
10. [Repository Structure](#repository-structure)
11. [Development Guidelines](#development-guidelines)

---

This document describes the architecture and organization of the datasiftrepository.

## Overview

Datasift-open is a modular, operator-based data processing framework designed for building flexible document curation pipelines. It enables advanced RAG (Retrieval-Augmented Generation) workflows by combining structured data extraction, semantic chunking, vector embeddings, and hybrid search capabilities. It uses a mixed architecture approach comprising of dynamic plugin discovery across operators, hexagonal architecture in subsystems that need interchangeable external services.

### Key Capabilities

- **Operator-Based Architecture**: 20+ specialized operators organized into 5 categories (Extract, Ingest, Functional, Quality, VectorDB)
- **PyArrow Data Format**: All data flows through the pipeline as PyArrow tables, ensuring efficient memory usage and interoperability
- **DAG-Based Workflow Execution**: Flows are defined as JSON configurations representing directed acyclic graphs (DAGs) of operator nodes
- **Prefect Orchestration**: Workflow execution managed by Prefect with support for both ephemeral (local) and distributed execution via work pools (Docker, Kubernetes / OpenShift)
- **Modern AI/ML Integrations**: Native support for Ollama (LLM operations), Docling (document processing), OpenSearch (vector and scalar storage) and Milvus (vector storage)

### Architectural Patterns

Datasift-opensource intentionally employs a **mixed architectural approach** rather than adhering to a single dominant pattern. This diversity enables flexibility, modularity, and maintainability across different system layers:

- **Hexagonal Architecture (Ports & Adapters)**: Core domain logic and operator abstractions are isolated from external dependencies, allowing operators to be framework-agnostic and easily testable. The Prefect orchestration module specifically uses hexagonal architecture with ports and adapters for batch execution strategies, enabling seamless switching between local and distributed execution modes. Quality operators such as the PII/HAP stack use runtime-native ports-and-adapters packages under [`src/datasift/core/operators/quality`](src/datasift/core/operators/quality).
- **Factory Pattern**: `OrchestratorFactory` and `OperatorFactory` provide centralized instantiation logic for orchestrators and operators
- **Strategy Pattern**: Different operator implementations can be swapped based on configuration without changing the orchestration logic
- **Observer Pattern**: Event handling system (`AbstractFlowExecutionEventHandler`, `FlowExecutionEventHandler`) enables monitoring and logging of flow execution
- **Template Method Pattern**: `AbstractOperator` defines the execution flow template while concrete operators implement specific behavior

This architectural diversity is a deliberate design choice that supports the framework's goal of being extensible, testable, and adaptable to various data processing scenarios.

### Use Cases

- Extract text and structured information from tables within unstructured documents (PDFs, DOCX, etc.)
- Combine vector similarity search with structured data filtering for improved retrieval accuracy
- Build custom document processing pipelines with configurable operators

### Technology Stack

| Layer                   | Technologies                                                                                                                                          |
| ----------------------- |-------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Orchestration**       | Prefect, Python 3.12+                                                                                                                                 |
| **Data Processing**     | PyArrow                                                                                                                                               |
| **Storage**             | DuckDB (metadata and tables), Filesystem (metadata only)                                                                                              |
| **Document Processing** | Docling (with ASR support for audio/video via ffmpeg)                                                                                                 |
| **LLM Integration**     | Ollama, Watsonx.ai, LiteLLM (unified interface supporting 100+ LLM providers including OpenAI, Anthropic, Google, AWS Bedrock, and more), HuggingFace |
| **Vector Storage**      | OpenSearch, Milvus, NMSLIB, Faiss                                                                                                                     |
| **Language Detection**  | FastText, langdetect                                                                                                                                  |
| **Web Framework**       | FastAPI (optional)                                                                                                                                    |
| **Testing**             | pytest, pytest-cov                                                                                                                                    |
| **Package Management**  | uv                                                                                                                                                    |

---

## System Architecture

### High-Level Architecture Diagram

```mermaid
graph TB
    subgraph "Interface Layer"
        CLI[CLI Application]
        API[Python API]
    end

    subgraph "Orchestration Layer"
        FE[FlowExecutor]
        FV[FlowValidator]
        ORCH[PythonOrchestrator]
        PE[PrefectEngine]
        BM[BatchManager]
    end

    subgraph "Operator Layer"
        subgraph "Extract"
            EXT[ExtractOperator]
        end
        subgraph "Ingest"
            ILO[IngestLocalOperator]
            ISO[IngestSourceOperator]
        end
        subgraph "Functional"
            BR[BranchingOperator]
            MRG[MergeOperator]
            CH[Chunker]
            EC[EntityCurationOperator]
            EMB[EmbeddingsOperator]
            NOOP[NoopOperator]
        end
        subgraph "Quality"
            DC[DocumentClassifier]
            DD[Dedup]
            DQ[DocQuality]
            MLE[MLEnrichment]
            RB[Readability]
            RD[Redaction]
            SF[SQLFilter]
            LD[LanguageDetection]
        end
        subgraph "VectorDB"
            VDB[VectorDBOperator]
        end
    end

    subgraph "Integration Layer"
        OLL[Ollama Client]
        DOC[Docling Client]
        OS[OpenSearch Adapter]
        LLM[LiteLLM Client]
    end

    subgraph "Data Layer"
        PA[PyArrow Tables]
        FS[File System]
        OBJ[Object Storage]
        VEC[Vector Store]
    end

    CLI --> FE
    API --> FE
    FE --> FV
    FE --> ORCH
    ORCH --> PE
    ORCH --> BM
    PE --> Extract
    PE --> Ingest
    PE --> Functional
    PE --> Quality
    PE --> VectorDB

    EXT --> DOC
    EXT --> OLL
    EXT --> LLM
    EMB --> OLL
    VDB --> OS

    Ingest --> PA
    Extract --> PA
    Functional --> PA
    Quality --> PA
    VectorDB --> PA

    PA --> FS
    PA --> OBJ
    OS --> VEC

    style CLI fill:#e1f5ff
    style API fill:#e1f5ff
    style ORCH fill:#fff4e1
    style PE fill:#fff4e1
    style PA fill:#e8f5e9
    style VEC fill:#e8f5e9
```

### Architecture Layers

**1. Interface Layer**

- CLI application for command-line flow execution
- Python API for programmatic access

**2. Orchestration Layer**

- FlowExecutor: Entry point for flow execution
- FlowValidator: Validates flow definitions
- PythonOrchestrator: Coordinates operator execution
- PrefectEngine: Manages workflow execution with Prefect
- BatchManager: Handles batch processing

**3. Operator Layer**

- 20+ specialized operators organized by category
- Each operator processes PyArrow tables
- Chainable in DAG workflows

**4. Integration Layer**

- Client abstractions for external services
- Ollama for LLM operations
- Docling for document processing
- OpenSearch for vector storage

**5. Data Layer**

- PyArrow tables for efficient data flow
- File system and object storage
- Vector database for embeddings

---

## Job Management and Execution Tracking

datasift-opensource includes a dedicated job management subsystem under [`core/job_management`](src/datasift/core/job_management) that separates orchestration concerns, persistent job statistics, and read-side aggregation.

### Hexagonal Architecture for Job Stats

The job stats implementation follows a ports-and-adapters design:

- **Domain ports**
  - [`JobStatsService`](src/datasift/core/job_management/domain/ports/job_stats_service.py) defines the orchestration-facing contract for starting jobs, updating node execution state, listing runs, and cancellation/deletion workflows.
  - [`JobStatsStore`](src/datasift/core/job_management/domain/ports/job_stats_store.py) defines persistence operations for job-level and node-level statistics.
- **Application services**
  - [`NodeStatsAggregator`](src/datasift/core/job_management/application/services/node_stats_aggregator.py) performs read-side aggregation of raw node stats records.
  - [`JobManagementService`](src/datasift/core/job_management/application/services/job_management_service.py) coordinates APIs, job execution, and framework integration.
- **Adapters**
  - [`JobTrackerService`](src/datasift/core/job_management/adapters/services/job_tracker_service.py) is the production implementation of [`JobStatsService`](src/datasift/core/job_management/domain/ports/job_stats_service.py).
  - Storage adapters include JSON, in-memory, DuckDB, and PostgreSQL implementations created by [`JobManagementFactory`](src/datasift/core/job_management/adapters/config/job_management_factory.py).

This runtime path does **not** depend on legacy job tracking utilities. The active job stats path uses the new `core/job_management` module.

### Persistence and Aggregation Split

A key architectural rule is that persistence adapters only store and retrieve raw records.

- [`JobStatsStore`](src/datasift/core/job_management/domain/ports/job_stats_store.py) implementations must persist job stats and raw node stats.
- Store adapters must **not** perform node aggregation.
- [`NodeStatsAggregator`](src/datasift/core/job_management/application/services/node_stats_aggregator.py) is the only layer responsible for combining batch-level node stats into an aggregated node view.

This separation keeps write paths simple and makes aggregation behavior explicit, testable, and replaceable.

### Micro-Batching Model

For micro-batch execution, datasift stores node statistics at batch granularity.

- Every batch execution can produce a separate [`NodeStatsDto`](src/datasift/api/dto/node_stats_dto.py) record.
- Batch records are keyed by `job_run_id`, `node_id`, and `batch_id`.
- Read APIs can return:
  - an aggregated per-node view
  - detailed batch-level stats for the same node
- Non-batch operators still produce a single node stats record.

This design allows:

- accurate per-batch progress tracking
- bulk creation of pending node stats before execution
- failure/cancel/abort handling at node-batch granularity
- aggregation of document counts and metadata after execution

### Prefect Execution Semantics

The Prefect orchestration layer must keep the outer flow alive until submitted batch futures are resolved. This avoids a failure mode where the outer flow exits early, the task runner begins shutdown, and in-flight batch tasks are canceled or marked as crashed before the job-management layer can record final state consistently.

Relevant implementation points:

- [`PrefectEngine`](src/datasift/core/orchestration/prefect/prefect_engine.py) waits for submitted batch work before the outer flow completes.
- [`JobTrackerService`](src/datasift/core/job_management/adapters/services/job_tracker_service.py) updates terminal job state separately from node-state persistence.
- The job-management layer is responsible for persisting terminal states such as completed, failed, canceled, and aborted.

### Metadata Aggregation Contract

Operators often emit custom metadata that is later aggregated across batches. Aggregation behavior is defined centrally in [`strategies.py`](src/datasift/core/job_management/application/aggregation/strategies.py).

Maintainer rule:

- if a new operator adds metadata fields that need anything other than the default `LAST` behavior, update [`DEFAULT_STRATEGIES`](src/datasift/core/job_management/application/aggregation/strategies.py)
- add or update tests covering the new aggregation behavior
- document the field in [`docs/job_stats_management/NODE_METADATA_AGGREGATION_STRATEGY.md`](docs/job_stats_management/NODE_METADATA_AGGREGATION_STRATEGY.md)

See [`docs/job_stats_management/NODE_METADATA_AGGREGATION_STRATEGY.md`](docs/job_stats_management/NODE_METADATA_AGGREGATION_STRATEGY.md) for detailed aggregation rules and maintainer guidance.

## Core Concepts

### 1. Operator Pattern

Operators are the fundamental building blocks of datasift. Each operator is a self-contained unit that performs a specific data processing task.

**Key Characteristics:**

- Inherits from [`AbstractOperator`](src/datasift/core/operators/abstract_operator.py)
- Implements the Template Method pattern
- Receives PyArrow tables as input
- Returns PyArrow tables as output
- Configurable via JSON parameters
- Chainable in DAG workflows
- Exposes metadata via static methods (see [Operator Metadata Architecture](#2-operator-metadata-architecture))

**Operator Categories:**

````mermaid
graph LR
    OP[Operator Categories]
    OP --> ING[Ingest]
    OP --> EXT[Extract]
    OP --> FUN[Functional]
    OP --> QUA[Quality]
    OP --> VDB[VectorDB]

    ING --> I1[IngestLocalOperator]
    ING --> I2[IngestSourceOperator]

    EXT --> E1[ExtactOperator]

    FUN --> F1[BranchingOperator]
    FUN --> F2[MergeOperator]
    FUN --> F3[Chunker]
    FUN --> F4[EmbeddingsOperator]
    FUN --> F5[NoopOperator]

    QUA --> Q1[DocumentClassifier]
    QUA --> Q2[Dedup]
    QUA --> Q3[DocQuality]
    QUA --> Q4[MLEnrichment]
    QUA --> Q5[Readability]
    QUA --> Q6[Redaction]
    QUA --> Q7[SQLFilter]
    QUA --> Q8[LanguageDetection]

    VDB --> V1[VectorDBOperator]

    style OP fill:#f9f9f9
    style EXT fill:#ffe6e6
    style ING fill:#e6f3ff
    style FUN fill:#fff4e6
    style QUA fill:#e6ffe6
    style VDB fill:#f3e6ff

### Custom Operator Ownership and Priority

All operators must properly identify themselves using the `owner` attribute to ensure correct priority resolution in the operator factory.

**Owner Attribute:**
- **Datasift operators**: `owner = DatasiftConstants.OWNER_DATASIFT` (must be explicitly set for all built-in operators)
- **Custom operators**: `owner = "custom"` (must be explicitly set)
- **Default**: `owner = None` (inherited from [`AbstractOperator`](src/datasift/core/operators/abstract_operator.py:32), treated as custom)

**Priority Resolution:**

When multiple operators share the same `short_name`, the operator factory uses priority-based resolution:
- **Priority 1**: Custom operators (`owner="custom"` or `owner=None`)
- **Priority 2**: Datasift operators (`owner="datasift"`)

**Important:** Lower priority numbers carry higher precedence. Custom operators with `owner="custom"` will override datasift operators with the same `short_name`.

**Example - Built-in Datasift Operator:**

```python
from datasift.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from datasift.core.constants.constants import DatasiftConstants

class MyDatasiftOperator(AbstractOperator):
    short_name: str = "my_operator"
    category: OperatorCategory = OperatorCategory.Functional
    owner: str = DatasiftConstants.OWNER_DATASIFT  # REQUIRED for built-in operators

    def __init__(self, *, config: dict[str, Any]) -> None:
        super().__init__(config=config)
        # Implementation
````

**Example - Custom Operator:**

```python
from datasift.core.operators.abstract_operator import AbstractOperator, OperatorCategory

class MyCustomOperator(AbstractOperator):
    short_name: str = "my_operator"
    category: OperatorCategory = OperatorCategory.Functional  # Use appropriate standard category
    owner: str = "custom"  # REQUIRED for custom operators

    def __init__(self, *, config: dict[str, Any]) -> None:
        super().__init__(config=config)
        # Custom implementation
```

**Environment Variable Validation:**

The `DATASIFT_CUSTOM_OPERATORS` environment variable must be a comma-separated string of package paths. Non-string values will be logged as warnings and ignored to prevent operator factory failures.

```bash
# Valid
export DATASIFT_CUSTOM_OPERATORS="my_company.operators,another_package.ops"

# Invalid (non-string values are ignored with warning)
export DATASIFT_CUSTOM_OPERATORS=123  # Will be ignored
```

See [`OperatorFactory`](src/datasift/core/orchestration/operator_factory.py:35) for implementation details.

````

### 2. Operator Metadata Architecture

The [`OperatorMetadata`](src/datasift/core/operators/operator_metadata.py) class is the **primary API** for accessing metadata from all operators in the system. It provides a unified interface for discovering operators, querying their capabilities, and understanding their requirements.

**Primary API Pattern:**

```python
from core.operators.operator_metadata import OperatorMetadata

# Initialize metadata manager
metadata = OperatorMetadata()

# Get metadata for all operators
all_operators = metadata.get_operator_metadata()

# Access specific operator metadata
extract_metadata = all_operators['extract_operator']
print(extract_metadata['label'])           # "Extract Operator"
print(extract_metadata['category'])        # OperatorCategory.Extract
print(extract_metadata['features'])        # Dict of output features
print(extract_metadata['required_features'])  # List of required inputs

# Query features from specific operator
features = metadata.get_features(short_name='extract_operator')
required = metadata.required_feature_names(short_name='chunker')

# Get reverse mapping: which operators produce a feature?
feature_map = metadata.get_feature_operators_map()
print(feature_map['content'])  # ['Extract Operator', 'Chunker', ...]
````

**Key Capabilities:**

1. **Operator Discovery**: Automatically discovers all registered operators via [`OperatorFactoryProvider`](src/datasift/core/orchestration/operator_factory.py)
2. **Metadata Aggregation**: Collects metadata from all operators in a single call
3. **Feature Filtering**: Filters internal features (like `doc_id_hash`) from public API
4. **Caching**: Caches metadata after first retrieval for performance
5. **Utility Methods**: Provides convenience methods for common queries

**Usage in Datasift:**

The `OperatorMetadata` class is used throughout the system:

- **CLI**: [`list_operators`](src/datasift/utils/operators/display.py) command uses it to display available operators
- **Flow Validation**: [`FlowValidator`](src/datasift/core/orchestration/flow_validator.py) uses it to validate operator connections
- **Flow Manager**: [`DatasiftFlowManager`](src/datasift/lib/datasift_flow_manager.py) uses it for programmatic access
- **UI/API**: Future UI components will use it to build flow editors

**Common Use Cases:**

```python
# 1. List all available operators
metadata = OperatorMetadata()
all_ops = metadata.get_operator_metadata()
for short_name, meta in all_ops.items():
    print(f"{meta['label']}: {meta['description']}")

# 2. Check what features an operator produces
extract_features = metadata.get_features(short_name='extract_operator')
for feature_name, feature_def in extract_features.items():
    print(f"{feature_name}: {feature_def['type']}")

# 3. Validate operator compatibility
chunker_required = metadata.required_feature_names(short_name='chunker')
extract_features = metadata.get_features(short_name='extract_operator')
can_connect = all(req in extract_features for req in chunker_required)

# 4. Find operators that produce a specific feature
feature_map = metadata.get_feature_operators_map()
content_producers = feature_map.get('embeddings', [])
print(f"Operators producing 'embeddings': {content_producers}")
```

**Implementation Details:**

Internally, `OperatorMetadata` calls static methods on operator classes:

```python
# How OperatorMetadata works internally (simplified)
for short_name, operator_class in operator_factory.operators.items():
    # Call static methods on each operator class
    metadata_dict = operator_class.get_metadata()
    required_features = operator_class.get_required_features()

    # Aggregate into unified structure
    all_metadata[short_name] = {
        **metadata_dict,
        'required_features': required_features
    }
```

Each operator implements two static methods:

```python
class ExtractOperator(AbstractOperator):
    @staticmethod
    def get_metadata():
        return {
            "label": "Extract Operator",
            "category": OperatorCategory.Extract,
            "description": "Extracts text and entities from documents",
            "features": {
                "content": {
                    "type": "string",
                    "description": "Extracted document text",
                    "required": False,
                    "available_for_filter": True,
                    "available_for_vector_db": True
                }
            }
        }

    @staticmethod
    def get_required_features() -> list[str]:
        return ["doc_id", "file_path"]
```

**Note:** While operators expose `get_metadata()` and `get_required_features()` as static methods, **users should not call these directly**. Always use the `OperatorMetadata` class as the primary API, which handles discovery, aggregation, filtering, and caching.

**Metadata Structure:**

Each operator's metadata dictionary contains:

| Field               | Type             | Description                                                        |
| ------------------- | ---------------- | ------------------------------------------------------------------ |
| `label`             | string           | Human-readable operator name                                       |
| `category`          | OperatorCategory | Operator category (Extract, Ingest, Functional, Quality, VectorDB) |
| `description`       | string           | Operator purpose and functionality                                 |
| `features`          | dict             | Output features produced by the operator                           |
| `required_features` | list             | Input feature names required by the operator                       |

**Feature Metadata:**

Each feature in the `features` dictionary contains:

| Field                     | Type    | Description                                                 |
| ------------------------- | ------- | ----------------------------------------------------------- |
| `type`                    | string  | Data type (string, int64, double, boolean, list)            |
| `description`             | string  | Feature description                                         |
| `required`                | boolean | Whether feature is always produced                          |
| `available_for_filter`    | boolean | Can be used in SQL WHERE clauses                            |
| `available_for_vector_db` | boolean | Can be stored in vector databases                           |
| `tags`                    | list    | Optional tags (e.g., "internal" for internal-only features) |

**Design Rationale:**

1. **Unified API**: Single entry point (`OperatorMetadata`) for all metadata queries
2. **Automatic Discovery**: Discovers all operators without manual registration
3. **Performance**: Caches metadata after first retrieval; no repeated instantiation
4. **Separation of Concerns**:
   - Metadata API (what operators produce/need) vs operator implementation (how they process data)
   - Static information vs runtime configuration
5. **Filtering**: Automatically filters internal features from public API
6. **Extensibility**: New operators are automatically discovered when added to the system

**Metadata vs Configuration:**

| Aspect            | Operator Metadata                            | Configuration                        |
| ----------------- | -------------------------------------------- | ------------------------------------ |
| **Access**        | `OperatorMetadata().get_operator_metadata()` | `operator_instance.config`           |
| **Instantiation** | No operator instantiation required           | Full operator instantiation required |
| **Represents**    | What operator _produces_ and _needs_         | What instance _will do_              |
| **Scope**         | Class-level capabilities and requirements    | Instance-specific parameters         |
| **Mutability**    | Immutable (cached)                           | Mutable per instance                 |
| **Examples**      | Output features, required inputs, category   | Batch size, model name, file paths   |
| **Use Cases**     | Flow validation, UI generation, discovery    | Runtime execution, data processing   |

### 3. Flow/Pipeline Concept

A **Flow** is a JSON-defined configuration that specifies a pipeline of operators connected in a directed acyclic graph (DAG).

**Flow Authoring Format vs Runtime DAG:**

DataSift uses two distinct representations:

1. **Authoring Format** (User-facing): Simplified JSON structure for defining flows
   - Uses `flow` array with operator definitions
   - Uses `depends_on` to declare dependencies by operator name
   - Uses `type` with short operator names (e.g., `ingest_local`, `extract_operator`)
   - Uses `config` for operator-specific parameters

2. **Runtime DAG** (Internal): Compiled execution graph with nodes and edges
   - Generated automatically from authoring format
   - Contains UUIDs, edge connections, and execution metadata
   - Used by the orchestration engine for execution

**Example Flow Authoring Format:**

```json
{
  "flow_name": "Document Processing Pipeline",
  "description": "Ingest, extract, chunk, and embed documents",
  "flow": [
    {
      "name": "ingest_local_folder",
      "type": "ingest_local",
      "config": {
        "paths": "./sample_documents"
      }
    },
    {
      "name": "extract_with_docling",
      "type": "extract_operator",
      "depends_on": ["ingest_local_folder"],
      "config": {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "none"
      }
    }
  ],
  "global_config": {
    "doc_column": "content"
  }
}
```

**Key Authoring Format Elements:**

- **flow_name**: Human-readable flow identifier
- **flow**: Array of operator definitions with unique names
- **depends_on**: Array of operator names that must execute before this operator
- **type**: Short operator name (e.g., `ingest_local`, `chunker`, `embeddings`, `vectordb`)
- **config**: Operator-specific configuration parameters
- **Automatic Compilation**: The system automatically generates the runtime DAG from the authoring format

### 4. DAG-Based Execution Model

The execution model follows these principles:

1. **Topological Ordering**: Operators execute in dependency order
2. **Parallel Execution**: Independent operators run concurrently
3. **Data Passing**: PyArrow tables flow between operators
4. **Error Handling**: Failed operators propagate errors appropriately
5. **Batch Processing**: Large datasets processed in configurable batches

```mermaid
graph LR
    A[Ingest] --> B[DocumentClassifier]
    B --> C[Extract]
    C --> D[Chunk]
    D --> E[Embed]
    E --> F[VectorDB]

    style A fill:#e1f5ff
    style B fill:#e6ffe6
    style C fill:#ffe1f5
    style D fill:#f5ffe1
    style E fill:#fff5e1
    style F fill:#e1fff5
```

### 5. PyArrow Data Format Rationale

PyArrow tables serve as the universal data format throughout the pipeline:

**Benefits:**

- **Columnar Storage**: Efficient memory usage and fast column-wise operations
- **Zero-Copy Reads**: Minimal memory overhead when passing data between operators
- **Type Safety**: Strong schema enforcement with rich type system
- **Interoperability**: Native support for Parquet, CSV, and other formats
- **Performance**: Optimized for analytical workloads and batch processing

**Schema Preservation:**

- Column schemas maintained across all operators
- Automatic type inference and validation
- Support for nested structures and complex types

## Component Deep Dive

### 1. Orchestrator Architecture

The orchestrator coordinates flow execution using Prefect for workflow management.

```mermaid
graph TB
    subgraph "Orchestrator Components"
        AO[AbstractOrchestrator]
        PO[PythonOrchestrator]
        FE[FlowExecutor]
        FV[FlowValidator]
        PE[PrefectEngine]
        BM[BatchManager]
        EH[EventHandler]
        JT[JobTracker]
    end

    subgraph "Execution Flow"
        START[Start] --> LOAD[Load Flow JSON]
        LOAD --> VALIDATE[Validate Flow]
        VALIDATE --> INIT[Initialize Orchestrator]
        INIT --> EXEC[Execute DAG]
        EXEC --> MONITOR[Monitor Progress]
        MONITOR --> COMPLETE[Complete]
    end

    FE --> FV
    FE --> PO
    PO --> PE
    PO --> BM
    PO --> EH
    PO --> JT

    LOAD --> FE
    VALIDATE --> FV
    INIT --> PO
    EXEC --> PE
    MONITOR --> EH

    style AO fill:#fff4e1
    style PO fill:#fff4e1
    style PE fill:#ffe1e1
    style START fill:#e1f5ff
    style COMPLETE fill:#e1ffe1
```

**Key Components:**

#### AbstractOrchestrator

- Base interface for all orchestrators
- Manages job lifecycle (initialization, execution, cleanup)
- Coordinates with Prefect engine
- Handles batch processing

#### Work Pool Configuration

The `WorkPoolConfig` model defines configuration for distributed execution modes:

```python
@dataclass
class WorkPoolConfig:
    enabled: bool = False
    type: str = "process"  # "process", "docker", "kubernetes"
    name: str = "default-pool"
    max_workers: Optional[int] = None
    image: Optional[str] = None
    namespace: Optional[str] = None
    batch_storage: Optional[BatchStorageConfig] = None
```

**Configuration Parameters:**

| Parameter       | Type   | Description                                       | Required   |
| --------------- | ------ | ------------------------------------------------- | ---------- |
| `enabled`       | bool   | Enable work pool execution                        | Yes        |
| `type`          | str    | Execution type: "process", "docker", "kubernetes" | Yes        |
| `name`          | str    | Work pool name in Prefect                         | Yes        |
| `max_workers`   | int    | Maximum concurrent workers (process pool only)    | No         |
| `image`         | str    | Docker/Kubernetes / OpenShift image name          | Docker/K8s |
| `namespace`     | str    | Kubernetes / OpenShift namespace                  | K8s only   |
| `batch_storage` | object | Batch storage configuration                       | Docker/K8s |

**Batch Storage Configuration:**

```python
@dataclass
class BatchStorageConfig:
    type: str = "local"  # Only "local" supported
    base_path: str = "/tmp/datasift/batches"
```

**Configuration Examples:**

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
    "image": "datasift:latest",
    "batch_storage": {
      "type": "local",
      "base_path": "/app/data/batches"
    }
  }
}
```

**Kubernetes / OpenShift:**

```json
{
  "work_pool": {
    "enabled": true,
    "type": "kubernetes",
    "name": "datasift-k8s-pool",
    "namespace": "datasift-production",
    "image": "myregistry.io/datasift:v1.0.0",
    "batch_storage": {
      "type": "local",
      "base_path": "/shared/batches"
    }
  }
}
```

**Work Pool Setup:**

Before using distributed execution, create the corresponding Prefect work pool:

```bash
# Process pool (managed automatically)
# No setup required

# Docker pool
prefect work-pool create datasift-docker-pool --type docker

# Kubernetes / OpenShift pool
prefect work-pool create datasift-k8s-pool --type kubernetes
```

**Worker Deployment:**

Start workers to process tasks from the work pool:

```bash
# Docker worker
prefect worker start --pool datasift-docker-pool

# Kubernetes / OpenShift worker (deployed as K8s Deployment)
kubectl apply -f k8s-deployment-examples/prefect-worker.yaml
```

- Tracks deleted rows and metadata

#### PythonOrchestrator

- Concrete implementation of [`AbstractOrchestrator`](src/datasift/core/orchestration/abstract_orchestrator.py)
- Used by both CLI and Python API
- Instantiated via [`OrchestratorFactory`](src/datasift/core/orchestration/orchestrator_factory.py)
- Manages operator execution through Prefect

#### FlowExecutor

- Entry point for flow execution
- Loads flow definitions from JSON files or dictionaries
- Validates flows before execution
- Manages memory diagnostics
- Handles cancellation requests

#### FlowValidator

- Validates operator configurations and parameters
- Checks data dependencies and DAG structure
- Verifies operator availability and compatibility
- Produces actionable errors and warnings

#### PrefectEngine

- Wraps Prefect workflow execution
- Manages task dependencies
- Handles parallel execution
- Provides retry logic
- Tracks execution state

#### BatchManager

- Coordinates batch processing
- Manages batch size configuration
- Handles batch splitting and merging
- Optimizes memory usage

### 2. Operator Base Classes

```mermaid
classDiagram
    class AbstractTableTransform {
        <<abstract>>
        +transform(table: Table) tuple[list[Table], dict]
    }

    class AbstractOperator {
        <<abstract>>
        +short_name: str
        +category: OperatorCategory
        +transform(table: Table) tuple[list[Table], dict]
        +validate(errors, warnings, features)
        +get_required_features()$ list
        +get_metadata()$ dict
        +is_available()$ bool
    }

    class ConcreteOperator {
        +transform(table: Table) tuple[list[Table], dict]
        +validate(errors, warnings, features)
        +get_required_features()$ list
    }

    AbstractTableTransform <|-- AbstractOperator
    AbstractOperator <|-- ConcreteOperator

    note for AbstractOperator "Template Method Pattern:\n- Defines execution flow\n- Subclasses implement specifics"
```

**AbstractOperator Responsibilities:**

1. **Configuration Management**: Parse and store operator parameters
2. **Validation**: Validate input data and configuration
3. **Execution**: Process PyArrow tables
4. **Metadata**: Track processing statistics
5. **Error Handling**: Record failed and skipped documents
6. **Feature Management**: Declare required input columns

**Class-Level vs Instance-Level Methods:**

Operators distinguish between class-level capabilities and instance-level configuration:

- **Static Methods** (`@staticmethod`):
  - [`get_metadata()`](src/datasift/core/operators/abstract_operator.py:61): Returns operator-level metadata (category, features, description)
  - [`get_required_features()`](src/datasift/core/operators/abstract_operator.py:56): Returns required input features
  - [`is_available()`](src/datasift/core/operators/abstract_operator.py:47): Checks if operator dependencies are available
  - Accessed via `OperatorClass.method_name()` without instantiation
  - Represent operator capabilities independent of any specific configuration

- **Instance Methods**:
  - `validate()`: Validates instance-specific parameters and configuration
  - `transform()`: Processes data using instance configuration
  - Require operator instantiation with specific configuration

**Rationale for Static Methods:**

Both [`get_metadata()`](src/datasift/core/operators/abstract_operator.py:61) and [`get_required_features()`](src/datasift/core/operators/abstract_operator.py:56) are static because:

1. They represent operator-level information, not instance-specific configuration
2. Enable metadata discovery without instantiation overhead
3. Information is constant across all instances of an operator class
4. Support efficient operator registry and discovery mechanisms
5. Align with the principle that metadata describes "what the operator can do" rather than "what this instance is configured to do"

### 3. Data Flow Between Operators

```mermaid
sequenceDiagram
    participant O1 as Operator 1
    participant DA as DataAccess
    participant FS as File System
    participant O2 as Operator 2

    O1->>O1: Process Data
    O1->>DA: Write PyArrow Table
    DA->>FS: Save Parquet File
    Note over DA,FS: Efficient columnar storage

    O2->>DA: Request Input Data
    DA->>FS: Read Parquet File
    FS->>DA: Return PyArrow Table
    DA->>O2: Provide Input Table
    O2->>O2: Process Data
```

**Key Features:**

1. **Schema Preservation**: Column schemas maintained across all operators
2. **Efficient Storage**: Columnar Parquet format for disk-based operations

**Processing Mechanisms:**

1. **In-Memory Passing**: Small datasets passed directly as PyArrow tables
2. **Disk-Based Storage**: Large datasets written to Parquet files for memory efficiency
3. **Batch Processing**: Large datasets split into configurable batches for parallel execution

### 4. Configuration Management

Configuration flows through multiple layers:

```mermaid
graph TD
    JSON[Flow JSON] --> FE[FlowExecutor]
    YAML[datasift-config.yaml] --> ORCH[Orchestrator]
    FE --> PARAMS[Runtime Parameters]
    PARAMS --> ORCH
    ORCH --> OP_CONFIG[Operator Config]
    OP_CONFIG --> OP[Operator Instance]

    ENV[Environment Variables] --> YAML
    DEFAULTS[Default Values] --> OP_CONFIG

    style JSON fill:#e1f5ff
    style YAML fill:#f3e5ff
    style PARAMS fill:#fff4e1
    style OP fill:#e1ffe1
```

**Configuration Hierarchy:**

1. Flow JSON for flow topology and operator parameters
2. `datasift-config.yaml` for centralized system configuration
3. Environment variables for deployment-specific overrides
4. Default values for unspecified settings

Flow JSON remains the source for DAG structure and operator-specific behavior, while shared runtime infrastructure such as job management, asset repositories, and incremental metadata is configured centrally through `datasift-config.yaml`.

#### Incremental Metadata Configuration

Incremental metadata configuration is YAML-first and uses `datasift-config.yaml` as the single source of truth. Flow-level `incremental_metadata` settings are no longer part of the supported configuration model.

The centralized configuration shape is:

```yaml
incremental_metadata:
  storage:
    type: "filesystem"  # Options: filesystem, postgresql
    config:
      base_dir: "./data"
      lock_timeout: 30.0
```

When `storage.type` is `postgresql`, the configuration also includes a dedicated `postgres` section for connection settings and schema selection.

Supported storage backends:

- **Filesystem** - file-backed storage using Parquet format for development and single-host execution
- **PostgreSQL** - centralized durable storage for concurrent and distributed execution

Environment variable substitution is supported inside `datasift-config.yaml`, allowing secrets such as database passwords to be supplied at deployment time rather than committed to source control.

#### Incremental Metadata Hexagonal Architecture

Incremental metadata is implemented as a hexagonal subsystem under [`src/datasift/core/incremental_metadata/`](src/datasift/core/incremental_metadata/):

- `domain/models/incremental_record.py` defines the domain record model
- `domain/ports/incremental_metadata_store.py` defines the storage port
- `adapters/config/` resolves backend configuration from `datasift-config.yaml`
- `adapters/stores/filesystem/` contains the Filesystem storage adapter (using Parquet format)
- `adapters/stores/postgres/` contains the PostgreSQL storage adapter

This structure separates domain contracts from infrastructure concerns and allows backend selection without changing ingest operator code. The orchestration layer resolves the configured incremental metadata store once and passes that capability to the ingest path that performs incremental change detection.

---

## Distributed Execution Architecture

Datasift-opensource supports multiple execution modes through a hexagonal architecture pattern that decouples the orchestration logic from the execution strategy. This enables seamless switching between local development and distributed production deployments.

### Execution Modes

The framework supports four execution modes:

1. **Thread Pool (Local Development)**: Uses Python's ThreadPoolExecutor for lightweight parallelism within a single process
2. **Process Pool (Single-Node Production)**: Uses Python's ProcessPoolExecutor for CPU-bound workloads on a single machine
3. **Docker (Distributed)**: Deploys batch processing tasks as Docker containers via Prefect work pools
4. **Kubernetes / OpenShift (Distributed)**: Orchestrates batch processing across Kubernetes / OpenShift pods for enterprise-scale deployments

### Hexagonal Architecture Pattern

The distributed execution system follows hexagonal architecture (ports and adapters) to maintain clean separation between business logic and infrastructure:

```mermaid
graph TB
    subgraph "Core Domain"
        PE[PrefectEngine]
        BM[BatchManager]
    end

    subgraph "Port Layer"
        BEP[BatchExecutionPort<br/>Interface]
    end

    subgraph "Adapter Layer"
        TPA[ThreadPoolAdapter]
        WPA[WorkPoolAdapter]
    end

    subgraph "Infrastructure"
        TP[ThreadPoolExecutor]
        PP[ProcessPoolExecutor]
        DW[Docker Work Pool]
        KW[Kubernetes / OpenShift Work Pool]
    end

    PE --> BEP
    BM --> BEP
    BEP --> TPA
    BEP --> WPA
    TPA --> TP
    WPA --> PP
    WPA --> DW
    WPA --> KW

    style PE fill:#fff4e1
    style BEP fill:#e1f5ff
    style TPA fill:#e1ffe1
    style WPA fill:#e1ffe1
```

**Key Components:**

#### BatchExecutionPort (Interface)

- Defines the contract for batch execution strategies
- Methods: `execute_batches()`, `shutdown()`
- Enables strategy pattern for execution modes

#### ThreadPoolAdapter

- Implements BatchExecutionPort for local execution
- Uses Python's ThreadPoolExecutor
- Best for I/O-bound operations and development
- No external infrastructure required

#### WorkPoolAdapter

- Implements BatchExecutionPort for distributed execution
- Supports process pool, Docker, and Kubernetes / OpenShift work pools
- Configurable via WorkPoolConfig
- Handles batch serialization and result aggregation

### Batch Storage Strategies

Distributed execution requires serializing batches for cross-process/container communication:

1. **Inline Storage**: Batches passed directly in memory (thread pool only)
2. **Local Filesystem**: Batches written to Parquet files on shared storage (process pool, Docker with volumes, Kubernetes / OpenShift with PVCs)

**Note:** S3 and other cloud storage backends are not currently supported.

### Execution Flow

```mermaid
sequenceDiagram
    participant FE as FlowExecutor
    participant PE as PrefectEngine
    participant BM as BatchManager
    participant Adapter as BatchExecutionAdapter
    participant Worker as Worker Process/Container

    FE->>PE: Execute Flow
    PE->>BM: Split into Batches
    BM->>Adapter: execute_batches()

    alt Thread Pool Mode
        Adapter->>Worker: Submit to ThreadPool
        Worker->>Worker: Process Batch (in-memory)
        Worker-->>Adapter: Return Results
    else Work Pool Mode
        Adapter->>Adapter: Serialize Batches to Disk
        Adapter->>Worker: Submit to Work Pool
        Worker->>Worker: Load Batch from Disk
        Worker->>Worker: Process Batch
        Worker->>Worker: Write Results to Disk
        Worker-->>Adapter: Signal Completion
        Adapter->>Adapter: Load Results from Disk
    end

    Adapter-->>BM: Aggregated Results
    BM-->>PE: Complete
    PE-->>FE: Flow Complete
```

### Configuration

Execution mode is configured via the `work_pool` section in flow JSON:

**Thread Pool (Default):**

```json
{
  "work_pool": {
    "enabled": false
  }
}
```

**Process Pool:**

```json
{
  "work_pool": {
    "enabled": true,
    "type": "process",
    "name": "my-process-pool",
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
    "name": "my-docker-pool",
    "image": "datasift:latest",
    "batch_storage": {
      "type": "local",
      "base_path": "/shared/batches"
    }
  }
}
```

**Kubernetes / OpenShift:**

```json
{
  "work_pool": {
    "enabled": true,
    "type": "kubernetes",
    "name": "my-k8s-pool",
    "namespace": "datasift",
    "image": "datasift:latest",
    "batch_storage": {
      "type": "local",
      "base_path": "/shared/batches"
    }
  }
}
```

---

## Operator Lifecycle

### Complete Lifecycle Diagram

```mermaid
stateDiagram-v2
    [*] --> Instantiation
    Instantiation --> Configuration
    Configuration --> Validation
    Validation --> Initialization
    Initialization --> Execution
    Execution --> DataProcessing
    DataProcessing --> MetadataCollection
    MetadataCollection --> OutputGeneration
    OutputGeneration --> Cleanup
    Cleanup --> [*]

    Validation --> Error: Validation Failed
    Execution --> Error: Execution Failed
    DataProcessing --> Error: Processing Failed
    Error --> Cleanup

    note right of Instantiation
        OperatorFactory creates
        operator instance from
        flow configuration
    end note

    note right of Validation
        Validate parameters,
        check dependencies,
        verify data schema
    end note

    note right of Execution
        Process PyArrow table,
        apply transformations,
        handle errors
    end note
```

### Detailed Lifecycle Stages

#### 1. Instantiation

**Process:**

```python
# OperatorFactory creates operator from config
operator_class = import_operator_class(operator_type)

# Access class-level metadata without instantiation
metadata = operator_class.get_metadata()
is_available = operator_class.is_available()

# Create instance with configuration
operator_instance = operator_class(config)
```

**Configuration Injection:**

- Operator type (fully qualified class name)
- Operator parameters (from flow JSON)
- Job metadata (job_id, job_run_id, context_id)
- Runtime parameters

**Metadata Access Pattern:**

- Operator metadata is accessed at the class level via static method [`OperatorClass.get_metadata()`](src/datasift/core/operators/abstract_operator.py:59)
- No instantiation required for metadata discovery
- Enables efficient operator registry and capability queries

#### 2. Configuration

**Operator receives:**

```python
config = {
    "name": "extract_1",
    "id": "extract_1",
    "job_id": "job_123",
    "job_run_id": "run_456",
    "config": {
        "docling_url": "http://localhost:5000",
        "batch_size": 10
    }
}
```

**Parsed into operator attributes:**

- `self.name`: Operator name
- `self.id`: Unique operator ID
- `self.job_id`: Job identifier
- `self.job_run_id`: Job run identifier
- Custom parameters from `config`

#### 3. Validation

**Two-Phase Validation:**

**Phase 1: Flow Validation (Pre-Execution)**

```python
def validate(self, errors: list, warnings: list, available_features: list):
    # Check required features exist
    OperatorUtils.validate_columns(
        available_features,
        self.get_required_features(),
        self.short_name,
        errors
    )
    # Validate operator-specific parameters
    self._validate_params(errors, warnings)
```

**Phase 2: Runtime Validation (During Execution)**

- Input data schema validation
- Parameter value validation
- External service availability checks

#### 4. Execution

**Main execution flow:**

```mermaid
graph TD
    START[Receive Input Table] --> CHECK{Validate Input}
    CHECK -->|Valid| PROCESS[Process Data]
    CHECK -->|Invalid| ERROR[Record Error]

    PROCESS --> BATCH{Batch Processing?}
    BATCH -->|Yes| SPLIT[Split into Batches]
    BATCH -->|No| TRANSFORM[Transform Data]

    SPLIT --> LOOP[Process Each Batch]
    LOOP --> TRANSFORM
    TRANSFORM --> MERGE[Merge Results]
    MERGE --> OUTPUT[Generate Output Table]

    ERROR --> METADATA[Update Metadata]
    OUTPUT --> METADATA
    METADATA --> RETURN[Return Results]

    style START fill:#e1f5ff
    style PROCESS fill:#fff4e1
    style OUTPUT fill:#e1ffe1
    style ERROR fill:#ffe1e1
```

#### 5. Metadata Collection

**Two Types of Metadata:**

**1. Operator Metadata (Class-Level, Static):**

```python
# Accessed without instantiation
operator_metadata = ExtractOperator.get_metadata()
# Returns:
# {
#     "label": "Extract Operator",
#     "category": "Extract",
#     "description": "Extracts text and entities from documents",
#     "features": {
#         "content": {"type": "string", "description": "Extracted text"},
#         "entities": {"type": "list", "description": "Extracted entities"}
#     }
# }
```

**2. Execution Metadata (Instance-Level, Runtime):**

```python
# Generated during operator execution
execution_metadata = {
    "total_docs": 100,
    "processed_docs": 95,
    "failed_docs_count": 3,
    "failed_docs": [
        {"id": "doc_1", "name": "file1.pdf", "reason": "Parse error"}
    ],
    "skipped_docs_count": 2,
    "skipped_docs": [
        {"id": "doc_3", "name": "file3.pdf", "reason": "Empty content"}
    ],
    "node_status": "COMPLETED"
}
```

**Key Distinction:**

- **Operator metadata**: Describes what the operator _can do_ (capabilities, features, requirements)
- **Execution metadata**: Describes what the operator _did_ (processing results, statistics, errors)

---

## Data Flow Architecture

### End-to-End Data Flow

The platform supports multiple input sources and optional quality operators, but the core document-processing path is a linear sequence from ingestion through vector storage:

```mermaid
graph LR
    SRC[Input Source]
    ING[IngestLocalOperator / IngestSourceOperator]
    EXT[ExtractOperator]
    CHK[Chunker]
    EMB[EmbeddingsOperator]
    VDB[VectorDBOperator]

    SRC --> ING --> EXT --> CHK --> EMB --> VDB

    style SRC fill:#e1f5ff
    style ING fill:#e1f5ff
    style EXT fill:#ffe1e1
    style CHK fill:#fff4e1
    style EMB fill:#fff5e1
    style VDB fill:#f3e6ff
```

## Integration Patterns

### 1. Ollama Integration Architecture

```mermaid
graph TB
    subgraph "Datasift Operators"
        EXT[ExtractOperator]
        EMB[EmbeddingsOperator]
    end

    subgraph "Client Layer"
        OC[OllamaClient]
        OEA[OllamaEmbeddingsAdapter]
    end

    subgraph "Ollama Service"
        OS[Ollama Server<br/>localhost:11434]
        M1[llama3.2]
        M2[nomic-embed-text]
        M3[mistral]
    end

    EE --> OC
    EMB --> OEA
    OC --> OS
    OEA --> OS
    OS --> M1
    OS --> M2
    OS --> M3

    style EE fill:#ffe1e1
    style EMB fill:#ffe1e1
    style OC fill:#fff4e1
    style OS fill:#e1f5ff
```

**Integration Points:**

1. **Entity Extraction**: Uses Ollama for LLM-based entity extraction
2. **Embeddings**: Generates vector embeddings using Ollama models
3. **Configuration**: Model selection, temperature, context window
4. **Error Handling**: Retry logic, timeout management

**Example Configuration:**

```json
{
  "operator": "extract_entities_ollama",
  "config": {
    "ollama_url": "http://localhost:11434",
    "model_name": "llama3.2",
    "temperature": 0.7,
    "max_tokens": 2000
  }
}
```

### 2. Watsonx.ai Integration Architecture

```mermaid
graph TB
    subgraph "Datasift Operators"
        EXT[ExtractOperator]
        DC[DocumentClassifier]
    end

    subgraph "Client Layer"
        WC[WatsonxClient]
        WEA[WatsonxEntityAdapter]
        WCA[Watsonx Classification Adapter]
    end

    subgraph "IBM watsonx.ai"
        IAM[IBM Cloud IAM]
        API[watsonx.ai API]
        M1[ibm/granite-13b-chat-v2]
        M2[ibm/granite-3-8b-instruct]
        M3[Other hosted models]
    end

    EXT --> WEA
    DC --> WCA
    WEA --> WC
    WCA --> WC
    WC --> IAM
    WC --> API
    API --> M1
    API --> M2
    API --> M3

    style EXT fill:#ffe1e1
    style DC fill:#e6ffe6
    style WC fill:#fff4e1
    style API fill:#e1f5ff
    style IAM fill:#e1f5ff
```

**Integration Points:**

1. **Entity Extraction**: Uses Watsonx.ai for LLM-based entity extraction in `ExtractOperator`
2. **Document Classification**: Uses Watsonx.ai for category classification in `DocumentClassifier`
3. **Authentication**: IBM Cloud IAM token flow using `WATSONX_API_KEY`
4. **Configuration**: `provider_config` carries non-sensitive settings such as `api_base`, `container_kind`, and `request_timeout`
5. **Container Targeting**: Requests are scoped to a project or deployment space via `WATSONX_CONTAINER_ID`
6. **Error Handling**: Client-managed retries, timeout control, and provider error normalization

**Required Environment Variables:**

- `WATSONX_API_KEY`: IBM Cloud API key used to obtain IAM access tokens
- `WATSONX_CONTAINER_ID`: Watsonx.ai project ID or space ID
- `WATSONX_API_BASE_URL`: Optional API base URL such as `https://us-south.ml.cloud.ibm.com`
- `WATSONX_CONTAINER_KIND`: Optional container type, defaults to `project`

**Supported Models:**

- **IBM Granite**: Hosted Granite chat and instruct models such as `ibm/granite-13b-chat-v2`
- **Other watsonx.ai models**: Any compatible model exposed through the configured watsonx.ai deployment

**Example Configuration:**

```json
{
  "operator_type": "ExtractOperator",
  "operator_params": {
    "entity_extraction_mode": "watsonx",
    "model_name": "ibm/granite-13b-chat-v2",
    "provider_config": {
      "api_base": "https://us-south.ml.cloud.ibm.com",
      "container_kind": "project",
      "request_timeout": 60
    },
    "custom_schema": {
      "invoice_number": "string",
      "total_amount": "float"
    }
  }
}
```

**Note:** When using entity extraction (any mode except `none`), you must provide either:
- A `custom_schema` in the operator configuration (as shown above), OR
- A `document_type` column from an upstream classification operator (e.g., DocumentClassifierOperator)

If neither is provided, a `ConfigurationError` will be thrown.

### 3. OpenSearch Integration Architecture

```mermaid
graph TB
    subgraph "Datasift Layer"
        VDB[VectorDBOperator]
    end

    subgraph "Adapter Layer (Hexagonal)"
        PORT[VectorDB Port<br/>Interface]
        OSA[OpenSearch Adapter]
    end

    subgraph "OpenSearch Service"
        OS[OpenSearch<br/>localhost:9200]
        IDX[Indices]
        KNN1[NMSLIB Engine]
        KNN2[Faiss Engine]
        KNN3[Lucene Engine]
    end

    VDB --> PORT
    PORT --> OSA
    OSA --> OS
    OS --> IDX
    IDX --> KNN1
    IDX --> KNN2
    IDX --> KNN3

    style VDB fill:#ffe1e1
    style PORT fill:#fff4e1
    style OSA fill:#e1ffe1
    style OS fill:#e1f5ff
```

**Hexagonal Architecture Benefits:**

1. **Decoupling**: VectorDBOperator independent of OpenSearch specifics
2. **Testability**: Easy to mock adapters for testing
3. **Extensibility**: Add new vector DB adapters without changing operator
4. **Flexibility**: Switch vector databases via configuration

**Supported KNN Engines:**

- **NMSLIB**: Fast approximate nearest neighbor search
- **Faiss**: Facebook's similarity search library
- **Lucene**: Native Lucene KNN implementation

**Example Configuration:**

```json
{
  "operator": "vectordb",
  "config": {
    "provider": "opensearch",
    "index_name": "documents",
    "provider_config": {
      "host": "localhost",
      "port": 9200,
      "engine": "nmslib",
      "space_type": "cosinesimil"
    }
  }
}
```

**Note:** Vector dimensions are auto-detected from embedding data. OpenSearch supports multiple vector columns with different dimensions in a single index.

### 4. OpenSearch Schema Templates and Metadata Normalization

The OpenSearch adapter supports a flexible schema template system that enables reusable index configurations with placeholder-based dynamic values, along with automatic metadata column normalization.

#### Schema Template System

**Purpose**: Provide consistent, reusable OpenSearch index schemas across different pipelines while maintaining backward compatibility with dynamic schema generation.

**Key Features**:

1. **JSON-Based Templates**: Schema templates are stored as JSON files in `src/datasift/core/operators/vectordb/schemas/`
2. **Placeholder Replacement**: Dynamic values are injected at runtime using placeholder strings
3. **Graceful Fallback**: If template is not found or invalid, falls back to dynamic schema generation
4. **Validation**: Comprehensive schema validation with detailed error messages
5. **Indexing Rules**: Field-level overrides for customizing field types and properties without full schema definitions

**Built-in Templates**:

- `default_schema.v1.json`: Basic schema with standard field types
- `template_with_content_analyzer.v1.json`: Template with custom content analyzer and indexing rules
- `full_schema.v1.json`: Example of full schema format with complete mappings

**Supported Placeholders**:

| Placeholder             | Description                | Example Value                          |
| ----------------------- | -------------------------- | -------------------------------------- |
| `__VECTOR_DIMENSION__`  | Vector embedding dimension | `384`, `768`, `1536`                   |
| `__ENGINE__`            | KNN engine name            | `faiss`, `lucene`, `nmslib`, `jvector` |
| `__ALGORITHM__`         | KNN algorithm              | `hnsw`, `ivf`                          |
| `__SPACE_TYPE__`        | Similarity metric          | `l2`, `cosine`, `inner_product`        |
| `__ENGINE_PARAMETERS__` | Engine-specific parameters | `{"ef_construction": 128, "m": 24}`    |

**Schema Format Options**:

Templates support two formats:

1. **Template Schema** (with `field_types` + optional `indexing_rules`): Dynamic field mapping with type templates
2. **Full Schema** (with `mappings`): Complete OpenSearch mapping definition

**Template Schema Structure**:

```json
{
  "schema_name": "default",
  "schema_version": 1,
  "settings": {
    "index": {
      "knn": true,
      "number_of_shards": 2,
      "number_of_replicas": 1
    }
  },
  "field_types": {
    "vector": {
      "type": "knn_vector",
      "dimension": "__VECTOR_DIMENSION__",
      "method": {
        "name": "__ALGORITHM__",
        "space_type": "__SPACE_TYPE__",
        "engine": "__ENGINE__",
        "parameters": "__ENGINE_PARAMETERS__"
      }
    },
    "string": {
      "type": "text",
      "fields": {
        "keyword": {
          "type": "keyword",
          "ignore_above": 256
        }
      }
    }
  },
  "indexing_rules": {
    "content": {
      "field_type": "content_text",
      "boost": 2.0,
      "copy_to": ["all_text"]
    }
  }
}
```

**Usage Example**:

```json
{
  "operator_type": "datasift.core.operators.vectordb.vectordb_operator.VectorDBOperator",
  "operator_params": {
    "provider": "opensearch",
    "index_name": "document_chunks",
    "provider_config": {
      "schema_template_path": "schemas/template_with_content_analyzer.v1.json",
      "host": "localhost",
      "port": 9200,
      "engine": "faiss",
      "algorithm": "hnsw"
    }
  }
}
```

**Note:** Vector dimensions are auto-detected from embedding data.

#### Indexing Rules System

**Purpose**: Enable flexible field-level customization without requiring full schema definitions. Indexing rules allow overriding field types and properties for specific fields while using template-based field type definitions for the rest.

**Key Features**:

1. **Field Type Override**: Map specific fields to custom field types defined in `field_types`
2. **Property Overrides**: Add or override specific OpenSearch mapping properties for individual fields without redefining the entire field type
3. **Dual Lookup Resolution**: Supports both feature names and mapped names for field resolution
4. **Allowlist Protection**: Only safe properties can be overridden to prevent schema corruption
5. **Deep Merging**: Nested properties are recursively merged with field type definitions

**Property Overrides Explained**:

Property overrides let you customize specific OpenSearch mapping properties for individual fields. Instead of creating a new field type for every variation, you can reuse a base field type and override just the properties you need.

**Common Use Cases**:

- **`boost`**: Increase relevance score for important fields (e.g., title gets boost of 3.0, content gets 2.0)
- **`copy_to`**: Copy field values to a combined search field (e.g., copy title and content to "all_text" for unified search)
- **`analyzer`**: Use different text analysis for specific fields (e.g., use "keyword_analyzer" for product codes)
- **`fields`**: Add sub-fields with different analysis (e.g., add "exact" keyword sub-field for case-sensitive matching)

**Supported Properties**: `analyzer`, `search_analyzer`, `copy_to`, `boost`, `index`, `store`, `similarity`, `normalizer`, `fields`

**Example - Boosting Important Fields**:

```json
{
  "indexing_rules": {
    "title": {
      "field_type": "string",
      "boost": 3.0,
      "copy_to": ["all_text"]
    },
    "content": {
      "field_type": "string",
      "boost": 2.0,
      "copy_to": ["all_text"]
    },
    "summary": {
      "field_type": "string",
      "boost": 1.5,
      "copy_to": ["all_text"]
    }
  }
}
```

In this example, all three fields use the same `string` field type, but each has different boost values to control search relevance. The `title` field is 3x more important than unboost fields, `content` is 2x, and `summary` is 1.5x.

**Indexing Rules Structure**:

```json
{
  "indexing_rules": {
    "field_name": {
      "field_type": "custom_type",
      "boost": 2.0,
      "copy_to": ["all_text"],
      "analyzer": "custom_analyzer"
    }
  }
}
```

**Example: Content Field with Custom Analyzer**:

```json
{
  "schema_name": "document_chunks",
  "schema_version": 1,
  "settings": {
    "analysis": {
      "analyzer": {
        "content_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "stop", "snowball"]
        }
      }
    }
  },
  "field_types": {
    "string": {
      "type": "text",
      "fields": {
        "keyword": {
          "type": "keyword",
          "ignore_above": 256
        }
      }
    },
    "content_text": {
      "type": "text",
      "analyzer": "content_analyzer",
      "fields": {
        "keyword": {
          "type": "keyword",
          "ignore_above": 256
        }
      }
    }
  },
  "indexing_rules": {
    "content": {
      "field_type": "content_text"
    }
  }
}
```

In this example:

- The `content` field uses `content_text` field type instead of the default `string` type
- The `content_text` type applies a custom analyzer with stemming and stop word removal
- Other string fields continue using the default `string` field type

**Lookup Priority**:

When resolving field configurations, the system follows this priority:

1. Check `indexing_rules` for the feature name (e.g., `content`)
2. Check `indexing_rules` for the mapped name (e.g., `doc_content`)
3. Fall back to `system_type` from `available_features` configuration
4. Use default field type if no match found

**Reserved Fields Protection**:

System fields cannot be overridden via indexing rules:

- `_id`
- `_index`
- `_source`
- `_type`
- `_meta`

**Validation and Safety**:

- Property overrides are validated against an allowlist to prevent invalid configurations
- Invalid field types in indexing rules raise clear error messages
- Empty analysis blocks are automatically removed to prevent OpenSearch errors
- Mapping explosion protection limits total fields to 2000 by default

**Implementation Details**:

The indexing rules system is implemented in `OpenSearchIndexManager._build_index_body_from_field_type_template()`:

1. **Field Type Resolution**: Looks up field type from `indexing_rules` or falls back to `system_type`
2. **Base Mapping Creation**: Retrieves field type definition from `field_types` section
3. **Property Override Application**: Deep merges allowlisted properties from indexing rules
4. **Dual Lookup Support**: Checks both feature name and mapped name for maximum flexibility
5. **Validation**: Ensures field types exist and properties are safe to override

**Benefits**:

- **Flexibility**: Customize specific fields without duplicating entire schema
- **Maintainability**: Centralized field type definitions with per-field overrides
- **Safety**: Allowlist protection prevents accidental schema corruption
- **Backward Compatibility**: Existing schemas without indexing rules continue to work
- **Clarity**: Clear separation between field type templates and field-specific customizations

#### Metadata Column Normalization

**Purpose**: Automatically normalize metadata column names and derive missing fields to ensure consistent document metadata across different data sources.

**Column Name Aliases**:

The system automatically maps common column name variations to standard names:

| Target Field | Source Aliases                          | Description          |
| ------------ | --------------------------------------- | -------------------- |
| `source`     | `source`, `path`                        | Document source path |
| `page_count` | `page_count`, `pages_processed`         | Number of pages      |
| `mimetype`   | `mimetype`, `mime_type`, `content_type` | MIME type            |

**Field Derivation**:

Missing metadata fields are automatically derived when possible:

- **extension**: Derived from `name` or `source` filename if missing
- **mimetype**: Derived from `extension` using standard MIME type mappings

**Predefined Metadata Fields**:

The following fields are automatically collected into a `metadata` object:

- `name`: Document filename
- `size`: File size in bytes
- `created_time`: Creation timestamp
- `modified_time`: Modification timestamp
- `source`: Document source path
- `mimetype`: MIME type
- `extension`: File extension
- `page_count`: Number of pages

**Example Transformation**:

```python
# Input row data
{
  "path": "/docs/report.pdf",
  "name": "report.pdf",
  "pages_processed": 10,
  "content": "..."
}

# Automatically normalized to
{
  "content": "...",
  "metadata": {
    "source": "/docs/report.pdf",
    "name": "report.pdf",
    "page_count": 10,
    "extension": "pdf",
    "mimetype": "application/pdf"
  }
}
```

#### Schema Validation

The system performs comprehensive validation of schema templates:

1. **Structure Validation**: Ensures required schema components are present
2. **Vector Field Validation**: Validates KNN vector configuration
3. **Parameter Range Validation**: Checks engine parameters are within valid ranges
4. **Analyzer Validation**: Validates custom analyzer configurations

**Validation Example**:

```python
# Invalid schema - missing required fields
{
  "settings": {},
  "field_types": {}
}
# Error: Schema missing required 'schema_name' field

# Invalid vector configuration
{
  "field_types": {
    "vector": {
      "type": "knn_vector",
      "dimension": -1  # Invalid dimension
    }
  }
}
# Error: Vector dimension must be positive
```

#### Implementation Architecture

```mermaid
graph TB
    subgraph "VectorDBOperator"
        VDB[VectorDBOperator]
    end

    subgraph "OpenSearch Adapter"
        OSA[OpenSearchAdapter]
        IM[IndexManager]
        BP[BatchProcessor]
    end

    subgraph "Schema Management"
        ST[Schema Templates]
        PH[Placeholder Replacement]
        VAL[Schema Validation]
    end

    subgraph "Metadata Processing"
        NORM[Column Normalization]
        DERIV[Field Derivation]
        AGG[Metadata Aggregation]
    end

    VDB --> OSA
    OSA --> IM
    OSA --> BP
    IM --> ST
    ST --> PH
    PH --> VAL
    BP --> NORM
    NORM --> DERIV
    DERIV --> AGG

    style VDB fill:#ffe1e1
    style IM fill:#e1ffe1
    style BP fill:#e1ffe1
    style ST fill:#fff4e1
    style NORM fill:#e1f5ff
```

**Key Components**:

- **OpenSearchIndexManager**: Handles schema template loading, placeholder replacement, and validation
- **OpenSearchBatchProcessor**: Handles metadata normalization, field derivation, and aggregation
- **Schema Templates**: JSON files defining reusable index configurations
- **Validation System**: Ensures schema correctness before index creation

### 5. Milvus Integration Architecture

```mermaid
graph TB
    subgraph "Datasift Layer"
        VDB[VectorDBOperator]
    end
    
    subgraph "Adapter Layer (Hexagonal)"
        PORT[VectorDB Port<br/>Interface]
        MA[Milvus Adapter]
    end
    
    subgraph "Milvus Service"
        MS[Milvus Server<br/>localhost:19530]
        COLL[Collections]
        IDX1[HNSW Index]
        IDX2[IVF_FLAT Index]
        IDX3[FLAT Index]
    end
    
    VDB --> PORT
    PORT --> MA
    MA --> MS
    MS --> COLL
    COLL --> IDX1
    COLL --> IDX2
    COLL --> IDX3
    
    style VDB fill:#ffe1e1
    style PORT fill:#fff4e1
    style MA fill:#e1ffe1
    style MS fill:#e1f5ff
```

**Hexagonal Architecture Benefits:**

1. **Decoupling**: VectorDBOperator independent of Milvus specifics
2. **Testability**: Easy to mock adapters for testing
3. **Extensibility**: Add new vector DB adapters without changing operator
4. **Flexibility**: Switch vector databases via configuration

**Supported Index Types:**
- **Dense Vectors**: HNSW, IVF_FLAT, IVF_SQ8, IVF_PQ, FLAT, DISKANN, AUTOINDEX
- **Sparse Vectors**: SPARSE_INVERTED_INDEX, SPARSE_WAND

**Supported Metric Types:**
- **Dense Vectors**: L2 (Euclidean), IP (Inner Product), COSINE (Cosine similarity)
- **Sparse Vectors**: BM25 (required for sparse mode)

**Vector Modes:**
- **Dense Only** (default): Stores only dense embeddings from embeddings operator
- **Sparse + Dense**: Dual storage mode with BM25 function generating sparse vectors from content
  - Requires `add_sparse_vector: true` and `metric_type: "BM25"`
  - Still requires embeddings operator in pipeline
  - Stores both dense embeddings and BM25-generated sparse vectors

**Example Configuration (Dense Vectors):**
```json
{
  "operator": "vectordb",
  "config": {
    "provider": "milvus",
    "index_name": "my_collection",
    "create_index": true,
    "add_sparse_vector": false,
    "provider_config": {
      "auth_type": "standalone",
      "host": "localhost",
      "port": 19530,
      "uri": null,
      "token": null,
      "username": "root",
      "password": "Milvus", # pragma: allowlist secret
      "database": "default",
      "secure": false,
      "index_type": "HNSW",
      "metric_type": "L2",
      "index_parameters": {
        "M": 16,
        "efConstruction": 256
      },
      "batch_size": 100,
      "primary_key_field": "pk"
    }
  }
}
```

**Note:** Vector dimension is auto-detected from `embeddings` column data. Milvus currently supports single vector column (multi-model support planned for future update).

**Example Configuration (Sparse Vectors):**
```json
{
  "id": "b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e",
  "operator": "vectordb",
  "config": {
    "provider": "milvus",
    "index_name": "documents_sparse",
    "add_sparse_vector": true,
    "provider_config": {
      "auth_type": "standalone",
      "host": "localhost",
      "port": 19530,
      "username": "root",
      "password": "Milvus", # pragma: allowlist secret
      "index_type": "SPARSE_INVERTED_INDEX",
      "metric_type": "BM25",
      "primary_key_field": "pk"
    }
  }
}
```

**Authentication Types:**
- `standalone`: Local Milvus with optional username/password
- `grpc`: IBM wx.data with gRPC (username with `ibmlhapikey_` prefix, password is API key)
- `uri`: Pre-constructed URI with embedded API key
- `token`: IAM token-based authentication

**Deployment Support:**
- **Standalone Milvus**: Single-node deployment for development and testing
- **wx.data**: IBM watsonx.data integration for enterprise deployments with multiple auth options

### 6. Embeddings Operator Integration Architecture

The Embeddings Operator supports multiple embedding providers through a hexagonal architecture with pluggable adapters:

**Supported Providers:**
- **Ollama** - Local LLM server for privacy-focused deployments
- **HuggingFace** - Open-source models with local or API options
- **LiteLLM** - Unified API for 100+ providers (OpenAI, Azure, Cohere, AWS, etc.)
- **Watsonx** - IBM watsonx.ai cloud service with IAM authentication

**Architecture Pattern:**

```mermaid
graph TB
    subgraph "Core Layer"
        EMB[EmbeddingsOperator]
    end

    subgraph "Adapter Layer"
        OLA[OllamaLLMAdapter]
        HFA[HuggingFaceLLMAdapter]
        LLA[LiteLLMLLMAdapter]
        WXA[WatsonxLLMAdapter]
    end

    subgraph "Client Layer"
        OLC[OllamaClient]
        HFC[HuggingFaceClient]
        LLC[LiteLLMClient]
        WRC[WatsonxRestClient]
    end

    subgraph "External Services"
        OLS[Ollama Server]
        HFS[HuggingFace API]
        LLS[LiteLLM Providers]
        WXS[Watsonx.ai API]
    end

    EMB --> OLA
    EMB --> HFA
    EMB --> LLA
    EMB --> WXA

    OLA --> OLC --> OLS
    HFA --> HFC --> HFS
    LLA --> LLC --> LLS
    WXA --> WRC --> WXS
```

**Configuration Examples:**

Ollama (Local):
```json
{
  "embeddings_type": "ollama",
  "embeddings_model_id": "nomic-embed-text",
  "embeddings_column": "embeddings"
}
```

HuggingFace (Local):
```json
{
  "embeddings_type": "huggingface",
  "embeddings_model_id": "sentence-transformers/all-MiniLM-L6-v2",
  "embeddings_column": "embeddings",
  "provider_config": {
    "device": "cuda"
  }
}
```

LiteLLM (OpenAI):
```json
{
  "embeddings_type": "litellm",
  "embeddings_model_id": "text-embedding-3-small",
  "embeddings_column": "embeddings",
  "provider_config": {
    "api_key": "${OPENAI_API_KEY}"
  }
}
```

Watsonx (IBM Cloud):
```json
{
  "embeddings_type": "watsonx",
  "embeddings_model_id": "ibm/slate-125m-english-rtrvr",
  "embeddings_column": "embeddings",
  "provider_config": {
    "api_key": "${WATSONX_API_KEY}",
    "api_base": "${WATSONX_API_BASE}",
    "container_id": "${WATSONX_CONTAINER_ID}"
  }
}
```

**Key Features:**
- Hexagonal architecture with port/adapter pattern
- Automatic retry logic and error handling
- Dynamic dimension detection for supported providers
- Batch processing support
- Provider-specific optimizations

### 7. Docling Integration Architecture

```mermaid
graph TB
    subgraph "Datasift Layer"
        EXT[ExtractOperator]
    end

    subgraph "Client Layer"
        DC[DoclingServeClient]
        RC[RestClient]
    end

    subgraph "Docling Service"
        DS[Docling Server<br/>localhost:5000]
        PDF[PDF Parser]
        DOCX[DOCX Parser]
        TABLE[Table Extractor]
    end

    ED --> DC
    DC --> RC
    RC --> DS
    DS --> PDF
    DS --> DOCX
    DS --> TABLE

    style ED fill:#ffe1e1
    style DC fill:#fff4e1
    style DS fill:#e1f5ff
```

**Integration Features:**

1. **Document Parsing**: Extract text and structure from PDFs, DOCX
2. **Table Extraction**: Identify and extract tables with structure
3. **Metadata Extraction**: Document properties, page count, etc.
4. **Batch Processing**: Process multiple documents efficiently

**Supported Providers:**

- **Docling Library (Local)**: Local document processing and chunking using the Docling library
  - Used by ExtractOperator for document parsing
  - Used by Chunker operator with `provider: "docling_library"` for local Hybrid chunking
- **Docling-serve (Remote)**: Remote Hybrid chunking via docling-serve API
  - Used by Chunker operator with `provider: "docling_serve"` for distributed Hybrid chunking
  - Enables offloading Hybrid chunking computation to dedicated service
  - Only supports Hybrid chunking strategy

**Example Configuration:**

```json
{
  "operator": "extract_docling",
  "config": {
    "doc_column": "content",
    "extract_tables": true,
    "extract_images": false
  }
}
```

### 8. DocumentClassifier Pattern

The DocumentClassifier operator classifies documents into predefined categories using Large Language Models. It uses a simplified service-based architecture that leverages the shared LLM adapter infrastructure for multi-provider support.

**Typical Workflow Position:**

```mermaid
graph LR
    A[Ingest] --> B[DocumentClassifier]
    B --> C[Extract]
    C --> D[Chunk]
    D --> E[Embed]
    E --> F[VectorDB]

    style A fill:#e1f5ff
    style B fill:#e6ffe6
    style C fill:#ffe1f5
    style D fill:#f5ffe1
    style E fill:#fff5e1
    style F fill:#e1fff5
```

**Simplified Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                   DocumentClassifierOperator                 │
│                     (Main Operator)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  ClassificationService                       │
│              (Business Logic Layer)                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Domain Models:                                       │  │
│  │  - ClassificationRequest                              │  │
│  │  - ClassificationResponse                             │  │
│  │  - build_classification_prompt()                      │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Shared LLM Adapter Infrastructure               │
│                  (LLMAdapterFactory)                         │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   LiteLLM    │  │  Watsonx.ai  │  │ HuggingFace  │
│   Client     │  │   Client     │  │   Client     │
└──────────────┘  └──────────────┘  └──────────────┘
```

**Classification Features:**

1. **LLM-Based Classification**: Uses Large Language Models for intelligent document classification
2. **Multi-Provider Support**: LiteLLM (100+ providers) and IBM watsonx.ai via shared LLM infrastructure
3. **Simplified Architecture**: Direct service-based design without port/adapter overhead
4. **Confidence Scoring**: 1-10 scale confidence scores for each classification
5. **Reasoning Output**: Optional explanations for classification decisions
6. **Shared Infrastructure**: Leverages common LLM adapter factory for consistency

**Supported Providers:**

- **LiteLLM**: Unified interface for 100+ providers (OpenAI, Anthropic, Azure, AWS Bedrock, Google, etc.)
  - Use with Ollama via OpenAI-compatible API: `provider='litellm'`, `api_base='http://localhost:11434/v1'`
- **Watsonx**: IBM watsonx.ai enterprise LLM platform

**Example Configuration:**

```json
{
  "operator_type": "DocumentClassifier",
  "operator_params": {
    "provider": "litellm",
    "model_id": "openai/gpt-4o-mini",
    "provider_config": {
      "api_key": "${OPENAI_API_KEY}"
    },
    "document_types": {
      "invoice": "Business invoice with line items and totals",
      "contract": "Legal contract or agreement",
      "receipt": "Payment receipt or confirmation",
      "report": "Business or technical report"
    },
    "confidence_threshold": 7.0,
    "include_confidence": true,
    "include_reasoning": true
  }
}
```

**Architecture Benefits:**

- **Testability**: Domain logic can be tested independently of LLM providers
- **Flexibility**: Easy to switch between providers or add new ones
- **Maintainability**: Clear separation of concerns
- **Extensibility**: New adapters can be added without modifying core logic

**Use Cases:**

- Route documents to specialized extraction pipelines based on type
- Filter documents by category before expensive processing
- Enrich metadata with document type information
- Enable type-specific chunking or embedding strategies

**Watsonx.ai Configuration Notes:**

- **Authentication**: IAM token-based authentication using `WATSONX_API_KEY`
- **Container Targeting**: Set `WATSONX_CONTAINER_ID` to a project ID or space ID
- **Optional Overrides**: Use `WATSONX_API_BASE_URL` and `WATSONX_CONTAINER_KIND` when the default region or container type is not appropriate
- **Non-Sensitive Settings**: Keep runtime options such as `api_base`, `container_kind`, and `request_timeout` in `provider_config`

### 9. External Service Pattern

**Common Pattern for All Integrations:**

```mermaid
sequenceDiagram
    participant OP as Operator
    participant CL as Client
    participant SVC as External Service

    OP->>CL: Initialize client
    CL->>SVC: Check availability
    SVC-->>CL: Service ready

    loop For each document
        OP->>CL: Process request
        CL->>SVC: API call
        alt Success
            SVC-->>CL: Return result
            CL-->>OP: Processed data
        else Failure
            SVC-->>CL: Error response
            CL->>CL: Retry logic
            alt Retry succeeds
                SVC-->>CL: Return result
                CL-->>OP: Processed data
            else Retry fails
                CL-->>OP: Error
                OP->>OP: Record failure
            end
        end
    end
```

**Client Responsibilities:**

1. Connection management
2. Request/response handling
3. Retry logic with exponential backoff
4. Error handling and logging
5. Timeout management

### 10. PIIAndHAPAnnotator Hexagonal Architecture Pattern

The PIIAndHAPAnnotator operator detects Personally Identifiable Information (PII) and Hate, Abuse, and Profanity (HAP) content using shared common-infrastructure ports and adapters. WatsonX uses its native text-detection API, while LiteLLM uses prompt-based chat inference.

```mermaid
graph TB
    subgraph "Datasift Layer"
        PIIHAP[PIIAndHAPAnnotator]
    end

    subgraph "Service Architecture"
        SERVICE[PIIHAPService<br/>Business Logic]
        INFPORT[LLMInferencePort]
        DETPORT[TextDetectionPort]
        LITELLM[LiteLLMAdapter]
        WATSONXDET[WatsonXAdapter<br/>text detection]
    end

    subgraph "External Services"
        LITELLMAPI[LiteLLM / OpenAI-compatible APIs<br/>100+ Providers]
        WATSONXAPI[WatsonX.ai /ml/v1/text/detection<br/>IBM Cloud]
    end

    PIIHAP --> SERVICE
    SERVICE --> INFPORT
    SERVICE --> DETPORT
    INFPORT --> LITELLM
    DETPORT --> WATSONXDET

    LITELLM --> LITELLMAPI
    WATSONXDET --> WATSONXAPI

    style PIIHAP fill:#ffe1e1
    style SERVICE fill:#fff4e1
    style INFPORT fill:#fff4e1
    style DETPORT fill:#fff4e1
    style LITELLM fill:#e1ffe1
    style WATSONXDET fill:#e1ffe1
```

**Supported Providers:**

1. **WatsonX.ai**: IBM's enterprise AI platform
   - IAM-based authentication
   - Enterprise-grade SLAs
   - Compliance certifications
   - Managed infrastructure

2. **LiteLLM**: Multi-provider unified interface
   - 100+ LLM providers supported
   - OpenAI (gpt-4, gpt-3.5-turbo)
   - Anthropic (claude-3-opus, claude-3-sonnet)
   - Azure OpenAI, Cohere, AWS Bedrock, Google Vertex AI
   - Easy provider switching

**Configuration Examples:**

**WatsonX.ai (Enterprise):**

```json
{
  "operator": "core.operators.quality.pii_and_hap.pii_and_hap_annotator.PIIAndHAPAnnotator",
  "config": {
    "provider": "watsonx",
    "provider_config": {
      "api_key": "your-ibm-cloud-api-key",  # pragma: allowlist secret
      "url": "https://us-south.ml.cloud.ibm.com",
      "container_id": "your-project-id",
      "container_kind": "project",
      "timeout": 300
    }
  }
}
```

**LiteLLM (Multi-Provider):**

```json
{
  "operator": "core.operators.quality.pii_and_hap.pii_and_hap_annotator.PIIAndHAPAnnotator",
  "config": {
    "provider": "litellm",
    "model_name": "gpt-4",
    "provider_config": {
      "api_key": "sk-..."  # pragma: allowlist secret
    }
  }
}
```

**Key Features:**

1. **Detection Types**:
   - **PII**: Email, phone, SSN, credit cards, addresses, names, DOB, medical records
   - **HAP**: Hate speech, abuse, profanity, discrimination, threats, harassment

2. **Output Format**:
   - Structured JSON with detection type, score, location (start/end), and matched text
   - Confidence scores for each detection
   - Compatible with downstream redaction operators

3. **Provider Flexibility**:
   - Switch providers without code changes
   - Configuration-driven provider selection
   - Ollama can be accessed through LiteLLM via an OpenAI-compatible `api_base`
   - Production deployment with WatsonX or LiteLLM

4. **Extensibility**:
   - Add new providers by extending the shared adapter and port infrastructure
   - Reuse provider integrations across operators
   - Keep operator-specific behavior isolated in `PIIHAPService`

**Use Cases:**

1. **Compliance Scanning**: Detect PII in documents for GDPR/CCPA compliance
2. **Content Moderation**: Identify HAP content in user-generated content
3. **Data Loss Prevention**: Prevent sensitive information leakage
4. **Document Sanitization**: Prepare documents for public release
5. **Risk Assessment**: Evaluate content risk before processing
6. **Audit Trail**: Track PII/HAP detections for compliance reporting

**Integration with Other Operators:**

```mermaid
graph LR
    A[IngestSource] --> B[ExtractOperator]
    B --> C[PIIAndHAPAnnotator]
    C --> D[Redaction]
    D --> E[Chunker]
    E --> F[EmbeddingsOperator]
    F --> G[VectorDBOperator]

    style A fill:#e1f5ff
    style B fill:#ffe1f5
    style C fill:#f5ffe1
    style D fill:#fff5e1
    style E fill:#e1fff5
    style F fill:#ffe1e1
    style G fill:#e1ffe1
```

**Typical Pipeline:**

1. **IngestSource**: Load documents from storage
2. **ExtractOperator**: Extract text content
3. **PIIAndHAPAnnotator**: Detect sensitive content
4. **Redaction**: Mask or remove detected PII/HAP
5. **Chunker**: Split sanitized documents into chunks
6. **EmbeddingsOperator**: Generate vector embeddings
7. **VectorDBOperator**: Store embeddings in vector database

See [PII and HAP Operator Documentation](docs/operators/pii_and_hap/pii_and_hap.md) for detailed usage guide.

---

### 7. IngestSource Multi-Provider Pattern

The IngestSource operator provides a unified interface for ingesting documents from multiple storage providers and data sources. It uses an adapter-based architecture for extensibility and supports both LangChain loaders and custom adapters.

```mermaid
graph TB
    subgraph "Datasift Layer"
        ISO[IngestSourceOperator]
    end

    subgraph "Adapter Architecture"
        SAF[SourceAdapterFactory]
        OBJA[Object Storage Adapter]
        IBMA[IBM COS Adapter]
        GDA[Google Drive Adapter]
        SPA[SharePoint Adapter]
        ODA[OneDrive Adapter]
        WPA[WebPageSourceAdapter]
        CUST[Custom Loaders]
    end

    subgraph "External Services"
        OBJ[Object Storage]
        IBM[IBM Cloud Object Storage]
        GD[Google Drive API]
        MS[Microsoft Graph API]
        CUSTOM[Custom Data Sources]
    end

    ISO --> SAF
    SAF --> OBJA
    SAF --> IBMA
    SAF --> GDA
    SAF --> SPA
    SAF --> ODA
    SAF --> WPA
    SAF --> CUST

    OBJA --> OBJ
    IBMA --> IBM
    GDA --> GD
    SPA --> MS
    ODA --> MS
    WPA --> CUSTOM
    CUST --> CUSTOM

    style ISO fill:#ffe1e1
    style SAF fill:#fff4e1
    style OBJA fill:#e1ffe1
    style IBMA fill:#e1ffe1
    style GDA fill:#e1ffe1
    style SPA fill:#e1ffe1
    style ODA fill:#e1ffe1
    style WPA fill:#e1ffe1
```

**Supported Providers:**

1. **Object Storage**: S3-compatible object storage
   - Bucket-based access
   - Prefix-based filtering
   - Binary content download via boto3

2. **IBM Cloud Object Storage (COS)**: IBM's S3-compatible storage
   - Custom endpoint configuration
   - S3-compatible API
   - Enterprise-grade storage

3. **Microsoft SharePoint**: Document management and collaboration
   - Microsoft Graph API integration
   - App-only (client credentials) authentication
   - Drive and folder-based access
   - Recursive directory traversal

4. **Microsoft OneDrive**: Personal and business cloud storage
   - Microsoft Graph API integration
   - Same authentication as SharePoint
   - Personal and shared drives support

5. **Google Drive**: Google's cloud storage service
   - OAuth2 authentication
   - Service account support
   - Folder hierarchy navigation
   - Shared drive access

6. **Web Pages**: Recursive website and documentation crawling
   - Backed by LangChain `RecursiveUrlLoader`
   - Multi-URL crawl entry points
   - Domain-bound crawling with optional external link following
   - URL path exclusion patterns and configurable request timeouts

7. **Custom Loaders**: Extensible loader framework
   - Dynamic loader import
   - LangChain-compatible interface
   - Provider-specific implementations

**Architecture Features:**

1. **Adapter Pattern**: Decouples operator from provider-specific implementations
2. **Factory Pattern**: Automatic adapter selection based on provider name
3. **Async Support**: Efficient document fetching with async/await
4. **Binary Content Handling**: Pre-fetches binary content for downstream processing
5. **Incremental Updates**: Tracks processed documents to avoid re-ingestion
6. **Metadata Enrichment**: Extracts file metadata (size, modified time, mimetype)

**Configuration Examples:**

**Object Storage:**

```json
{
  "operator": "IngestSourceOperator",
  "config": {
    "provider": "s3",
    "connection_params": {
      "bucket": "my-documents",
      "prefix": "invoices/"
    },
    "credentials": {
      "access_key": "your-access-key",  # pragma: allowlist secret
      "secret_key": "your-secret-key"  # pragma: allowlist secret
    },
    "max_files": 100,
    "include_filter": ".pdf,.docx",
    "ignore_hidden_files": true
  }
}
```

**IBM Cloud Object Storage:**

```json
{
  "operator": "IngestSourceOperator",
  "config": {
    "provider": "ibm_cos",
    "connection_params": {
      "bucket": "enterprise-docs",
      "endpoint_url": "https://s3.us-south.cloud-object-storage.appdomain.cloud",
      "prefix": "contracts/"
    },
    "credentials": {
      "access_key": "your-access-key",  # pragma: allowlist secret
      "secret_key": "your-secret-key"  # pragma: allowlist secret
    },
    "max_files": 500
  }
}
```

**Microsoft SharePoint:**

```json
{
  "operator": "IngestSourceOperator",
  "config": {
    "provider": "sharepoint",
    "connection_params": {
      "drive_id": "b!abc123...",
      "folder_path": "/Shared Documents/Projects",
      "recursive": true
    },
    "credentials": {
      "client_id": "your-app-client-id",
      "client_secret": "your-app-secret",  # pragma: allowlist secret
      "tenant_id": "your-tenant-id"
    },
    "include_filter": ".pdf,.docx,.xlsx",
    "max_files": 200
  }
}
```

**Microsoft OneDrive:**

```json
{
  "operator": "IngestSourceOperator",
  "config": {
    "provider": "onedrive",
    "connection_params": {
      "drive_id": "b!xyz789...",
      "folder_path": "/Documents/Reports",
      "recursive": false
    },
    "credentials": {
      "client_id": "your-app-client-id",
      "client_secret": "your-app-secret",  # pragma: allowlist secret
      "tenant_id": "your-tenant-id"
    },
    "exclude_filter": ".tmp,.bak"
  }
}
```

**Google Drive:**

```json
{
  "operator": "IngestSourceOperator",
  "config": {
    "provider": "google_drive",
    "connection_params": {
      "folder_id": "1a2b3c4d5e6f7g8h9i0j",
      "recursive": true
    },
    "credentials": {
      "service_account_key": "/path/to/service-account-key.json"
    },
    "max_files": 150
  }
}
```

**Web Pages:**
```json
{
  "operator": "IngestSourceOperator",
  "config": {
    "provider": "web",
    "connection_params": {
      "urls": ["https://example.com", "https://www.iana.org/domains/reserved"],
      "max_depth": 2,
      "prevent_outside": true,
      "exclude_patterns": ["/admin", "/login", "/api"],
      "timeout": 30
    },
    "credentials": {}
  }
}
```

**Key Features:**

1. **Authentication Methods**:
   - Access key credentials (object storage, IBM COS)
   - OAuth2 client credentials (SharePoint, OneDrive)
   - Service account keys (Google Drive)
   - No credentials required for public web crawling with the web adapter
   - Custom authentication for extensible loaders

2. **Filtering Capabilities**:
   - Extension-based include/exclude filters
   - Hidden file filtering (files starting with '.')
   - Prefix-based path filtering
   - Maximum file count limits

3. **Metadata Extraction**:
   - File name, size, and modified time
   - MIME type and file extension
   - Source URL and unique identifiers
   - Provider-specific metadata

4. **Binary Content Handling**:
   - Pre-fetches binary content for downstream operators
   - Efficient memory management
   - Fallback to text content when binary unavailable
   - Compatible with ExtractOperator and other extract operators

5. **Incremental Processing**:
   - Tracks previously processed documents
   - Skips unchanged files on subsequent runs
   - Force re-ingestion option available
   - Job-based tracking for multi-run workflows

**Use Cases:**

1. **Multi-Source Document Ingestion**: Ingest documents from multiple storage providers in a single pipeline
2. **Enterprise Content Migration**: Migrate documents from SharePoint/OneDrive to vector databases
3. **Compliance Document Processing**: Process regulatory documents from object storage or IBM COS with audit trails
4. **Knowledge Base Construction**: Build searchable knowledge bases from Google Drive folders or recursively crawled websites
5. **Documentation Site Ingestion**: Crawl public documentation portals and marketing sites with `RecursiveUrlLoader`
6. **Hybrid Workflows**: Combine on-premises, cloud storage, and web content sources
7. **Incremental Updates**: Efficiently process only new or modified documents

**Integration with Other Operators:**

```mermaid
graph LR
    A[IngestSource] --> B[ExtractOperator]
    B --> C[Chunker]
    C --> D[EmbeddingsOperator]
    D --> E[VectorDBOperator]

    style A fill:#e1f5ff
    style B fill:#ffe1f5
    style C fill:#f5ffe1
    style D fill:#fff5e1
    style E fill:#e1fff5
```

**Typical Pipeline:**

1. **IngestSource**: Load documents from cloud storage
2. **ExtractOperator**: Extract structured content from binary files
3. **Chunker**: Split documents into manageable chunks
4. **EmbeddingsOperator**: Generate vector embeddings
5. **VectorDBOperator**: Store in OpenSearch or other vector databases

---

### 8. Document Set Hexagonal Architecture Pattern

The Document Set operator follows hexagonal architecture (ports and adapters pattern) for flexible storage backend support. It uses the storage layer interfaces (KeyValueStorage and TableStorage) for persistence.

#### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    DocumentSetOperator                      │
│         (Orchestrates via DocumentSetService)               │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌──────────────────┐    ┌──────────────────┐
│ Metadata Factory │    │ Data Store       │
│                  │    │ Factory          │
└────────┬─────────┘    └────────┬─────────┘
         │                       │
         ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│ Metadata Port    │    │ Data Store Port  │
│ (Interface)      │    │ (Interface)      │
└────────┬─────────┘    └────────┬─────────┘
         │                       │
         ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│ DuckDB Metadata  │    │ DuckDB Data      │
│ Adapter          │    │ Adapter          │
└────────┬─────────┘    └────────┬─────────┘
         │                       │
         ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│ KeyValueStorage  │    │ TableStorage     │
│ (Interface)      │    │ (Interface)      │
└──────────────────┘    └──────────────────┘
```

#### Components

**1. Domain Layer** (`src/datasift/core/assets/document_sets/domain/`)

- **Models** (`models/`): Pure Python domain entities
  - `DocumentSet`: Core entity for document collections
  - `StorageReference`: Physical storage location metadata
  - `DataCard`: Lineage and provenance tracking
- **Ports** (`ports/`): Abstract interfaces defining contracts
  - `DocumentSetMetadataRepository`: Metadata CRUD operations
  - `DocumentSetDataStore`: PyArrow table data operations
- **Types** (`types/`): TypedDict-based configuration types
  - `RepositoryConfig`: Metadata repository configuration
  - `DataStoreConfig`: Data store configuration
  - `HealthCheckResult`: Health check response structure

**2. Application Layer** (`src/datasift/core/assets/document_sets/application/`)

- **DocumentSetService** (`services/`): Business logic using port interfaces
- Orchestrates metadata and data operations
- Handles idempotent create-or-get behavior, data storage, preview, delete, and metric recomputation
- Independent of concrete storage implementation
- Injected with metadata repository and data store adapters

**3. Adapter Layer** (`src/datasift/core/assets/document_sets/adapters/`)

- **DuckDB Adapters** (`duckdb/`):
  - **DuckDBDocumentSetMetadataRepository**: Metadata persistence
    - Uses KeyValueStorage interface for JSON-based metadata
    - Stores in 'document_sets' collection
  - **DuckDBDocumentSetDataStore**: Data persistence
    - Uses TableStorage interface for PyArrow tables
    - Handles schema creation, upsert, preview, deletion
- Registered via `@MetadataRepositoryFactory.register()` and `@DataStoreFactory.register()` decorators
- Supports health checks and configuration validation

**4. Factory Layer** (`src/datasift/core/assets/document_sets/factories/`)

- **MetadataRepositoryFactory**: Creates metadata repository adapters
  - Decorator-based registration system
  - Validates configuration before instantiation
  - Supports multiple backends (currently: duckdb)
- **DataStoreFactory**: Creates data store adapters
  - Decorator-based registration system
  - Validates configuration before instantiation
  - Supports multiple backends (currently: duckdb)

#### Configuration

**Flow Configuration (global_config)**:

```json
{
  "global_config": {
    "storage_type": "duckdb",
    "database_path": "data/assets.db"
  },
  "nodes": [
    {
      "operator_type": "datasift.core.operators.storage.document_set.DocumentSetOperator",
      "operator_params": {
        "document_set_name": "my_documents",
        "description": "Document collection",
        "data_backend": "duckdb"
      }
    }
  ]
}
```

**Note**: The `metadata_backend` parameter is deprecated. Metadata storage is now controlled by `storage_type` in `global_config`.

#### Entry Points

Document sets can be managed through multiple entry points that share the same application and adapter layers:

1. **Pipeline execution** via `DocumentSetOperator`
   - Persists PyArrow tables during flow execution
   - Returns the original input table unchanged for downstream operators
   - Uses factory-created metadata and data adapters
   - Storage backend configured via `global_config.storage_type`

2. **REST API** via `/api/v1/document-sets`
   - Creates, lists, retrieves, updates, deletes, and previews document sets
   - Uses `DocumentSetService` with factory-created adapters
   - Storage backend determined by API configuration

3. **Flow definitions**
   - Use the `document_set` operator in DAG JSON
   - Typical pattern: `Ingest → Extract → [Other Operators] → DocumentSetOperator`

#### Adding New Storage Backends

To add PostgreSQL, MongoDB, or other backends:

1. **Implement Storage Layer Interfaces** (if needed):

```python
# Implement KeyValueStorage for metadata
class PostgreSQLKeyValueStorage(KeyValueStorage):
    def save_record(self, *, collection: str, key: str, data: dict[str, Any]) -> None:
        pass
    # ... other methods

# Implement TableStorage for data
class PostgreSQLTableStorage(TableStorage):
    def create_table(self, *, table_name: str, schema: pa.Schema) -> None:
        pass
    # ... other methods
```

2. **Register Storage in Factory**:

```python
# In StorageFactory
@staticmethod
def create_key_value_storage(*, storage_type: str, **config: Any) -> KeyValueStorage:
    if storage_type == "postgresql":
        return PostgreSQLKeyValueStorage(**config)
    # ... existing types
```

3. **Implement Document Set Adapters**:

```python
@MetadataRepositoryFactory.register(name="postgresql", display_name="PostgreSQL")
class PostgreSQLMetadataRepository(DocumentSetMetadataRepository):
    def __init__(self, *, key_value_storage: KeyValueStorage):
        self.storage = key_value_storage
    # ... implement port methods

@DataStoreFactory.register(name="postgresql", display_name="PostgreSQL")
class PostgreSQLDataStore(DocumentSetDataStore):
    def __init__(self, *, table_storage: TableStorage):
        self.storage = table_storage
    # ... implement port methods
```

4. **Update Configuration**:

```json
{
  "global_config": {
    "storage_type": "postgresql",
    "connection_string": "postgresql://user:pass@localhost:5432/documents"  # pragma: allowlist secret
  },
  "nodes": [
    {
      "operator_params": {
        "data_backend": "postgresql"
      }
    }
  ]
}
```

#### Benefits

- **Pluggable Storage**: Easy to swap storage backends via configuration
- **Testability**: Mock adapters can satisfy port contracts in unit tests
- **Maintainability**: Clear separation of domain, application, adapters, and storage layers
- **Type Safety**: TypedDict-based configuration and strong typing throughout
- **Performance**: Singleton pattern for storage instances, pass-through operator execution
- **Extensibility**: New adapters registered via decorators without changing business logic
- **Consistency**: Shared storage layer across flows and document sets

#### Usage Pattern

```json
{
  "global_config": {
    "storage_type": "duckdb",
    "database_path": "data/assets.db"
  },
  "nodes": [
    {
      "operator_type": "datasift.core.operators.storage.document_set.DocumentSetOperator",
      "operator_params": {
        "document_set_name": "my_documents",
        "description": "Processed documents",
        "data_backend": "duckdb",
        "metadata": { "source": "pipeline_v1" }
      }
    }
  ]
}
```

#### Data Flow

```
Ingest → Extract → [Other Operators] → DocumentSetOperator → [Downstream Operators]
                                              │
                                              ├─> MetadataRepositoryFactory → DuckDB adapter → KeyValueStorage
                                              ├─> DataStoreFactory → DuckDB adapter → TableStorage
                                              └─> Original table (pass-through)
```

#### Storage Type Configuration

The `storage_type` in `global_config` determines the storage backend for metadata:

- **"duckdb"** (default): Uses DuckDB for both metadata and data storage
  - Metadata stored in key-value tables
  - Data stored as PyArrow tables
  - Single database file for all assets
- **"filesystem"**: Uses filesystem for metadata (key-value only)
  - Metadata stored as JSON files
  - Data storage still requires DuckDB (via `data_backend`)
  - Suitable for development and small-scale deployments

**Note**: The `data_backend` parameter in operator configuration is separate from `storage_type` and controls where PyArrow table data is stored.

## Deployment Patterns

Datasift-opensource supports multiple deployment patterns to accommodate different operational requirements, from local development to enterprise-scale production deployments.

### 1. Local Development (ThreadPoolAdapter)

**Use Case:** Development, testing, and small-scale processing

**Architecture:**

```mermaid
graph TB
    subgraph "Single Machine"
        FE[FlowExecutor]
        PE[PrefectEngine]
        TPA[ThreadPoolAdapter]
        TP[ThreadPool]
        OP1[Operator 1]
        OP2[Operator 2]
        OP3[Operator 3]
    end

    FE --> PE
    PE --> TPA
    TPA --> TP
    TP --> OP1
    TP --> OP2
    TP --> OP3

    style FE fill:#e1f5ff
    style TPA fill:#e1ffe1
    style TP fill:#fff4e1
```

**Configuration:**

```json
{
  "work_pool": {
    "enabled": false
  }
}
```

**Characteristics:**

- No external infrastructure required
- In-memory batch passing
- Fast startup and iteration
- Limited to single machine resources
- Ideal for I/O-bound operations

**Setup:**

```bash
# No additional setup required
datasift-orchestrator --flow-file my-flow.json
```

---

### 2. Production Single-Node (ProcessPoolAdapter)

**Use Case:** CPU-intensive workloads on a single powerful machine

**Architecture:**

```mermaid
graph TB
    subgraph "Single Machine"
        FE[FlowExecutor]
        PE[PrefectEngine]
        WPA[WorkPoolAdapter]
        PP[ProcessPool]

        subgraph "Worker Processes"
            P1[Process 1]
            P2[Process 2]
            P3[Process 3]
            P4[Process 4]
        end

        FS[Local Filesystem<br/>Batch Storage]
    end

    FE --> PE
    PE --> WPA
    WPA --> PP
    PP --> P1
    PP --> P2
    PP --> P3
    PP --> P4

    WPA -.->|Write Batches| FS
    P1 -.->|Read/Write| FS
    P2 -.->|Read/Write| FS
    P3 -.->|Read/Write| FS
    P4 -.->|Read/Write| FS

    style FE fill:#e1f5ff
    style WPA fill:#e1ffe1
    style PP fill:#fff4e1
    style FS fill:#ffe1e1
```

**Configuration:**

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

**Characteristics:**

- True parallel processing with separate Python processes
- Bypasses GIL limitations
- Disk-based batch storage
- Scales to machine CPU cores
- Better for CPU-bound operations

**Setup:**

```bash
# Process pool is managed automatically
datasift-orchestrator --flow-file my-flow.json
```

---

### 3. Production Distributed Docker (WorkPoolAdapter + Docker)

**Use Case:** Containerized deployments with horizontal scaling

**Architecture:**

```mermaid
graph TB
    subgraph "Control Node"
        FE[FlowExecutor]
        PE[PrefectEngine]
        WPA[WorkPoolAdapter]
        PS[Prefect Server]
    end

    subgraph "Shared Storage"
        VOL[Docker Volume<br/>Batch Storage]
    end

    subgraph "Worker Nodes"
        W1[Docker Worker 1]
        W2[Docker Worker 2]
        W3[Docker Worker 3]
    end

    FE --> PE
    PE --> WPA
    WPA --> PS
    PS --> W1
    PS --> W2
    PS --> W3

    WPA -.->|Write Batches| VOL
    W1 -.->|Read/Write| VOL
    W2 -.->|Read/Write| VOL
    W3 -.->|Read/Write| VOL

    style FE fill:#e1f5ff
    style WPA fill:#e1ffe1
    style PS fill:#fff4e1
    style VOL fill:#ffe1e1
```

**Configuration:**

```json
{
  "work_pool": {
    "enabled": true,
    "type": "docker",
    "name": "datasift-docker-pool",
    "image": "datasift:latest",
    "batch_storage": {
      "type": "local",
      "base_path": "/app/data/batches"
    }
  }
}
```

**Characteristics:**

- Containerized execution environment
- Horizontal scaling across multiple hosts
- Shared volume for batch storage
- Consistent runtime environment
- Easy deployment and rollback

**Setup:**

1. **Build Docker Image:**

```bash
docker build -t datasift:latest -f docker/Dockerfile .
```

2. **Create Work Pool:**

```bash
prefect work-pool create datasift-docker-pool --type docker
```

3. **Start Workers:**

```bash
# Using Docker Compose
docker-compose -f docker/docker-compose.worker.yml up -d

# Or manually
docker run -d \
  -v datasift-batches:/app/data/batches \
  datasift:latest \
  prefect worker start --pool datasift-docker-pool
```

4. **Execute Flow:**

```bash
datasift-orchestrator --flow-file my-flow.json
```

**Docker Compose Example:**

```yaml
version: "3.8"
services:
  worker:
    image: datasift:latest
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

---

### 4. Production Distributed Kubernetes / OpenShift (WorkPoolAdapter + Kubernetes / OpenShift)

**Use Case:** Enterprise-scale deployments with auto-scaling and high availability

**Architecture:**

```mermaid
graph TB
    subgraph "Control Plane"
        FE[FlowExecutor]
        PE[PrefectEngine]
        WPA[WorkPoolAdapter]
        PS[Prefect Server]
    end

    subgraph "Kubernetes / OpenShift Cluster"
        subgraph "Shared Storage"
            PVC[PersistentVolumeClaim<br/>Batch Storage]
        end

        subgraph "Worker Pods"
            POD1[Worker Pod 1]
            POD2[Worker Pod 2]
            POD3[Worker Pod 3]
            PODN[Worker Pod N]
        end

        HPA[HorizontalPodAutoscaler]
    end

    FE --> PE
    PE --> WPA
    WPA --> PS
    PS --> POD1
    PS --> POD2
    PS --> POD3
    PS --> PODN

    HPA -.->|Scale| Worker Pods

    WPA -.->|Write Batches| PVC
    POD1 -.->|Read/Write| PVC
    POD2 -.->|Read/Write| PVC
    POD3 -.->|Read/Write| PVC
    PODN -.->|Read/Write| PVC

    style FE fill:#e1f5ff
    style WPA fill:#e1ffe1
    style PS fill:#fff4e1
    style PVC fill:#ffe1e1
```

**Configuration:**

```json
{
  "work_pool": {
    "enabled": true,
    "type": "kubernetes",
    "name": "datasift-k8s-pool",
    "namespace": "datasift-production",
    "image": "myregistry.io/datasift:v1.0.0",
    "batch_storage": {
      "type": "local",
      "base_path": "/shared/batches"
    }
  }
}
```

**Characteristics:**

- Enterprise-grade orchestration
- Auto-scaling based on workload
- High availability and fault tolerance
- Resource isolation and limits
- Multi-tenant support
- Rolling updates and rollbacks

**Setup:**

1. **Create Namespace:**

```bash
kubectl create namespace datasift-production
```

2. **Deploy Persistent Volume:**

```bash
kubectl apply -f k8s-deployment-examples/persistent-volume.yaml
```

3. **Create Work Pool:**

```bash
prefect work-pool create datasift-k8s-pool --type kubernetes
```

4. **Deploy Workers:**

```bash
kubectl apply -f k8s-deployment-examples/prefect-worker.yaml
```

5. **Execute Flow:**

```bash
datasift-orchestrator --flow-file my-flow.json
```

**Kubernetes / OpenShift Manifests:**

See `k8s-deployment-examples/` directory for complete manifests:

- `persistent-volume.yaml`: Shared storage for batches
- `prefect-worker.yaml`: Worker deployment with auto-scaling
- `configmap.yaml`: Configuration management
- `secrets.yaml`: Credentials management

**Resource Requirements:**

- **CPU**: 2-4 cores per worker pod
- **Memory**: 4-8 GB per worker pod
- **Storage**: 50-100 GB shared PVC for batch storage

---

### Deployment Pattern Comparison

| Pattern                    | Complexity | Scalability    | Cost    | Use Case               |
| -------------------------- | ---------- | -------------- | ------- | ---------------------- |
| **Thread Pool**            | Low        | Single machine | Minimal | Development, testing   |
| **Process Pool**           | Low        | Single machine | Low     | Single-node production |
| **Docker**                 | Medium     | Horizontal     | Medium  | Multi-host deployments |
| **Kubernetes / OpenShift** | High       | Auto-scaling   | Higher  | Enterprise production  |

### Choosing a Deployment Pattern

**Use Thread Pool when:**

- Developing and testing flows
- Processing small datasets (<1000 documents)
- Running on a laptop or workstation
- I/O-bound operations dominate

**Use Process Pool when:**

- Running CPU-intensive operations
- Single powerful machine available
- Simple deployment preferred
- Dataset fits on one machine

**Use Docker when:**

- Need containerized deployments
- Scaling across multiple hosts
- Consistent runtime environment required
- Docker infrastructure already available

**Use Kubernetes / OpenShift when:**

- Enterprise-scale deployments
- Auto-scaling required
- High availability needed
- Multi-tenant environments
- Advanced orchestration features required

---

## Design Decisions

### 1. Why PyArrow Tables?

**Decision:** Use PyArrow as the primary data interchange format.

**Rationale:**

| Aspect                 | Benefit                                                        |
| ---------------------- | -------------------------------------------------------------- |
| **Memory Efficiency**  | Columnar format reduces memory footprint by 50-70%             |
| **Performance**        | Zero-copy reads, fast serialization (10-100x faster than JSON) |
| **Interoperability**   | Works with Pandas, Polars, DuckDB, Spark                       |
| **Schema Enforcement** | Strong typing prevents data quality issues                     |
| **Scalability**        | Handles datasets from KB to TB efficiently                     |
| **Parquet Support**    | Native integration with Parquet file format                    |

### 2. Why Prefect for Orchestration?

**Decision:** Use Prefect as the workflow orchestration engine.

**Rationale:**

| Feature                | Benefit                                        |
| ---------------------- | ---------------------------------------------- |
| **DAG Support**        | Native directed acyclic graph execution        |
| **Parallel Execution** | Automatic parallelization of independent tasks |
| **Error Handling**     | Built-in retry logic and error recovery        |
| **Monitoring**         | Real-time execution monitoring and logging     |
| **Python-Native**      | Pure Python, no external DSL required          |
| **Local Execution**    | Runs locally without external infrastructure   |

### 3. Why Operator-Based Architecture?

**Decision:** Build the framework around composable operators.

**Rationale:**

| Principle           | Benefit                                         |
| ------------------- | ----------------------------------------------- |
| **Modularity**      | Each operator is self-contained and testable    |
| **Reusability**     | Operators can be reused across different flows  |
| **Extensibility**   | Easy to add new operators without changing core |
| **Composability**   | Complex pipelines built from simple operators   |
| **Maintainability** | Changes isolated to individual operators        |
| **Testability**     | Unit test operators independently               |

**Design Pattern:** Template Method + Strategy Pattern

### 4. Extensibility Considerations

**Design for Extension:**

1. **Abstract Base Classes**: Clear contracts for new operators
2. **Factory Pattern**: Centralized operator instantiation
3. **Configuration-Driven**: Operators configured via JSON
4. **Hexagonal Architecture**: External services via adapters
5. **Plugin Discovery**: Automatic operator registration

**Extension Points:**

```mermaid
graph TD
    EXT[Extension Points]
    EXT --> OP[New Operators]
    EXT --> ADAPT[New Adapters]
    EXT --> ORCH[Custom Orchestrators]
    EXT --> VAL[Custom Validators]

    OP --> IMPL1[Inherit AbstractOperator]
    OP --> IMPL2[Implement transform]
    OP --> IMPL3[Register in factory]

    ADAPT --> IMPL4[Implement adapter interface]
    ADAPT --> IMPL5[Register in VectorDBOperator]

    style EXT fill:#e1f5ff
    style OP fill:#ffe1e1
    style ADAPT fill:#fff4e1
```

**Example: Adding a New Operator**

```python
from core.operators.abstract_operator import AbstractOperator, OperatorCategory

class MyCustomOperator(AbstractOperator):
    short_name = "my_custom"
    category = OperatorCategory.Functional

    def __init__(self, config: dict):
        super().__init__(config)
        self.custom_param = config.get("custom_param")

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        # Implementation
        metadata = self.create_base_metadata(total_docs_count=len(table))
        # Process table
        return [output_table], metadata
    @staticmethod
    def get_required_features() -> list[str]:

        return ["doc_id", "content"]
```

### Schema Evolution

```mermaid
graph LR
    S1[Initial Schema] --> S2[After Extract]
    S2 --> S3[After Chunk]
    S3 --> S4[After Embed]

    S1 -.->|doc_id, doc_name,<br/>file_path| S1
    S2 -.->|+ content, tables,<br/>metadata| S2
    S3 -.->|+ chunks, chunk_ids| S3
    S4 -.->|+ embeddings| S4

    style S1 fill:#ffe1e1
    style S2 fill:#fff4e1
    style S3 fill:#e1ffe1
    style S4 fill:#e1f5ff
```

**Schema Transformation Example:**

**After Ingest:**

```
doc_id: string
doc_name: string
file_path: string
file_size: int64
```

**After Extract:**

```
doc_id: string
doc_name: string
file_path: string
file_size: int64
content: string          # NEW
tables: list<struct>     # NEW
metadata: struct         # NEW
```

**After Chunk:**

```
doc_id: string
doc_name: string
content: string
chunk_id: string         # NEW
chunk_text: string       # NEW
chunk_index: int32       # NEW
```

**After Embed:**

```
doc_id: string
doc_name: string
chunk_id: string
chunk_text: string
embeddings: list<float>  # NEW
```

---

**Why PyArrow?**

- **Memory Efficiency**: Columnar format with zero-copy reads
- **Interoperability**: Standard format across data tools (Pandas, Polars, DuckDB)
- **Performance**: Fast serialization/deserialization
- **Schema Enforcement**: Strong typing with schema validation
- **Scalability**: Handles large datasets efficiently
- **Parquet Integration**: Native support for Parquet file format

**Data Flow Pattern:**

```
Operator Input (PyArrow Table)
    → Processing Logic
    → Operator Output (PyArrow Table)
```

---

- Perform entity extraction, semantic chunking, and embedding generation at scale

## Repository Structure

```
datasift/
├── src/datasift_opensource/          # Main source code
│   ├── backend/                      # Backend components
│   │   ├── app/                      # Backend API application
│   │   │   ├── routes/               # API route handlers
│   │   │   │   ├── flows.py          # Flow management endpoints
│   │   │   │   └── job_runs.py       # Job run management endpoints
│   │   │   ├── dependencies.py       # Dependency injection providers
│   │   │   └── main.py               # FastAPI application
│   │   ├── cli/                      # CLI implementation
│   │   ├── common/                   # Shared utilities and models
│   │   │   ├── clients/              # LLM client abstractions
│   │   │   ├── constants/            # Constants and enums
│   │   │   ├── document_classes/     # 40+ document class schemas
│   │   │   ├── exceptions/           # Exception hierarchy with error codes
│   │   │   ├── models/               # Data models
│   │   │   └── util/                 # Utility functions
│   │   │       ├── core/             # Core utilities (strings, validation, etc.)
│   │   │       ├── data/             # Data handling utilities
│   │   │       ├── infrastructure/   # Infrastructure utilities
│   │   │       ├── job_tracker/      # Legacy job tracking (reference only)
│   │   │       ├── operators/        # Operator utilities
│   │   │       └── orchestration/    # Orchestration utilities
│   │   ├── core/                     # Core orchestration framework
│   │   │   ├── data_access/          # Data access abstractions
│   │   │   ├── job_management/       # Job statistics and management (hexagonal)
│   │   │   │   ├── domain/           # Domain models and ports
│   │   │   │   ├── application/      # Application services
│   │   │   │   └── adapters/         # Infrastructure adapters
│   │   │   ├── operators/            # Operator implementations
│   │   │   │   ├── extract/          # Extract operators
│   │   │   │   ├── functional/       # Functional operators
│   │   │   │   ├── ingest/           # Ingest operators
│   │   │   │   ├── quality/          # Quality/filtering operators
│   │   │   │   └── vectordb/         # Vector database operators
│   │   │   └── orchestrator/         # Orchestration components
│   │   │       ├── cmdline/          # Command-line executor
│   │   │       ├── prefect/          # Prefect orchestration module
│   │   │       │   ├── adapters/     # Batch execution adapters
│   │   │       │   ├── config/       # Work pool configuration
│   │   │       │   ├── domain/       # Domain models
│   │   │       │   └── ports/        # Batch execution port
│   │   │       └── python/           # Python orchestrator
│   │   └── models/                   # ML models (FastText, etc.)
│   └── ui/                           # User interface components
├── tests/                            # Test suites
│   ├── unit/                         # Unit tests
│   ├── integration/                  # Integration tests
│   └── fixtures/                     # Test fixtures
├── docs/                             # Documentation
├── examples/                         # Example flows and configurations
└── pyproject.toml                    # Project configuration
```

## Core Components

### 1. Core Utilities (`src/datasift/utils/` and `src/datasift/core/`)

#### Clients (`common/clients/`)

- **LLM Client Abstractions**: Base interfaces for LLM providers
- **Ollama Client**: Integration with Ollama for local LLM operations
- **LiteLLM Client**: Multi-provider LLM support
- **HuggingFace Client**: HuggingFace model integration
- **DoclingServeClient**: REST API client for Docling Serve document processing

#### Exceptions (`common/exceptions/`)

- **Structured Exception Hierarchy**: Comprehensive error handling
- **Error Codes**: Standardized error code system
- **Error Messages**: Centralized error message management

#### Document Classes (`common/document_classes/`)

### 5. Storage Layer (`src/datasift/storage/`)

The storage layer provides a clean, interface-based abstraction for data persistence in datasift. It follows a port-adapter pattern with two primary interfaces for different storage needs.

#### Storage Interfaces

**KeyValueStorage Interface** (`interfaces/key_value_storage.py`)

- Interface for storing JSON-serializable records in logical collections
- Used for asset metadata (flows, document set metadata)
- Operations: save_record, get_record, list_records, delete_record, collection_exists, record_exists
- Implementations:
  - **FileSystemStorage**: JSON files organized by collection directories
  - **DuckDBKeyValueStorage**: DuckDB tables with JSON columns

**TableStorage Interface** (`interfaces/table_storage.py`)

- Interface for PyArrow table storage with SQL query capabilities
- Used for document set data and structured data operations
- Operations: create_table, upsert_data, read_data, delete_table, table_exists, get_row_count, execute_query
- Implementations:
  - **DuckDBTableStorage**: DuckDB-based PyArrow table storage with schema evolution

#### Storage Factory

**StorageFactory** (`factory.py`)

- Factory pattern for creating storage instances
- Methods:
  - `create_key_value_storage(storage_type, **config)`: Creates KeyValueStorage instances
  - `create_table_storage(storage_type, **config)`: Creates TableStorage instances
- Supported types:
  - Key-value: "filesystem", "duckdb"
  - Table: "duckdb"
- Validates storage types and provides clear error messages

#### DuckDB Implementations

**DuckDBKeyValueStorage** (`duck_db/key_value_storage.py`)

- Stores records as JSON in DuckDB tables (one table per collection)
- Schema: `key TEXT PRIMARY KEY, data JSON`
- Singleton pattern per database path for connection reuse
- Features: JSON serialization, SQL-based filtering, atomic operations

**DuckDBTableStorage** (`duck_db/table_storage.py`)

- Stores PyArrow tables directly in DuckDB
- Features:
  - Schema evolution support (automatic column addition)
  - Atomic upsert operations with row count verification
  - SQL query execution with parameterization
  - Metrics computation (row counts, aggregations)
  - Connection pooling and singleton pattern

#### FileSystem Implementation

**FileSystemStorage** (`file_system/key_value_storage.py`)

- Stores records as JSON files in directory structure
- Directory layout: `base_dir/collection/key.json`
- Features: Atomic writes, file locking, directory creation
- Suitable for development and small-scale deployments

#### Storage Exceptions

- **StorageException**: Base exception for storage errors
- **StorageNotFoundError**: Record or table not found
- **StorageValidationError**: Invalid parameters or data
- **StorageConnectionError**: Database connection failures

### 6. Assets Management (`src/datasift/core/assets/`)

The assets management layer provides hexagonal architecture implementations for managing data assets like flows and document sets. It follows clean architecture principles with clear separation between domain, application, and adapter layers.

#### Flows (`assets/flows/`)

Hexagonal architecture implementation for flow management:

**Domain Layer** (`domain/models/`):

- **Flow**: Core entity representing pipeline definitions
- **FlowMetadata**: Flow metadata and configuration
- **FlowRepository (Port)**: Interface for flow persistence

**Application Layer** (`application/services/`):

- **FlowService**: Business logic for flow operations
  - Flow creation, retrieval, updates, and deletion
  - Flow validation and configuration management

**Adapter Layer** (`adapters/repositories/`):

- **StorageFlowRepository**: Generic repository using KeyValueStorage interface
  - Works with any storage backend (DuckDB, filesystem)
  - Stores flows in 'flows' collection with flow_id as key
  - Exception wrapping with FlowNotFoundException, FlowStorageException

#### Document Sets (`assets/document_sets/`)

Hexagonal architecture implementation for document set management:

**Domain Layer** (`domain/models/`):

- **DocumentSet**: Core entity for named document collections
- **StorageReference**: Physical storage location metadata
- **DataCard**: Lineage and provenance tracking

**Domain Ports** (`domain/ports/`):

- **DocumentSetMetadataRepository**: Interface for metadata persistence
- **DocumentSetDataStore**: Interface for PyArrow table data operations

**Application Layer** (`application/services/`):

- **DocumentSetService**: Business logic orchestration
  - Idempotent create-or-get operations
  - Metrics computation and updates
  - Data storage coordination
  - Independent of concrete storage implementation

**Adapter Layer** (`adapters/`):

- **DuckDB Adapters** (`adapters/duckdb/`):
  - **DuckDBDocumentSetMetadataRepository**: Metadata persistence using KeyValueStorage
  - **DuckDBDocumentSetDataStore**: Data persistence using TableStorage
  - Registered via factory decorators for automatic discovery

**Factory Layer** (`factories/`):

- **MetadataRepositoryFactory**: Creates metadata repository adapters
- **DataStoreFactory**: Creates data store adapters
- Decorator-based registration system
- Validates adapter configuration before instantiation

**Predefined Schemas**:

- 40+ JSON schemas for common document types
- Insurance forms, bank statements, legal documents, etc.

- **Core Utilities**: String manipulation, validation, patterns
- **Data Utilities**: PyArrow handling, schema management, transformations
- **Infrastructure Utilities**: Logging, caching, retry logic, performance monitoring, IAM token management
- **Job Tracker**: Job statistics and monitoring
- **Orchestration Utilities**: Flow utilities, Prefect configuration, deleted rows tracking

##### IAM Token Manager

**Location**: `src/datasift/utils/infrastructure/iam_token_manager.py`

The IAM Token Manager handles IBM Cloud and MCSP (Multi-Cloud Service Platform) authentication for WatsonX integrations. It provides automatic token management with caching, refresh, and multi-environment support.

**Key Features**:
- **Multi-Environment Support**: Automatically detects and handles IBM Cloud, MCSP Production, and MCSP Test environments
- **Automatic Environment Detection**: Determines environment from WatsonX URL patterns
- **Token Caching**: Uses LRUCache for efficient token storage with 1-hour TTL
- **Auto-Refresh**: Refreshes tokens 10 minutes before expiration
- **Thread-Safe**: Built on thread-safe LRUCache implementation
- **Multi-Tenant Support**: API key-based cache keys enable multiple tenants

**Environment Detection**:

| Environment | URL Pattern | IAM Endpoint |
|-------------|-------------|--------------|
| MCSP Production | Contains `.aws.` or `platform.saas.ibm.com` | `https://account-iam.platform.saas.ibm.com/api/2.0/apikeys/token` |
| MCSP Test | Contains `.test.` and `platform.saas.ibm.com` | `https://account-iam.platform.test.saas.ibm.com/api/2.0/apikeys/token` |
| IBM Cloud | All other URLs (default) | `https://iam.cloud.ibm.com/identity/token` |

**Architecture**:
```
WatsonX REST Client
        ↓
IAMTokenManager
  - Environment detection
  - Token caching (LRUCache)
  - Auto-refresh (10 min buffer)
        ↓
IAM Endpoints (IBM Cloud/MCSP)
```

**Usage Example**:
```python
from datasift.utils.infrastructure.iam_token_manager import IAMTokenManager

# Initialize with API key and WatsonX URL
token_manager = IAMTokenManager(
    api_key="your-api-key",  # pragma: allowlist secret
    watsonx_url="https://us-south.ml.cloud.ibm.com"
)

# Get valid token (automatically cached and refreshed)
token = token_manager.get_token()
```

**Integration with WatsonX**: The WatsonX REST client automatically uses IAM Token Manager for authentication. Users only need to provide their API key and URL - token management is handled transparently.

**IBM Cloud vs MCSP Differences**:
- **IBM Cloud**: Uses form-urlencoded requests, returns `access_token` field
- **MCSP**: Uses JSON requests, returns `token` field
- Both support automatic token refresh with 1-hour expiration

**See Also**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md#iam-authentication-issues) for authentication troubleshooting

### 2. Core Framework (`src/datasift/core/`)

#### Orchestrator (`core/orchestrator/`)

- **AbstractOrchestrator**: Base interface for all orchestrators
- **PythonOrchestrator**: Programmatic flow execution
- **OrchestratorFactory**: Factory for orchestrator instantiation
- **FlowExecutor**: Flow execution coordination
- **FlowValidator**: Comprehensive flow validation (520+ lines)
- **PrefectEngine**: Prefect-based workflow execution engine
- **BatchManager**: Batch processing coordination
- **AbstractOperatorExecutor**: Base executor interface
- **CommandLineOperatorExecutor**: CLI execution support
- **PythonOperatorExecutor**: Python execution support
- **Event Handling**: `AbstractFlowExecutionEventHandler`, `FlowExecutionEventHandler`
- **NodeLogger**: Node-level logging
- **FuturedList**: Async result handling

**Prefect Module** (`prefect/`):

- **PrefectEngine**: Main Prefect workflow execution engine
- **BatchSubflow**: Standalone batch execution subflow
- **BatchExecutionPort**: Port interface for batch execution strategies
- **ThreadPoolAdapter**: Local thread-based batch execution
- **WorkPoolAdapter**: Distributed batch execution via Prefect work pools
- **WorkPoolConfig**: Configuration for Docker and Kubernetes / OpenShift work pools
- **Domain Models**: Batch execution domain models and constants

#### Operators (`core/operators/`)

- **AbstractOperator**: Base operator class with template method pattern
- **OperatorMetadata**: Operator metadata and discovery
- **OperatorUtils**: Operator utility functions

#### Data Access (`core/data_access/`)

- Data access utilities and abstractions
- Storage management interfaces
#### Assets Management (`core/assets_management/`)

The Assets Management module provides metadata management for document collections using hexagonal architecture (ports & adapters pattern). It stores only metadata in DuckDB, not document content.

**Document Libraries** (`document_libraries/`):
- **Domain Layer** (`domain/`):
  - **DocumentLibrary**: Domain model representing a collection of document sets
    - Attributes: library_id, name, description, tags, document_set_ids, aggregate metrics
    - Methods: create(), validate(), add_document_set(), remove_document_set(), update_aggregate_metrics()
    - Validation: Name (3-100 chars), description (max 500 chars), tags (max 20, each 1-50 chars)
  - **DocumentLibraryRepositoryPort**: Repository interface defining persistence contract
  - **Exceptions**: DocumentLibraryNotFoundError, DocumentLibraryAlreadyExistsError, InvalidDocumentLibraryError

- **Adapters Layer** (`adapters/`):
  - **DuckDBDocumentLibraryStorage**: DuckDB storage implementation (metadata only)
    - Tables: `document_libraries` (metadata), `library_documentset_junction` (many-to-many relationships)
    - Schema: library_id (UUID), name, description, tags (JSON), created_at, updated_at, aggregate_metrics (JSON)
  - **DuckDBDocumentLibraryMetadataRepository**: Repository implementation using DuckDB storage (metadata only)
    - CRUD operations: create(), get_by_id(), get_by_name(), list_all(), update(), delete()
    - Relationship management: add_document_set(), remove_document_set(), get_document_sets()
    - Filtering: list_by_tags(), search_by_name()

- **Application Layer** (`application/services/`):
  - **DocumentLibraryService**: Business logic orchestration
    - Library lifecycle: create_library(), get_library(), update_library(), delete_library()
    - Document set management: add_document_set_to_library(), remove_document_set_from_library()
    - Queries: list_libraries(), get_library_document_sets(), search_libraries()
    - Validation: Ensures business rules and constraints

- **API Layer** (`app/api/document_libraries/`):
  - **DTOs**: Pydantic models for request/response (CreateLibraryRequest, LibraryResponse, etc.)
  - **Mapper**: Converts between domain models and DTOs
  - **Routes**: FastAPI endpoints for library operations
    - POST /api/v1/document-libraries - Create library
    - GET /api/v1/document-libraries/{library_id} - Get library
    - PUT /api/v1/document-libraries/{library_id} - Update library
    - DELETE /api/v1/document-libraries/{library_id} - Delete library
    - POST /api/v1/document-libraries/{library_id}/document-sets/{set_id} - Add document set
    - DELETE /api/v1/document-libraries/{library_id}/document-sets/{set_id} - Remove document set
    - GET /api/v1/document-libraries - List all libraries
    - GET /api/v1/document-libraries/search - Search libraries

**Architecture Benefits**:
- **Separation of Concerns**: Domain logic isolated from infrastructure
- **Testability**: Easy to mock repositories and test business logic
- **Flexibility**: Can swap DuckDB for PostgreSQL/MongoDB without changing domain
- **Maintainability**: Clear boundaries between layers


### 3. Operators (`src/datasift/core/operators/`)

Operators are organized by category (defined in `OperatorCategory` enum):

#### Extract Operators (`extract/`)

- **ExtractOperator**: Extraction operator using hexagonal architecture with multiple adapters; outputs extracted text plus estimated page-count metrics
  - **Text Extraction Modes**:
    - `docling_library`: Local Docling extraction with optional VLM (Vision-Language Model) and ASR (Automatic Speech Recognition) pipelines
    - `docling_serve`: Remote extraction via Docling Serve API with OCR support
  - **Entity Extraction Modes**:
    - `ollama`: LLM-based entity extraction using Ollama models
    - `docling`: Template-based entity extraction using Docling templates
    - `litellm`: Multi-provider LLM extraction (OpenAI, Anthropic, Cohere, etc.)
    - `watsonx`: IBM watsonx.ai entity extraction using Granite and other hosted models
    - `none`: No entity extraction (default)
  - **Adapters**: DoclingAdapter, DoclingServeAdapter (text); OllamaEntityAdapter, DoclingEntityAdapter, LiteLLMEntityAdapter, WatsonxEntityAdapter (entity)
  - **Configuration**: Supports both text and entity extraction in a single operator with independent mode selection

#### Ingest Operators (`ingest/`)

- **IngestLocalOperator**: Local filesystem ingestion
- **IngestSourceOperator**: Multi-provider data ingestion (object storage, IBM COS, SharePoint, OneDrive, Google Drive, web pages, custom loaders)

#### Functional Operators (`functional/`)

- **BranchingOperator**: Conditional workflow branching
- **MergeOperator**: Combine multiple tables from branches using row concatenation or column joins
- **Chunker**: Document chunking with multiple strategies:
  - **Simple**: Basic text splitting with configurable chunk size and overlap
  - **Semantic**: Sentence-based chunking using NLTK
  - **Hybrid**: Advanced chunking using Docling library
    - Supports both local execution (`docling_library` provider) and remote execution via docling-serve API (`docling_serve` provider) for offloading computation
- **DocIdHash**: Document ID generation (internal operator)
- **EntityCurationOperator**: Schema-based entity transformation with 9 built-in transformations (currency, date, number parsing)
- **NoopOperator**: Pass-through for testing
- **EmbeddingsOperator**: Vector embedding generation

#### Quality Operators (`quality/`)

- **DocumentClassifier**: LLM-based document classification (simplified service-based architecture with LiteLLM and Watsonx.ai support via shared LLM infrastructure)
- **Dedup**: Deduplication
- **DocQuality**: Document quality assessment using dpk_doc_quality (word count, mean word length, symbol ratios, bad words, etc.)
- **MLEnrichment**: ML-based enrichment
- **Readability**: Readability scoring
- **Redaction**: PII redaction
- **SQLFilter**: SQL-based filtering
- **LanguageDetection**: Language identification (hexagonal architecture with FastText adapter)
- **PIIAndHAPAnnotator**: PII and HAP detection (hexagonal architecture with Ollama, WatsonX, and LiteLLM adapters)

#### VectorDB Operators (`vectordb/`)

- **VectorDBOperator**: Generic vector database operator using hexagonal architecture (ports & adapters)
  - Supports multiple vector databases through adapter pattern
  - **OpenSearch Adapter**: OpenSearch vector storage and retrieval with multiple KNN engines (NMSLIB, Faiss, Lucene)
  - **Milvus Adapter**: Milvus vector storage supporting both standalone and wx.data deployments with multiple index types (HNSW, IVF_FLAT, FLAT, etc.)

#### Storage Operators (`storage/`)

- **DocumentSetOperator**: Persistent storage operator for pipeline data using document sets
  - Stores PyArrow table data with DuckDB backend
  - Automatic schema evolution and metrics computation
  - Incremental updates with soft-delete cleanup support
  - Pass-through design for downstream operator chaining
  - Hexagonal architecture with service/repository/storage layers

### 4. CLI Application (`src/datasift/cli/`)

- **datasift_cli.py**: Command-line interface implementation
- Uses `PythonOrchestrator` via `OrchestratorFactory`
- Supports flow execution from JSON files

## Key Features

1. **Lightweight Deployment**: Runs locally
2. **Python-Based Execution**: Pure Python operator implementations
3. **Plugin System**: Extensible with custom operators
4. **Flow Configuration**: JSON-based flow definitions
5. **Local Data Processing**: File system and local storage support
6. **Distributed Execution**: Support for scaling across multiple workers using Prefect work pools (Docker, Kubernetes / OpenShift)

## Operator Pattern

Each operator follows a consistent pattern:

- Inherits from `AbstractOperator`
- Implements `transform()` method
- Configurable via JSON
- Chainable in flows

## Orchestrator Architecture

```
AbstractOrchestrator (base interface)
└── PythonOrchestrator (single implementation)
    └── Used by CLI via OrchestratorFactory

Supporting Components:
├── FlowExecutor (coordinates flow execution)
├── FlowValidator (validates flow configuration)
├── PrefectEngine (Prefect workflow engine)
│   ├── BatchExecutionPort (strategy interface)
│   │   ├── ThreadPoolAdapter (local execution)
│   │   └── WorkPoolAdapter (distributed execution)
│   └── BatchSubflow (worker-side batch processing)
├── BatchManager (batch processing)
├── OperatorFactory (operator instantiation)
└── Event Handlers (execution monitoring)
```

**Note**: There is no separate `CommandLineOrchestrator` class. The CLI uses `PythonOrchestrator` through the factory pattern.

### 5. REST API (`src/datasift/app/`)

The FastAPI-based REST API provides programmatic access to flow and job management:

#### Flow Management Endpoints (`/api/v1/flows`)

- `POST /flows` - Create a new flow
- `GET /flows/{flow_id}` - Retrieve flow by ID
- `GET /flows` - List flows with pagination and filtering
- `PUT /flows/{flow_id}` - Update flow (full replacement)
- `PATCH /flows/{flow_id}` - Partial flow update
- `DELETE /flows/{flow_id}` - Delete flow
- `DELETE /flows` - Bulk delete flows

#### Job Run Management Endpoints (`/api/v1/job-runs`)

- `GET /job-runs/{job_run_id}` - Get job run status and statistics
- `POST /job-runs/{job_run_id}/cancel` - Request job cancellation
- `DELETE /job-runs/{job_run_id}` - Delete job run data

#### Job Management Architecture

The job management subsystem uses hexagonal architecture (ports and adapters pattern):

- **Domain Layer**: `JobStatsDto`, `NodeStatsDto` models and `JobStatsService` port
- **Application Layer**: `JobManagementService` for orchestrating job operations
- **Adapters Layer**: Multiple storage implementations with pluggable backends
  - `InMemoryJobStatsStore`: Fast in-memory storage for testing/development
  - `JsonJobStatsStore`: JSON file-based storage for restart recovery and inspection
  - `CompositeJobStatsStore`: Write-through composite (memory + persistent) for fast reads with durability
- **Dependency Injection**: Factory pattern via `JobManagementFactory`

This architecture enables:

- Pluggable storage backends (in-memory, JSON, composite, PostgreSQL, Redis, etc.)
- Framework-agnostic job tracking
- Clean separation between business logic and infrastructure
- Restart recovery with JSON persistence
- Write-through caching for optimal performance

## Development Guidelines

1. **Python orchestration**: Entire orchestration using Python and Prefect
2. **Python-Only Operators**: Implement operators in pure Python
3. **Modular Design**: Keep components loosely coupled
4. **Plugin Support**: Design for extensibility
5. **Local Testing**: All features should work locally

## Testing Strategy

- **Unit Tests**: Test individual operators and components
- **Integration Tests**: Test flow execution end-to-end
- **Fixtures**: Reusable test data and configurations
- **Coverage**: Maintain >80% code coverage

## Documentation

- **User Guide**: How to use the CLI and create flows
- **Developer Guide**: How to create custom operators
- **API Reference**: Detailed API documentation
- **Examples**: Sample flows and use cases

## Future Enhancements

- Additional operator types
- Enhanced plugin system
- Performance optimizations
- Enhanced work pool types
- Auto-scaling based on workload
- Web UI for flow management
