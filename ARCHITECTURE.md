# Datasift-Open Architecture

This document describes the architecture and organization of the datasift-open repository.

## Overview

Datasift-open is a modular, operator-based data processing framework designed for building flexible document curation pipelines. It enables advanced RAG (Retrieval-Augmented Generation) workflows by combining structured data extraction, semantic chunking, vector embeddings, and hybrid search capabilities.

### Key Capabilities

- **Operator-Based Architecture**: 17+ specialized operators organized into categories (ingest, extract, chunk, embed, vectordb, filter, branching and merging, utility, and language processing)
- **PyArrow Data Format**: All data flows through the pipeline as PyArrow tables, ensuring efficient memory usage and interoperability
- **DAG-Based Workflow Execution**: Flows are defined as JSON configurations representing directed acyclic graphs (DAGs) of operator nodes
- **Prefect Orchestration**: Workflow execution managed by Prefect for parallel processing and task dependency management
- **Modern AI/ML Integrations**: Native support for Ollama (LLM operations), Docling (document processing), and OpenSearch (vector and scalar storage)

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
│   │   ├── config/                   # Configuration management
│   │   ├── common/                   # Shared utilities and models
│   │   ├── core/                     # Core orchestration framework
│   │   │   ├── orchestrator/         # Orchestrator implementations
│   │   │   │   ├── cmdline/          # Command-line orchestrator
│   │   │   │   └── python/           # Python orchestrator
│   │   │   ├── data_access/          # Data access abstractions
│   │   │   ├── plugins/              # Plugin system
│   │   │   └── runtime_jobs/         # Runtime job execution
│   │   ├── operators/                # Python operator implementations
│   │   │   ├── language/             # Language processing operators
│   │   │   ├── transform/            # Data transformation operators
│   │   │   ├── validation/           # Data validation operators
│   │   │   ├── universal/            # Universal operators
│   │   │   └── custom/               # Custom operator support
│   │   ├── app/                      # Backend API application
│   │   └── orchestrator/             # Legacy orchestrator (to be migrated)
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

### 1. Configuration Management (`src/datasift_opensource/backend/config/`)
- Configuration loading and validation
- Environment-specific settings
- Configuration schemas and defaults

### 2. Common Utilities (`src/datasift_opensource/backend/common/`)
- Shared utility functions
- Common data models
- Exception classes
- Helper functions
- **Note:** Excludes Spark-specific utilities

### 3. Core Framework (`src/datasift_opensource/backend/core/`)

#### Orchestrator
- **Abstract Orchestrator**: Base interface for all orchestrators
- **Command-Line Orchestrator**: Execute flows from CLI
- **Python Orchestrator**: Programmatic flow execution
- **Flow Executor**: Flow execution logic
- **Operator Factory**: Operator instantiation

#### Operators
- **Abstract Operator**: Base operator class
- **Abstract Custom Operator**: Custom operator base class

#### Data Access
- Data access utilities and abstractions
- Storage management interfaces

#### Plugins
- Plugin loading and registration
- Custom operator discovery

#### Runtime Jobs
- Runtime flow execution
- Job management

### 4. Operators (`src/datasift_opensource/backend/operators/`)

Python-based operator implementations (non-Spark):

- **Language Operators**: Language detection, text analysis, NLP
- **Transform Operators**: Data mapping, format conversion, enrichment
- **Validation Operators**: Schema validation, data quality checks
- **Universal Operators**: Storage operations, generic transformations
- **Custom Operators**: User-defined operators, plugin-based extensions

### 5. CLI Application
- Command-line interface for flow execution is now integrated in the orchestrator
- Local data processing
- Development and testing workflows

## Key Features

1. **Lightweight Deployment**: No Spark dependency, runs locally
2. **Python-Based Execution**: Pure Python operator implementations
3. **Plugin System**: Extensible with custom operators
4. **Flow Configuration**: JSON-based flow definitions
5. **Local Data Processing**: File system and local storage support

## Operator Pattern

Each operator follows a consistent pattern:
- Inherits from `AbstractOperator`
- Implements `execute()` method
- Configurable via JSON
- Chainable in flows

## Orchestrator Hierarchy

```
AbstractOrchestrator (base class)
├── CommandLineOrchestrator (CLI execution)
└── PythonOrchestrator (programmatic execution)
```



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
- Cloud deployment support (without Spark)
- Web UI for flow management