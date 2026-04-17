# Datasift-Open Architecture

This document describes the architecture and organization of the datasift-open repository.

## Overview

Datasift-open is a modular, operator-based data processing framework designed for building flexible document curation pipelines. It enables advanced RAG (Retrieval-Augmented Generation) workflows by combining structured data extraction, semantic chunking, vector embeddings, and hybrid search capabilities. It uses a mixed architecture approach comprising of dynamic plugin discovery across operators, hexagonal architecture in subsystems that need interchangeable external services. 

### Key Capabilities

- **Operator-Based Architecture**: 17+ specialized operators organized into categories (ingest, extract, chunk, embed, vectordb, filter, branching and merging, utility, and language processing)
- **PyArrow Data Format**: All data flows through the pipeline as PyArrow tables, ensuring efficient memory usage and interoperability
- **DAG-Based Workflow Execution**: Flows are defined as JSON configurations representing directed acyclic graphs (DAGs) of operator nodes
- **Prefect Orchestration**: Workflow execution managed by Prefect with support for both ephemeral (local) and distributed execution via work pools (Docker, Kubernetes)
- **Modern AI/ML Integrations**: Native support for Ollama (LLM operations), Docling (document processing), and OpenSearch (vector and scalar storage)

### Architectural Patterns

Datasift-opensource intentionally employs a **mixed architectural approach** rather than adhering to a single dominant pattern. This diversity enables flexibility, modularity, and maintainability across different system layers:

- **Hexagonal Architecture (Ports & Adapters)**: Core domain logic and operator abstractions are isolated from external dependencies, allowing operators to be framework-agnostic and easily testable. The Prefect orchestration module specifically uses hexagonal architecture with ports and adapters for batch execution strategies, enabling seamless switching between local and distributed execution modes.
- **Factory Pattern**: `OrchestratorFactory` and `OperatorFactory` provide centralized instantiation logic for orchestrators and operators
- **Strategy Pattern**: Different operator implementations can be swapped based on configuration without changing the orchestration logic
- **Observer Pattern**: Event handling system (`AbstractFlowExecutionEventHandler`, `FlowExecutionEventHandler`) enables monitoring and logging of flow execution
- **Template Method Pattern**: `AbstractOperator` defines the execution flow template while concrete operators implement specific behavior

This architectural diversity is a deliberate design choice that supports the framework's goal of being extensible, testable, and adaptable to various data processing scenarios.

### Use Cases

- Extract structured information from tables within unstructured documents (PDFs, DOCX, etc.)
- Combine vector similarity search with structured data filtering for improved retrieval accuracy
- Build custom document processing pipelines with configurable operators
- Perform entity extraction, semantic chunking, and embedding generation at scale

## Repository Structure

```
datasift-opensource/
├── src/datasift_opensource/          # Main source code
│   ├── backend/                      # Backend components
│   │   ├── app/                      # Backend API application
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
│   │   │       ├── job_tracker/      # Job tracking and statistics
│   │   │       ├── operators/        # Operator utilities
│   │   │       └── orchestration/    # Orchestration utilities
│   │   ├── core/                     # Core orchestration framework
│   │   │   ├── data_access/          # Data access abstractions
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

### 1. Common Utilities (`src/datasift_opensource/backend/common/`)

#### Clients (`common/clients/`)
- **LLM Client Abstractions**: Base interfaces for LLM providers
- **Ollama Client**: Integration with Ollama for local LLM operations
- **LiteLLM Client**: Multi-provider LLM support
- **HuggingFace Client**: HuggingFace model integration
- **Docling Serve Client**: Document processing via Docling

#### Exceptions (`common/exceptions/`)
- **Structured Exception Hierarchy**: Comprehensive error handling
- **Error Codes**: Standardized error code system
- **Error Messages**: Centralized error message management

#### Document Classes (`common/document_classes/`)
- **40+ Predefined Schemas**: JSON schemas for common document types
- **Insurance Forms, Bank Statements, Legal Documents, etc.**

#### Utilities (`common/util/`)
- **Core Utilities**: String manipulation, validation, patterns
- **Data Utilities**: PyArrow handling, schema management, transformations
- **Infrastructure Utilities**: Logging, caching, retry logic, performance monitoring
- **Job Tracker**: Job statistics and monitoring
- **Orchestration Utilities**: Flow utilities, Prefect configuration, deleted rows tracking

### 2. Core Framework (`src/datasift_opensource/backend/core/`)

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
- **WorkPoolConfig**: Configuration for Docker and Kubernetes work pools
- **Domain Models**: Batch execution domain models and constants

#### Operators (`core/operators/`)
- **AbstractOperator**: Base operator class with template method pattern
- **OperatorMetadata**: Operator metadata and discovery
- **OperatorUtils**: Operator utility functions

#### Data Access (`core/data_access/`)
- Data access utilities and abstractions
- Storage management interfaces

### 3. Operators (`src/datasift_opensource/backend/core/operators/`)

Operators are organized by category (defined in `OperatorCategory` enum):

#### Extract Operators (`extract/`)
- **ExtractDocling**: Document content extraction using Docling
- **ExtractEntitiesOllama**: LLM-based entity extraction

#### Ingest Operators (`ingest/`)
- **IngestLocalFolder**: Local filesystem ingestion
- **IngestLocalS3**: S3-compatible storage ingestion
- **IngestCSV**: CSV file processing
- **IngestSource**: Multi-provider data ingestion

#### Functional Operators (`functional/`)
- **BranchingOperator**: Conditional workflow branching
- **Chunker**: Document chunking (Simple, Semantic, Hybrid/Docling)
- **DocIdHash**: Document ID generation (internal operator)
- **NoopOperator**: Pass-through for testing
- **EmbeddingsOperator**: Vector embedding generation

#### Quality Operators (`quality/`)
- **DocumentClassifier**: Document classification
- **Dedup**: Deduplication
- **MLEnrichment**: ML-based enrichment
- **Readability**: Readability scoring
- **Redaction**: PII redaction
- **SQLFilter**: SQL-based filtering
- **LanguageDetection**: Language identification

#### VectorDB Operators (`vectordb/`)
- **VectorDBOperator**: Generic vector database operator using hexagonal architecture (ports & adapters)
  - Supports multiple vector databases through adapter pattern
  - **OpenSearch Adapter**: OpenSearch vector storage and retrieval with multiple KNN engines

### 4. CLI Application (`src/datasift_opensource/backend/cli/`)
- **datasift_cli.py**: Command-line interface implementation
- Uses `PythonOrchestrator` via `OrchestratorFactory`
- Supports flow execution from JSON files

## Key Features

1. **Lightweight Deployment**: Runs locally
2. **Python-Based Execution**: Pure Python operator implementations
3. **Plugin System**: Extensible with custom operators
4. **Flow Configuration**: JSON-based flow definitions
5. **Local Data Processing**: File system and local storage support
6. **Distributed Execution**: Support for scaling across multiple workers using Prefect work pools (Docker, Kubernetes)

## Operator Pattern

Each operator follows a consistent pattern:
- Inherits from `AbstractOperator`
- Implements `execute()` method
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
- Enhanced work pool types (e.g., ECS, Cloud Run)
- Auto-scaling based on workload
- Web UI for flow management
