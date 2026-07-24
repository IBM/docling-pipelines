# Core Package

This package contains the core functionality of the Docling Pipelines project, including orchestrators, operators, and runtime components.

## Purpose
- Orchestration framework (command-line and Python)
- Base operator classes and implementations
- Data access abstractions
- Plugin system
- Runtime job execution

## Structure

### orchestrator/
Contains orchestrator implementations for executing data processing flows:
- `abstract_orchestrator.py` - Base orchestrator interface
- `cmdline/` - Command-line orchestrator for CLI execution
- `python/` - Python orchestrator for programmatic execution
- `flow_executor.py` - Flow execution logic
- `operator_factory.py` - Operator instantiation

### operators/
Base operator classes (implementations are in `/operators` at root level):
- `abstract_operator.py` - Base operator class
- `abstract_custom_operator.py` - Custom operator base

### data_access/
Data access utilities and abstractions:
- `data_access_utils.py` - Data access helper functions

### plugins/
Plugin system for custom operators:
- `loader.py` - Plugin loading and registration

### runtime_jobs/
Runtime job execution:
- `runtime_flow_executor.py` - Runtime flow execution logic