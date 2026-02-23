# Documentation

This directory contains comprehensive documentation for the datasift-open project.

## Contents

### Getting Started
- Installation guide
- Quick start tutorial
- Basic concepts

### User Guide
- Flow configuration
- Operator reference
  - [Ingest LangChain Loader](operators/ingest_langchain_loader.md) - Multi-provider document ingestion
  - [Google Drive Setup](operators/google_drive_setup.md) - Google Drive configuration guide
- CLI usage
- Python API usage

### Developer Guide
- Architecture overview
- Creating custom operators
- Plugin development
- Contributing guidelines

### API Reference
- Core API documentation
- Operator API
- Configuration API

### Examples
- Sample flows
- Common use cases
- Best practices

## Building Documentation

Documentation is built using Sphinx or MkDocs (to be determined).

```bash
# Build documentation
cd docs
make html

# View documentation
open _build/html/index.html
```

## Contributing to Documentation
- Use clear, concise language
- Include code examples
- Add diagrams where helpful
- Keep documentation up-to-date with code changes