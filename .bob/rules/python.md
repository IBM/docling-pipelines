## Python Environment
- Activate venv before any Python/pytest command: `source .venv/bin/activate`
- Use `uv pip` not `pip`
- Do not add "made with Bob" to any Python code

## Linting
- Try `ruff check <path>` first; if ruff is not found, fall back to `pre-commit run ruff --files <file1> <file2> ...`
