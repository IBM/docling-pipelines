"""File storage abstraction and implementations for custom operators."""

import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from docpipe.utils.infrastructure.filesystem import get_data_path
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class CustomOperatorFileStore(ABC):
    """Abstract interface for storing custom operator files."""

    @abstractmethod
    def store(self, *, operator_id: str, operator_file_path: Path, stored_filename: str | None = None) -> str:
        """Store operator file and return the directory path.

        Args:
            operator_id: Unique operator identifier
            operator_file_path: Path to source operator file
            stored_filename: Filename to use on disk. Defaults to operator_file_path.name.

        Returns:
            String path to the storage directory
        """
        ...

    @abstractmethod
    def delete(self, *, operator_id: str) -> None:
        """Delete all files associated with an operator.

        Args:
            operator_id: Unique operator identifier
        """
        ...

    @abstractmethod
    def get_operator_dir(self, *, operator_id: str) -> Path | None:
        """Return the operator's storage directory, or None if it doesn't exist.

        Args:
            operator_id: Unique operator identifier

        Returns:
            Path to directory or None
        """
        ...

    @abstractmethod
    def get_directory_tree(self, *, depth: int = 10) -> dict[str, Any]:
        """Return a nested dict representing the storage directory structure.

        Args:
            depth: Maximum traversal depth

        Returns:
            Nested dict of files and directories
        """
        ...


class LocalFileStore(CustomOperatorFileStore):
    """Local filesystem implementation of CustomOperatorFileStore.

    Stores operator files under {data_root}/custom_operators/{operator_id}/{filename}.py.
    """

    def __init__(self, *, base_dir: Path | str | None = None) -> None:
        if base_dir is None:
            self.base_dir = Path(get_data_path(sub_dir="/custom_operators"))
        else:
            self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def store(self, *, operator_id: str, operator_file_path: Path, stored_filename: str | None = None) -> str:
        """Store operator file in the operator's directory."""
        target_dir = self.base_dir / operator_id
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = stored_filename or operator_file_path.name
        target_file = target_dir / filename

        # Identify the existing operator file (if any) before writing the new one.
        # Exclude target_file itself so a same-name replacement is handled by atomic rename.
        existing_files = [f for f in target_dir.glob("*.py") if f != target_file]

        tmp_target = target_dir / f".tmp_{filename}"
        try:
            tmp_target.write_bytes(operator_file_path.read_bytes())
            tmp_target.rename(target_file)
        except Exception:
            if tmp_target.exists():
                tmp_target.unlink()
            raise

        # New file is safely in place — remove the old file only if the name changed
        for old_file in existing_files:
            old_file.unlink()
            logger.info("Removed old operator file %s", old_file.name)

        logger.info("Stored custom operator file %s in %s", filename, target_dir)
        return str(target_dir)

    def delete(self, *, operator_id: str) -> None:
        """Delete operator directory and its contents."""
        target_dir = self.base_dir / operator_id
        if target_dir.exists():
            shutil.rmtree(target_dir)
            logger.info("Deleted custom operator directory: %s", target_dir)

    def get_operator_dir(self, *, operator_id: str) -> Path | None:
        """Return operator directory if it exists."""
        target_dir = self.base_dir / operator_id
        if target_dir.exists() and target_dir.is_dir():
            return target_dir
        return None

    def get_directory_tree(self, *, depth: int = 10) -> dict[str, Any]:
        """Return directory tree ignoring symlinks with max depth."""
        return self._build_tree(self.base_dir, current_depth=0, max_depth=depth)

    def _build_tree(self, root_path: Path, *, current_depth: int, max_depth: int) -> dict[str, Any]:
        """Recursively build tree dict."""
        if current_depth > max_depth or not root_path.exists():
            return {}

        tree: dict[str, Any] = {
            "name": root_path.name,
            "type": "directory",
            "children": [],
        }

        try:
            entries = sorted(root_path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
            for entry in entries:
                if entry.is_symlink():
                    continue

                if entry.is_dir():
                    tree["children"].append(
                        self._build_tree(entry, current_depth=current_depth + 1, max_depth=max_depth)
                    )
                else:
                    tree["children"].append(
                        {
                            "name": entry.name,
                            "type": "file",
                            "size": entry.stat().st_size,
                        }
                    )
        except PermissionError:
            logger.warning("Permission denied accessing %s", root_path)

        return tree
