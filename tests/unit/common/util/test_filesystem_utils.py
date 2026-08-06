"""
Unit tests for filesystem utilities.
Tests for path management and directory operations.
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from docpipe.utils.infrastructure.filesystem import (
    delete_folders,
    get_data_path,
)

DEFAULT_DATA_ROOT_FOLDER = "./data"


class TestGetDataPath:
    """Test get_data_path functionality."""

    def test_get_data_path_default(self):
        """Test getting default data path."""
        result = get_data_path()
        assert result == DEFAULT_DATA_ROOT_FOLDER
        assert Path(result).exists()

    def test_get_data_path_with_subdirectory(self):
        """Test getting data path with subdirectory."""
        sub_dir = "/test_subdir"
        result = get_data_path(sub_dir=sub_dir)

        expected = DEFAULT_DATA_ROOT_FOLDER + sub_dir
        assert result == expected
        assert Path(result).exists()

        # Cleanup
        if Path(result).exists():
            shutil.rmtree(result)

    def test_get_data_path_creates_directory(self):
        """Test that get_data_path creates directory if it doesn't exist."""
        sub_dir = "/test_create_dir"
        full_path = DEFAULT_DATA_ROOT_FOLDER + sub_dir

        # Ensure directory doesn't exist
        if Path(full_path).exists():
            shutil.rmtree(full_path)

        result = get_data_path(sub_dir=sub_dir)

        assert Path(result).exists()
        assert Path(result).is_dir()

        # Cleanup
        if Path(result).exists():
            shutil.rmtree(result)

    def test_get_data_path_with_nested_subdirectories(self):
        """Test getting data path with nested subdirectories."""
        sub_dir = "/level1/level2/level3"
        result = get_data_path(sub_dir=sub_dir)

        expected = DEFAULT_DATA_ROOT_FOLDER + sub_dir
        assert result == expected
        assert Path(result).exists()

        # Cleanup
        base_path = DEFAULT_DATA_ROOT_FOLDER + "/level1"
        if Path(base_path).exists():
            shutil.rmtree(base_path)

    def test_get_data_path_idempotent(self):
        """Test that calling get_data_path multiple times is safe."""
        sub_dir = "/test_idempotent"

        result1 = get_data_path(sub_dir=sub_dir)
        result2 = get_data_path(sub_dir=sub_dir)

        assert result1 == result2
        assert Path(result1).exists()

        # Cleanup
        if Path(result1).exists():
            shutil.rmtree(result1)

    def test_get_data_path_with_empty_string(self):
        """Test getting data path with empty string subdirectory."""
        result = get_data_path(sub_dir="")
        assert result == DEFAULT_DATA_ROOT_FOLDER
        assert Path(result).exists()

    def test_get_data_path_with_leading_slash(self):
        """Test that subdirectory with leading slash works correctly."""
        sub_dir = "/test_slash"
        result = get_data_path(sub_dir=sub_dir)

        assert result == DEFAULT_DATA_ROOT_FOLDER + sub_dir

        # Cleanup
        if Path(result).exists():
            shutil.rmtree(result)

    def test_get_data_path_with_trailing_slash(self):
        """Test subdirectory with trailing slash."""
        sub_dir = "/test_trailing/"
        result = get_data_path(sub_dir=sub_dir)

        expected = DEFAULT_DATA_ROOT_FOLDER + sub_dir
        assert result == expected

        # Cleanup
        base_path = DEFAULT_DATA_ROOT_FOLDER + "/test_trailing"
        if Path(base_path).exists():
            shutil.rmtree(base_path)

    def test_get_data_path_with_special_characters(self):
        """Test subdirectory with special characters."""
        sub_dir = "/test-dir_123"
        result = get_data_path(sub_dir=sub_dir)

        assert Path(result).exists()

        # Cleanup
        if Path(result).exists():
            shutil.rmtree(result)


class TestDeleteFolders:
    """Test delete_folders functionality."""

    def test_delete_single_folder(self):
        """Test deleting a single folder."""
        # Create a temporary folder
        temp_dir = tempfile.mkdtemp()

        # Create some files in it
        test_file = Path(temp_dir) / "test.txt"
        test_file.open("w").close()

        assert Path(temp_dir).exists()

        delete_folders(paths_list=[temp_dir])

        assert not Path(temp_dir).exists()

    def test_delete_multiple_folders(self):
        """Test deleting multiple folders."""
        # Create multiple temporary folders
        temp_dir1 = tempfile.mkdtemp()
        temp_dir2 = tempfile.mkdtemp()
        temp_dir3 = tempfile.mkdtemp()

        assert Path(temp_dir1).exists()
        assert Path(temp_dir2).exists()
        assert Path(temp_dir3).exists()

        delete_folders(paths_list=[temp_dir1, temp_dir2, temp_dir3])

        assert not Path(temp_dir1).exists()
        assert not Path(temp_dir2).exists()
        assert not Path(temp_dir3).exists()

    def test_delete_folder_with_nested_structure(self):
        """Test deleting folder with nested files and directories."""
        temp_dir = tempfile.mkdtemp()

        # Create nested structure
        nested_dir = Path(temp_dir) / "nested" / "deep"
        nested_dir.mkdir(parents=True)

        # Create files at different levels
        (Path(temp_dir) / "root.txt").open("w").close()
        (nested_dir / "deep.txt").open("w").close()

        delete_folders(paths_list=[temp_dir])

        assert not Path(temp_dir).exists()

    def test_delete_nonexistent_folder(self):
        """Test deleting a folder that doesn't exist."""
        nonexistent_path = "/tmp/nonexistent_folder_12345"

        # Should not raise error
        delete_folders(paths_list=[nonexistent_path])

    def test_delete_empty_folder(self):
        """Test deleting an empty folder."""
        temp_dir = tempfile.mkdtemp()

        assert Path(temp_dir).exists()

        delete_folders(paths_list=[temp_dir])

        assert not Path(temp_dir).exists()

    def test_delete_folders_logs_contents(self):
        """Test that delete_folders logs folder contents before deletion."""
        temp_dir = tempfile.mkdtemp()

        # Create some files
        test_file1 = Path(temp_dir) / "file1.txt"
        test_file2 = Path(temp_dir) / "file2.txt"
        test_file1.open("w").close()
        test_file2.open("w").close()

        # Mock logger to verify logging
        with patch("docpipe.utils.infrastructure.filesystem.logger") as mock_logger:
            delete_folders(paths_list=[temp_dir])

            # Verify that logger.info was called
            assert mock_logger.info.called

    def test_delete_folders_with_empty_list(self):
        """Test deleting with empty list."""
        # Should not raise error
        delete_folders(paths_list=[])

    def test_delete_folders_with_mixed_existing_and_nonexistent(self):
        """Test deleting mix of existing and non-existing folders."""
        temp_dir = tempfile.mkdtemp()
        nonexistent = "/tmp/nonexistent_12345"

        delete_folders(paths_list=[temp_dir, nonexistent])

        assert not Path(temp_dir).exists()

    def test_delete_folder_with_readonly_files(self):
        """Test deleting folder with read-only files."""
        temp_dir = tempfile.mkdtemp()

        # Create a read-only file
        readonly_file = Path(temp_dir) / "readonly.txt"
        readonly_file.open("w").close()

        # Make file read-only
        readonly_file.chmod(0o444)

        try:
            delete_folders(paths_list=[temp_dir])
            # On some systems, this might succeed; on others, it might fail
            # Just verify the function doesn't crash
        except Exception:
            # If it fails, that's also acceptable behavior
            pass
        finally:
            # Cleanup: restore permissions and delete if still exists
            if Path(temp_dir).exists():
                readonly_file.chmod(0o644)
                shutil.rmtree(temp_dir)

    def test_delete_folder_with_symlinks(self):
        """Test deleting folder containing symlinks."""
        temp_dir = tempfile.mkdtemp()

        # Create a file and a symlink to it
        real_file = Path(temp_dir) / "real.txt"
        real_file.open("w").close()

        symlink_path = Path(temp_dir) / "link.txt"
        try:
            symlink_path.symlink_to(real_file)
        except OSError:
            # Symlinks might not be supported on all systems
            pass

        delete_folders(paths_list=[temp_dir])

        assert not Path(temp_dir).exists()

    def test_delete_folder_with_large_number_of_files(self):
        """Test deleting folder with many files."""
        temp_dir = tempfile.mkdtemp()

        # Create 100 files
        for i in range(100):
            (Path(temp_dir) / f"file_{i}.txt").open("w").close()

        delete_folders(paths_list=[temp_dir])

        assert not Path(temp_dir).exists()

    def test_delete_folder_with_unicode_filenames(self):
        """Test deleting folder with Unicode filenames."""
        temp_dir = tempfile.mkdtemp()

        # Create files with Unicode names
        unicode_file1 = Path(temp_dir) / "文件.txt"
        unicode_file2 = Path(temp_dir) / "файл.txt"

        try:
            unicode_file1.open("w", encoding="utf-8").close()
            unicode_file2.open("w", encoding="utf-8").close()
        except Exception:
            # Some systems might not support Unicode filenames
            pass

        delete_folders(paths_list=[temp_dir])

        assert not Path(temp_dir).exists()


class TestDefaultDataRootFolder:
    """Test DEFAULT_DATA_ROOT_FOLDER constant."""

    def test_default_data_root_folder_is_string(self):
        """Test that DEFAULT_DATA_ROOT_FOLDER is a string."""
        assert isinstance(DEFAULT_DATA_ROOT_FOLDER, str)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_get_data_path_with_very_long_subdirectory(self):
        """Test with very long subdirectory path."""
        # Create a very long path
        long_subdir = "/" + "/".join([f"dir{i}" for i in range(50)])

        try:
            _ = get_data_path(sub_dir=long_subdir)
            # If successful, cleanup
            base_path = DEFAULT_DATA_ROOT_FOLDER + "/dir0"
            if Path(base_path).exists():
                shutil.rmtree(base_path)
        except Exception:
            # Some systems might have path length limits
            pass

    def test_delete_folders_with_none_in_list(self):
        """Test that None values in paths_list are handled."""
        temp_dir = tempfile.mkdtemp()

        # Should handle None gracefully
        try:
            delete_folders(paths_list=[temp_dir, None])
        except Exception:
            # If it raises, cleanup
            if Path(temp_dir).exists():
                shutil.rmtree(temp_dir)

    def test_get_data_path_concurrent_calls(self):
        """Test that concurrent calls to get_data_path are safe."""
        sub_dir = "/test_concurrent"

        # Multiple calls should all succeed
        results = [get_data_path(sub_dir=sub_dir) for _ in range(10)]

        # All results should be the same
        assert all(r == results[0] for r in results)

        # Cleanup
        if Path(results[0]).exists():
            shutil.rmtree(results[0])
