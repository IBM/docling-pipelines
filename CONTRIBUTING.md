# Contributing to datasift-opensource

Thank you for your interest in contributing to datasift-opensource! This guide will help you get started with contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Documentation Requirements](#documentation-requirements)
- [Getting Help](#getting-help)

## Code of Conduct

### Expected Behavior

- Be respectful and inclusive in all interactions
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards other community members

### Unacceptable Behavior

- Harassment, discrimination, or offensive comments
- Trolling or insulting/derogatory comments
- Publishing others' private information without permission
- Other conduct which could reasonably be considered inappropriate

### Reporting Issues

If you experience or witness unacceptable behavior, please report it to the project maintainers.

## Getting Started

### Prerequisites

- **Python 3.12** (required)
- **uv** package manager ([installation guide](https://docs.astral.sh/uv/))
- **Git** for version control
- **Ollama** (optional, for LLM operators)
- **OpenSearch** (optional, for vector database operators)

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:

```bash
git clone https://github.com/YOUR-USERNAME/datasift-opensource.git
cd datasift-opensource
```

3. Add the upstream repository:

```bash
git remote add upstream https://github.com/ORIGINAL-OWNER/datasift-opensource.git
```

## Development Setup

### Quick Setup (Automated)

Use the automated setup script for a complete environment:

```bash
./scripts/setup_datasift_environment.sh
```

This installs Python 3.12, uv, Ollama, OpenSearch, and all dependencies.

### Manual Setup

1. **Install uv** (if not already installed):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. **Navigate to backend directory and install dependencies**:

```bash
cd src/datasift_opensource/backend
uv sync --extra dev
```

3. **Activate the virtual environment**:

```bash
source .venv/bin/activate
cd ../../..  # Return to project root
```

4. **Install pre-commit hooks**:

```bash
cd src/datasift_opensource/backend
uv run pre-commit install
```

### Verify Installation

Run tests to verify your setup:

```bash
# From project root with activated venv
pytest -v
```

## Development Workflow

### Branch Naming Conventions

Use descriptive branch names following these patterns:

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring
- `test/description` - Test additions or modifications

Examples:
- `feature/add-pdf-extractor`
- `fix/opensearch-connection-timeout`
- `docs/update-api-reference`

### Creating a Feature Branch

1. **Sync with upstream**:

```bash
git checkout main
git pull upstream main
```

2. **Create your feature branch**:

```bash
git checkout -b feature/your-feature-name
```

### Making Changes

1. **Make your changes** following the [Code Style Guidelines](#code-style-guidelines)

2. **Run code quality checks**:

```bash
# From backend directory
cd src/datasift_opensource/backend

# Run pre-commit hooks
uv run pre-commit run --all-files

# Or run individual tools
uv run ruff check --fix .
uv run ruff format .
uv run mypy .
```

3. **Run tests**:

```bash
# From project root with activated venv
pytest -v

# Run with coverage
pytest -v --cov=src --cov-report=html
```

4. **Commit your changes** following [Commit Message Guidelines](#commit-message-guidelines)

## Code Style Guidelines

### Python Style Guide

We follow **PEP 8** with some project-specific conventions:

#### Line Length
- Maximum line length: **120 characters**

#### Import Organization

Imports should be organized in the following order:
1. Standard library imports
2. Third-party imports
3. Local application imports

Add a blank line between each import group.

Use `ruff` for automatic import sorting:

```bash
uv run ruff check --fix .
```

#### Type Hints

- **Always use type hints** for function parameters and return values
- Use `typing` module for complex types

```python
from typing import List, Dict, Optional

def process_documents(
    file_paths: List[str],
    config: Dict[str, any],
    batch_size: Optional[int] = None
) -> List[Dict[str, any]]:
    """Process documents with given configuration."""
    pass
```

#### Naming Conventions

- **Classes**: `PascalCase` (e.g., `DocumentProcessor`, `VectorDBOperator`)
- **Functions/Methods**: `snake_case` (e.g., `process_document`, `get_embeddings`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_BATCH_SIZE`, `DEFAULT_TIMEOUT`)
- **Private methods**: Prefix with `_` (e.g., `_validate_config`)

#### String Quotes

- Use **double quotes** for strings: `"example"`
- Configured automatically by `ruff format`

#### Documentation Standards

- **Docstrings**: Use Google-style docstrings for all public functions and classes
- **Comments**: Use inline comments sparingly, prefer self-documenting code

```python
def extract_text(file_path: str, use_ocr: bool = False) -> str:
    """Extract text content from a document.
    
    Args:
        file_path: Path to the document file
        use_ocr: Whether to use OCR for image-based documents
        
    Returns:
        Extracted text content
        
    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If the file format is not supported
    """
    pass
```

### Code Quality Tools

The project uses the following tools (configured in [`pyproject.toml`](src/datasift_opensource/backend/pyproject.toml:159)):

- **Ruff**: Linting and formatting (replaces black, isort, flake8)
- **mypy**: Static type checking
- **detect-secrets**: Prevent committing secrets

All tools run automatically via pre-commit hooks.

## Testing Requirements

### Test Organization

Tests are organized by type:

- **Unit tests**: `tests/unit/` - Fast, isolated tests
- **Integration tests**: `tests/integration/` - Tests with external dependencies

### Writing Tests

1. **Create test files** matching the pattern `test_*.py`
2. **Use pytest fixtures** from [`tests/conftest.py`](tests/conftest.py)
3. **Mark tests appropriately**:

```python
import pytest

@pytest.mark.unit
def test_document_processor():
    """Test document processing logic."""
    pass

@pytest.mark.integration
def test_opensearch_integration():
    """Test OpenSearch integration."""
    pass
```

### Running Tests

```bash
# Run all tests
pytest -v

# Run only unit tests
pytest -m unit -v

# Run only integration tests
pytest -m integration -v

# Run specific test file
pytest tests/unit/operators/test_chunker.py -v

# Run with coverage
pytest -v --cov=src --cov-report=html
```

### Test Coverage Expectations

- **New features**: Minimum 80% coverage
- **Bug fixes**: Add tests that reproduce the bug
- **Critical paths**: Aim for 90%+ coverage

View coverage report:

```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Test Best Practices

- Write clear, descriptive test names
- One assertion per test when possible
- Use fixtures for common setup
- Mock external dependencies in unit tests
- Clean up resources in teardown

## Pull Request Process

### Before Submitting

1. **Sync with upstream main**:

```bash
git checkout main
git pull upstream main
git checkout your-feature-branch
git rebase main
```

2. **Run all checks**:

```bash
# Code quality
cd src/datasift_opensource/backend
uv run pre-commit run --all-files

# Tests
cd ../../..
pytest -v --cov=src
```

3. **Update documentation** if needed (see [Documentation Requirements](#documentation-requirements))

### PR Title Format

Use clear, descriptive titles following this format:

```
<type>: <short description>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Test additions or modifications
- `chore`: Maintenance tasks

Examples:
- `feat: Add semantic chunking operator`
- `fix: Resolve OpenSearch connection timeout`
- `docs: Update API reference for VectorDB operator`

### PR Description

Include in your PR description:

1. **Summary**: Brief overview of changes
2. **Motivation**: Why this change is needed
3. **Changes**: Detailed list of modifications
4. **Testing**: How you tested the changes
5. **Screenshots**: If applicable (UI changes)
6. **Breaking Changes**: If any
7. **Related Issues**: Link to related issues

Template:

```markdown
## Summary
Brief description of the changes

## Motivation
Why this change is needed

## Changes
- Change 1
- Change 2
- Change 3

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Breaking Changes
None / List any breaking changes

## Related Issues
Closes #123
```

### Required Checks

All PRs must pass:

- ✅ Pre-commit hooks (ruff, mypy, detect-secrets)
- ✅ Unit tests
- ✅ Integration tests (if applicable)
- ✅ Code coverage threshold
- ✅ Documentation updates (if needed)

### Review Process

1. **Automated checks** run on PR submission
2. **Maintainer review** - typically within 2-3 business days
3. **Address feedback** - make requested changes
4. **Approval** - at least one maintainer approval required
5. **Merge** - maintainer will merge after approval

### Merge Requirements

- All checks passing
- At least one maintainer approval
- No unresolved conversations
- Up-to-date with main branch

## Commit Message Guidelines

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Test additions or modifications
- `chore`: Maintenance tasks

### Scope

Optional, indicates the area of change:
- `operators`: Operator-related changes
- `orchestrator`: Orchestration logic
- `api`: API changes
- `cli`: CLI changes
- `tests`: Test-related changes

### Subject

- Use imperative mood: "add" not "added" or "adds"
- Don't capitalize first letter
- No period at the end
- Maximum 50 characters

### Body

- Explain what and why, not how
- Wrap at 72 characters
- Separate from subject with blank line

### Footer

- Reference issues: `Closes #123`, `Fixes #456`
- Note breaking changes: `BREAKING CHANGE: description`

### Examples

**Good commits:**

```
feat(operators): add semantic chunking operator

Implement semantic chunking using sentence transformers for
context-aware document splitting. Includes configurable
similarity threshold and minimum chunk size.

Closes #234
```

```
fix(opensearch): resolve connection timeout issue

Increase default timeout from 30s to 60s and add retry logic
for transient connection failures.

Fixes #456
```

```
docs: update API reference for VectorDB operator

Add examples for OpenSearch configuration and clarify
parameter descriptions.
```

**Bad commits:**

```
Fixed bug
```

```
Updated files
```

```
WIP
```

## Documentation Requirements

### When to Update Documentation

Update documentation when you:

- Add new operators or features
- Change existing APIs or behavior
- Add new configuration options
- Fix bugs that affect documented behavior
- Add new examples or use cases

### Documentation Files

- **[`README.md`](README.md)**: Project overview, setup, and quick start
- **[`ARCHITECTURE.md`](ARCHITECTURE.md)**: System design and architecture
- **[`OPERATOR_REFERENCE.md`](OPERATOR_REFERENCE.md)**: Detailed operator and API documentation
- **[`QUICKSTART.md`](QUICKSTART.md)**: Quick start guide
- **`docs/operators/`**: Operator-specific documentation
- **`examples/`**: Code examples and sample flows

### Documentation Style

- Use clear, concise language
- Include code examples
- Use proper Markdown formatting
- Add links to related documentation
- Keep examples up-to-date with code changes

### Code Comments

- Use docstrings for all public functions and classes
- Keep inline comments minimal and meaningful
- Explain "why" not "what" in comments
- Update comments when changing code

## Getting Help

### Resources

- **[Complete Pipeline Setup Guide](USER_GUIDE_PIPELINE_SETUP.md)**: Comprehensive setup and usage
- **[Architecture Documentation](ARCHITECTURE.md)**: System design details
- **[Operator Reference](OPERATOR_REFERENCE.md)**: Detailed operator and API documentation
- **[Examples](examples/)**: Sample flows and code examples

### Communication

- **Issues**: For bug reports and feature requests
- **Discussions**: For questions and general discussion
- **Pull Requests**: For code contributions

### Questions?

If you have questions:

1. Check existing documentation
2. Search existing issues and discussions
3. Create a new discussion or issue

---

Thank you for contributing to datasift-opensource! Your contributions help make this project better for everyone.