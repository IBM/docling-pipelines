#!/usr/bin/env python3
"""Validate notebook JSON structure and Python code-cell syntax."""

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Iterable


def notebook_paths(paths: Iterable[Path]) -> list[Path]:
    """Return sorted notebook files from the supplied files and directories."""
    notebooks: set[Path] = set()
    for path in paths:
        if path.is_dir():
            notebooks.update(path.rglob("*.ipynb"))
        elif path.suffix == ".ipynb":
            notebooks.add(path)
    return sorted(notebooks)


def validate_notebook(path: Path) -> list[str]:
    """Return validation errors for one notebook."""
    try:
        notebook = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return [f"{path}: invalid JSON ({error})"]

    if not isinstance(notebook, dict) or not isinstance(notebook.get("cells"), list):
        return [f"{path}: notebook must be an object with a cells list"]

    errors: list[str] = []
    for index, cell in enumerate(notebook["cells"]):
        if not isinstance(cell, dict):
            errors.append(f"{path}: cell {index} is not an object")
            continue
        if cell.get("cell_type") != "code":
            continue

        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        if not isinstance(source, str):
            errors.append(f"{path}: cell {index} source is not text")
            continue

        try:
            ast.parse(source, filename=f"{path}:cell {index}")
        except SyntaxError as error:
            location = f"line {error.lineno}" if error.lineno is not None else "unknown line"
            errors.append(f"{path}: cell {index} has invalid Python ({location}: {error.msg})")
    return errors


def main(argv: list[str] | None = None) -> int:
    """Validate notebooks named on the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="Notebook files or directories")
    args = parser.parse_args(argv)

    paths = notebook_paths(args.paths)
    if not paths:
        print("No .ipynb files found.", file=sys.stderr)
        return 1

    errors = [error for path in paths for error in validate_notebook(path)]
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"Validated {len(paths)} notebook(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
