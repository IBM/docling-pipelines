# datasift-operators

This repository contains the datasift operators with FastAPI server, CLI orchestrator, and UI components.

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
├── apps/                      # Applications
│   └── cli/                   # CLI application
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
# Using uv (from backend directory)
cd src/datasift_opensource/backend
uv run uvicorn datasift_opensource.backend.app.main:app --reload

# Or with activated venv (from project root)
uvicorn datasift_opensource.backend.app.main:app --reload --host 0.0.0.0 --port 8000
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

Available commands:
```bash
# Start a service
datasift-orchestrator start <service-name> --config <config-file>

# Stop a service
datasift-orchestrator stop <service-name>

# Check service status
datasift-orchestrator status [service-name]

# List all services
datasift-orchestrator list
```

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

Run all tests (from backend directory):
```bash
cd src/datasift_opensource/backend

# Set environment variables (PYTHONPATH must point to src directory)
export PYTHONPATH="$(cd ../../.. && pwd)/src:${PYTHONPATH}"
export TEST_CP4D_USERNAME=udp_unittest_user
export TEST_CP4D_PASSWORD="udp_unittest_pass@123"

# Sync dependencies (first time or after changes)
uv sync --extra dev

# Run all tests
uv run pytest ../../../tests/ -v

# Run specific test directory
uv run pytest ../../../tests/unit/operators/ingest/ -v

# With coverage
uv run pytest ../../../tests/ --cov=datasift_opensource --cov-report=html
```

**Important**: The `PYTHONPATH` must point to the `src` directory (relative to project root) for imports to work correctly.

### Code Quality

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

## Contributing

1. Create a new branch for your feature
2. Make your changes
3. Run tests and code quality checks
4. Submit a pull request