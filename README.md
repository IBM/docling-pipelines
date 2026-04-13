# datasift-operators

This repository contains the datasift operators with FastAPI server, CLI orchestrator, and UI components.

## Available Operators

### Vector Database Operators

- **OpenSearch** - Vector similarity search with multiple KNN engines (FAISS, Lucene, nmslib, jVector)
  - See [OpenSearch Documentation](docs/opensearch/) - Complete setup and usage guide
  - See [Operator Reference](docs/operators/opensearch.md) - Technical API documentation
  - See [Integration Example](examples/opensearch_example_README.md) - Code examples

### Ingest Operators

- **Local Folder** - Ingest documents from local filesystem
- **Local S3** - Ingest documents from S3-compatible storage
- **CSV** - Ingest structured data from CSV files
- **LangChain Loader** - Ingest using LangChain document loaders

### Extract Operators

- **Docling** - Extract content and structure from documents using Docling
  - Basic markdown extraction
  - VLM pipeline for enhanced extraction
  - Template-based structured extraction
  - Docling-Serve REST API integration for scalable processing

### Chunking Operators

- **Docling Chunker** - Chunk documents using Docling's chunking capabilities
- **Semantic Chunker** - Semantic-aware document chunking

### Language Operators

- **Language Detection** - Detect document language
- **Readability** - Assess document readability scores

### Utility Operators

- **Branching** - Conditional flow branching
- **No-op** - Pass-through operator for testing

## Project Structure

```
datasift-opensource/
├── src/datasift_opensource/
│   ├── backend/               # Backend components
│   │   ├── config/           # Configuration management
│   │   ├── common/           # Shared utilities
│   │   ├── core/             # Core orchestration framework
│   │   ├── operators/        # Python operators
│   │   ├── app/              # FastAPI application
│   │   │   ├── routes/       # API route handlers
│   │   │   ├── models/       # Database models
│   │   │   ├── utils/        # Utility functions
│   │   │   └── main.py       # FastAPI app entry point
│   │   ├── orchestrator/     # CLI orchestrator
│   │   │   ├── cli.py        # Command-line interface
│   │   │   └── __init__.py
│   │   ├── pyproject.toml    # Backend dependencies and configuration
│   │   ├── uv.lock           # UV lock file
│   │   └── .python-version   # Python version
│   └── ui/                    # UI components
├── tests/                     # Test suites
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── fixtures/              # Test fixtures
├── docs/                      # Documentation
├── examples/                  # Example flows
├── Dockerfile                 # Docker configuration
└── README.md
```

## Setup

This project uses [uv](https://docs.astral.sh/uv/) for fast Python package management.

### Prerequisites

Install uv if you haven't already:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd datasift-opensource
```

2. Navigate to the backend directory and create a virtual environment:

```bash
cd src/datasift_opensource/backend
uv sync --extra dev
```

This will:

- Create a virtual environment in `.venv/`
- Install all project dependencies
- Install development dependencies

3. Activate the virtual environment:

```bash
source .venv/bin/activate
cd ../../..  # Return to project root
```

## Running the Application

### FastAPI Server

Start the FastAPI server with uvicorn:

```bash
# Using uvicorn from project root
uvicorn src.datasift_opensource.backend.app.main:app --reload --host 0.0.0.0 --port 8000

# Or using uv from backend directory
cd src/datasift_opensource/backend
uv run uvicorn app.main:app --reload --reload --host 0.0.0.0 --port 8000
```

The API will be available at:

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc

### CLI Orchestrator

Run the CLI orchestrator:

```bash
# Using uv
uv run datasift-orchestrator --help

# Or with activated venv
datasift-orchestrator --help
```

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
# Summary view
datasift-orchestrator --list-operators

# Detailed view with parameters
datasift-orchestrator --list-operators --verbose
```
### DatasiftFlowManager API

Execute datasift flows programmatically using Python:

```python
from datasift_opensource.backend.datasift_flow_manager import DatasiftFlowManager

# Initialize executor
executor = DatasiftFlowManager()

# Execute flow from file
result = executor.execute_flow("path/to/flow.json")

# Execute flow from dictionary
flow_dict = {
    "nodes": [...],
    "edges": [...]
}
result = executor.execute_flow(flow_dict)

# List available operators
operators = executor.list_operators()
```

For detailed examples and usage patterns, see:
- [DatasiftFlowManager Examples](examples/datasift_flow_manager/) - Complete usage guide
- [Quick Start Example](examples/datasift_flow_manager/01_execute_from_file.py) - Basic flow execution


## Docker

### Build Docker Image

Build the Docker image:

```bash
docker build -t datasift-operators:latest .
```

### Run with Docker

Run the FastAPI server:

```bash
docker run -p 8000:8000 datasift-operators:latest
```

Run the CLI orchestrator:

```bash
docker run datasift-operators:latest datasift-orchestrator --help
```

### Build Wheel

Build a wheel distribution:

```bash
cd src/datasift_opensource/backend
uv build --wheel
```

The wheel file will be created in the `dist/` directory.

## Development

### Adding Dependencies

Add a new dependency (from backend directory):

```bash
cd src/datasift_opensource/backend
uv add <package-name>==<version>  # Always specify a fixed version
```

Add a development dependency:

```bash
cd src/datasift_opensource/backend
uv add --dev <package-name>==<version>  # Always specify a fixed version
```

**Important**: After adding any new package, always follow these steps:

1. Sync dependencies and update lock file:

```bash
cd src/datasift_opensource/backend
uv sync --extra dev
```

2. Generate updated requirements.txt:

```bash
cd src/datasift_opensource/backend
uv pip compile pyproject.toml -o requirements.txt
```

3. Install package in editable mode and run tests:

```bash
cd src/datasift_opensource/backend
uv pip install -e .
export TEST_CP4D_USERNAME=udp_unittest_user
export TEST_CP4D_PASSWORD="udp_unittest_pass@123"
uv run pytest ../../../tests/ -v
```

### Testing

The test suite uses pytest with colored output, coverage tracking, and test markers for easy filtering.

#### Quick Start

Run tests from the **project root** (recommended):

```bash
# Activate virtual environment
source src/datasift_opensource/backend/.venv/bin/activate

# Run all tests with colored output
pytest -v

# Run with coverage report
pytest -v --cov=src --cov-report=html

# Run only unit tests
pytest -m unit -v

# Run only integration tests
pytest -m integration -v

# Show 10 slowest tests
pytest --durations=10

# Run specific test file
pytest tests/unit/operators/embeddings/test_embeddings_operator.py -v
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

### Code Quality

#### Pre-commit Hooks

This project uses pre-commit hooks to automatically check and format code before commits. The hooks include:

- **Ruff**: Python linting and formatting
- **detect-secrets**: Prevent committing secrets
- **uv-export**: Keep requirements.txt in sync with pyproject.toml

**Setup pre-commit hooks:**

```bash
# Install pre-commit hooks (one-time setup)
cd src/datasift_opensource/backend
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

## API Development

### Adding New Routes

1. Create a new route file in `src/datasift_opensource/backend/app/routes/`
2. Define your route handlers
3. Import and include the router in `src/datasift_opensource/backend/app/main.py`

Example:

```python
# src/datasift_opensource/backend/app/routes/example.py
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

## Environment Variables

Create a `.env` file in the project root for environment-specific configuration:

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true

# Add other environment variables as needed
```

## Operator Specific Setup

### Embeddings Operator — Ollama Setup

The [`EmbeddingsOperator`](src/datasift_opensource/backend/core/operators/universal/embeddings/embeddings_operator.py) uses Ollama as its **default** embeddings provider (`embeddings_type = "ollama"`). Before using this operator, you must complete the following setup steps.

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

> **Note**: If Ollama is not installed, the server is not running, or no model has been pulled, the operator will raise a [`DatasiftException`](src/datasift_opensource/backend/common/exceptions/datasift_exceptions.py) at runtime.

### OpenSearch Vector Store Operator

The [`OpenSearchOperator`](src/datasift_opensource/backend/core/operators/universal/vectordb/opensearch_operator.py) requires a running OpenSearch instance. The quickest way to get one locally is via the provided Compose file.

#### Step 1 — Start OpenSearch

**Docker:**

```bash
docker-compose -f docker-compose.opensearch.yml up -d
```

**Podman:**

```bash
podman-compose -f docker-compose.opensearch.yml up -d
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
docker-compose -f docker-compose.opensearch.yml down

# Podman
podman-compose -f docker-compose.opensearch.yml down
```

> For full configuration options, engine selection (FAISS/Lucene), AWS OpenSearch Service setup, and advanced usage, see [`docs/opensearch/`](docs/opensearch/) and [`docs/operators/opensearch.md`](docs/operators/opensearch.md).

## Contributing

1. Create a new branch for your feature
2. Make your changes
3. Run tests and code quality checks
4. Submit a pull request
