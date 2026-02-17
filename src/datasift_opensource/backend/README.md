# Backend

This directory contains all backend components of the datasift-open project, including the core framework, operators, and orchestration logic.

## Structure

### config/
Configuration management utilities for the backend services.

### common/
Shared utilities, models, and exceptions used across backend components.

### core/
Core orchestration framework including:
- **orchestrator/** - Flow orchestration (cmdline, python)
- **data_access/** - Data access layer
- **plugins/** - Plugin system
- **runtime_jobs/** - Runtime job execution

### operators/
Python-based operator implementations:
- **language/** - Language processing operators
- **transform/** - Data transformation operators
- **validation/** - Data validation operators
- **universal/** - Universal operators
- **custom/** - Custom operator support

### app/
Backend API application (if needed for web services).

### orchestrator/
Legacy orchestrator components (to be migrated to core/).

## Purpose

The backend layer provides:
- Data processing orchestration
- Operator execution framework
- Configuration management
- Plugin system for extensibility
- API services (optional)

All backend components are Python-based with no Spark dependencies.