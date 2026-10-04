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

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "validate_notebooks.py"
SPEC = importlib.util.spec_from_file_location("validate_notebooks", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def write_notebook(path: Path, cells: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"cells": cells}), encoding="utf-8")


def test_validates_code_cells_and_nested_directories(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    write_notebook(
        nested / "valid.ipynb",
        [{"cell_type": "code", "source": ["value = 1\n", "print(value)\n"]}],
    )

    assert VALIDATOR.main([str(tmp_path)]) == 0


def test_rejects_invalid_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    notebook = tmp_path / "broken.ipynb"
    notebook.write_text("{not json", encoding="utf-8")

    assert VALIDATOR.main([str(notebook)]) == 1
    assert "broken.ipynb" in capsys.readouterr().err


def test_rejects_invalid_notebook_structure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    notebook = tmp_path / "malformed.ipynb"
    notebook.write_text(json.dumps({"metadata": {}}), encoding="utf-8")

    assert VALIDATOR.main([str(notebook)]) == 1
    assert "cells list" in capsys.readouterr().err


def test_rejects_invalid_python_cell(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    notebook = tmp_path / "invalid-python.ipynb"
    write_notebook(notebook, [{"cell_type": "code", "source": "if True print('oops')"}])

    assert VALIDATOR.main([str(notebook)]) == 1
    output = capsys.readouterr().err
    assert "cell 0" in output
    assert "invalid Python" in output


def test_no_notebooks_is_an_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert VALIDATOR.main([str(tmp_path)]) == 1
    assert "No .ipynb files found" in capsys.readouterr().err
