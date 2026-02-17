# Datasift-Open Architecture

This document describes the architecture and organization of the datasift-open repository.

## Overview

Datasift-open is a lightweight, standalone runtime for executing data processing flows locally or in non-Spark environments. It provides a command-line orchestrator and Python-based operators for data transformation, validation, and processing tasks.

## Repository Structure

```
datasift-opensource/
├── src/datasift_opensource/          # Main source code
│   ├── config/                       # Configuration management
│   ├── common/                       # Shared utilities and models
│   ├── core/                         # Core orchestration framework
│   │   ├── orchestrator/             # Orchestrator implementations
│   │   │   ├── cmdline/              # Command-line orchestrator
│   │   │   └── python/               # Python orchestrator
│   │   ├── data_access/              # Data access abstractions
│   │   ├── plugins/                  # Plugin system
│   │   └── runtime_jobs/             # Runtime job execution
│   ├── operators/                    # Python operator implementations
│   │   ├── language/                 # Language processing operators
│   │   ├── transform/                # Data transformation operators
│   │   ├── validation/               # Data validation operators
│   │   ├── universal/                # Universal operators
│   │   └── custom/                   # Custom operator support
│   ├── app/                          # Web application (if needed)
│   ├── orchestrator/                 # Legacy orchestrator (to be migrated)
│   └── ui/                           # User interface components
├── apps/                             # Applications
│   └── cli/                          # Command-line interface
├── tests/                            # Test suites
│   ├── unit/                         # Unit tests
│   ├── integration/                  # Integration tests
│   └── fixtures/                     # Test fixtures
├── docs/                             # Documentation
├── examples/                         # Example flows and configurations
└── pyproject.toml                    # Project configuration
```

## Core Components

### 1. Configuration Management (`src/datasift_opensource/config/`)
- Configuration loading and validation
- Environment-specific settings
- Configuration schemas and defaults

### 2. Common Utilities (`src/datasift_opensource/common/`)
- Shared utility functions
- Common data models
- Exception classes
- Helper functions
- **Note:** Excludes Spark-specific utilities

### 3. Core Framework (`src/datasift_opensource/core/`)

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

### 4. Operators (`src/datasift_opensource/operators/`)

Python-based operator implementations (non-Spark):

- **Language Operators**: Language detection, text analysis, NLP
- **Transform Operators**: Data mapping, format conversion, enrichment
- **Validation Operators**: Schema validation, data quality checks
- **Universal Operators**: Storage operations, generic transformations
- **Custom Operators**: User-defined operators, plugin-based extensions

### 5. CLI Application (`apps/cli/`)
- Command-line interface for flow execution
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

## Excluded Components

The following components are **NOT** included in this repository (they belong in datasift-spark):
- Spark orchestrator (`PySparkOrchestrator`)
- Spark operators (`SparkLanguageDetect`, `SparkRedactionOperator`, etc.)
- Spark-specific utilities
- Enterprise integrations (CAMS, UDC)
- REST API for Spark job management

## Migration Notes

This repository is organized to support the split from the datasift-api monorepo:
- All Spark dependencies removed
- Focus on lightweight, local execution
- Python-only operator implementations
- Command-line and programmatic interfaces

## Development Guidelines

1. **No Spark Dependencies**: Keep the project Spark-free
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