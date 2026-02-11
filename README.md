# datasift-operators

This repository contains the datasift operators.

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

2. Create a virtual environment and install dependencies:
```bash
uv sync
```

This will:
- Create a virtual environment in `.venv/`
- Install all project dependencies
- Install development dependencies

3. Activate the virtual environment:
```bash
source .venv/bin/activate
```

### Development

Install with development dependencies:
```bash
uv sync --extra dev
```

### Adding Dependencies

Add a new dependency:
```bash
uv add <package-name>
```

Add a development dependency:
```bash
uv add --dev <package-name>
```

### Running the Project

```bash
uv run python main.py
```

Or activate the virtual environment and run directly:
```bash
source .venv/bin/activate
python main.py
```

### Testing

Run tests (after installing dev dependencies):
```bash
uv run pytest
```

### Code Formatting

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