"""Unit tests for LocalFileStore."""

from pathlib import Path
from unittest.mock import patch

import pytest

from docpipe.core.custom_operators.file_store import LocalFileStore


class TestLocalFileStore:
    """Test suite for LocalFileStore implementation."""

    def test_store_and_get_operator_dir(self, *, tmp_path: Path) -> None:
        """Test storing operator file and retrieving directory."""
        store = LocalFileStore(base_dir=tmp_path)

        src_file = tmp_path / "my_op.py"
        src_file.write_text("# sample operator code", encoding="utf-8")

        operator_id = "test-operator-123"
        dir_path = store.store(operator_id=operator_id, operator_file_path=src_file)

        assert Path(dir_path).exists()
        assert (Path(dir_path) / "my_op.py").exists()

        retrieved_dir = store.get_operator_dir(operator_id=operator_id)
        assert retrieved_dir is not None
        assert retrieved_dir == Path(dir_path)

    def test_get_operator_dir_returns_none_when_missing(self, *, tmp_path: Path) -> None:
        """Test getting non-existent operator directory."""
        store = LocalFileStore(base_dir=tmp_path)
        assert store.get_operator_dir(operator_id="nonexistent") is None

    def test_delete_removes_operator_directory(self, *, tmp_path: Path) -> None:
        """Test deleting operator directory."""
        store = LocalFileStore(base_dir=tmp_path)

        src_file = tmp_path / "op.py"
        src_file.write_text("# code", encoding="utf-8")

        operator_id = "del-op-456"
        dir_path = store.store(operator_id=operator_id, operator_file_path=src_file)
        assert Path(dir_path).exists()

        store.delete(operator_id=operator_id)
        assert not Path(dir_path).exists()
        assert store.get_operator_dir(operator_id=operator_id) is None

    def test_get_directory_tree_skips_symlinks(self, *, tmp_path: Path) -> None:
        """Test directory tree generation ignores symlinks."""
        store = LocalFileStore(base_dir=tmp_path)

        # Create operator subfolder and file
        op_dir = tmp_path / "op-1"
        op_dir.mkdir()
        (op_dir / "op.py").write_text("print('hello')", encoding="utf-8")

        # Create symlink
        symlink_path = tmp_path / "symlink_dir"
        try:
            symlink_path.symlink_to(op_dir, target_is_directory=True)
        except OSError:
            pass  # Some platforms/environments disallow symlinks

        tree = store.get_directory_tree()
        child_names = [c["name"] for c in tree.get("children", [])]
        assert "op-1" in child_names
        assert "symlink_dir" not in child_names

    def test_store_cleans_up_tmp_and_reraises_on_write_failure(self, *, tmp_path: Path) -> None:
        """Tmp file is removed and exception propagates when write_bytes raises after creating it."""
        store = LocalFileStore(base_dir=tmp_path)
        src_file = tmp_path / "op.py"
        src_file.write_text("# code", encoding="utf-8")
        tmp_target = tmp_path / "err-op" / ".tmp_op.py"

        original_write_bytes = Path.write_bytes

        def write_then_raise(self, data):
            if self.name.startswith(".tmp_"):
                original_write_bytes(self, data)  # create the tmp file, then fail
                raise OSError("disk full")
            return original_write_bytes(self, data)

        with patch.object(Path, "write_bytes", write_then_raise):
            with pytest.raises(OSError, match="disk full"):
                store.store(operator_id="err-op", operator_file_path=src_file)

        assert not tmp_target.exists()

    def test_store_cleans_up_tmp_and_reraises_on_rename_failure(self, *, tmp_path: Path) -> None:
        """Tmp file is removed and exception propagates when rename raises after a successful write."""
        store = LocalFileStore(base_dir=tmp_path)
        src_file = tmp_path / "op.py"
        src_file.write_text("# code", encoding="utf-8")
        tmp_target = tmp_path / "err-op" / ".tmp_op.py"

        with patch.object(Path, "rename", side_effect=OSError("rename failed")):
            with pytest.raises(OSError, match="rename failed"):
                store.store(operator_id="err-op", operator_file_path=src_file)

        assert not tmp_target.exists()
