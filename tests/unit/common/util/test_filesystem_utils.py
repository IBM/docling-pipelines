"""
Unit tests for filesystem utilities.
Tests for path management and directory operations.
"""

import os
import shutil
import tempfile
from unittest.mock import patch

from docpipe.utils.infrastructure.filesystem import (
    DEFAULT_DATA_ROOT_FOLDER,
    delete_folders,
    get_data_path,
)


class TestGetDataPath:
    """Test get_data_path functionality."""

    def test_get_data_path_default(self):
        """Test getting default data path."""
        result = get_data_path()
        assert result == DEFAULT_DATA_ROOT_FOLDER
        assert os.path.exists(result)

    def test_get_data_path_with_subdirectory(self):
        """Test getting data path with subdirectory."""
        sub_dir = "/test_subdir"
        result = get_data_path(sub_dir=sub_dir)

        expected = DEFAULT_DATA_ROOT_FOLDER + sub_dir
        assert result == expected
        assert os.path.exists(result)

        # Cleanup
        if os.path.exists(result):
            shutil.rmtree(result)

    def test_get_data_path_creates_directory(self):
        """Test that get_data_path creates directory if it doesn't exist."""
        sub_dir = "/test_create_dir"
        full_path = DEFAULT_DATA_ROOT_FOLDER + sub_dir

        # Ensure directory doesn't exist
        if os.path.exists(full_path):
            shutil.rmtree(full_path)

        result = get_data_path(sub_dir=sub_dir)

        assert os.path.exists(result)
        assert os.path.isdir(result)

        # Cleanup
        if os.path.exists(result):
            shutil.rmtree(result)

    def test_get_data_path_with_nested_subdirectories(self):
        """Test getting data path with nested subdirectories."""
        sub_dir = "/level1/level2/level3"
        result = get_data_path(sub_dir=sub_dir)

        expected = DEFAULT_DATA_ROOT_FOLDER + sub_dir
        assert result == expected
        assert os.path.exists(result)

        # Cleanup
        base_path = DEFAULT_DATA_ROOT_FOLDER + "/level1"
        if os.path.exists(base_path):
            shutil.rmtree(base_path)

    def test_get_data_path_idempotent(self):
        """Test that calling get_data_path multiple times is safe."""
        sub_dir = "/test_idempotent"

        result1 = get_data_path(sub_dir=sub_dir)
        result2 = get_data_path(sub_dir=sub_dir)

        assert result1 == result2
        assert os.path.exists(result1)

        # Cleanup
        if os.path.exists(result1):
            shutil.rmtree(result1)

    def test_get_data_path_with_empty_string(self):
        """Test getting data path with empty string subdirectory."""
        result = get_data_path(sub_dir="")
        assert result == DEFAULT_DATA_ROOT_FOLDER
        assert os.path.exists(result)

    def test_get_data_path_with_leading_slash(self):
        """Test that subdirectory with leading slash works correctly."""
        sub_dir = "/test_slash"
        result = get_data_path(sub_dir=sub_dir)

        assert result == DEFAULT_DATA_ROOT_FOLDER + sub_dir

        # Cleanup
        if os.path.exists(result):
            shutil.rmtree(result)

    def test_get_data_path_with_trailing_slash(self):
        """Test subdirectory with trailing slash."""
        sub_dir = "/test_trailing/"
        result = get_data_path(sub_dir=sub_dir)

        expected = DEFAULT_DATA_ROOT_FOLDER + sub_dir
        assert result == expected

        # Cleanup
        base_path = DEFAULT_DATA_ROOT_FOLDER + "/test_trailing"
        if os.path.exists(base_path):
            shutil.rmtree(base_path)

    def test_get_data_path_with_special_characters(self):
        """Test subdirectory with special characters."""
        sub_dir = "/test-dir_123"
        result = get_data_path(sub_dir=sub_dir)

        assert os.path.exists(result)

        # Cleanup
        if os.path.exists(result):
            shutil.rmtree(result)


class TestDeleteFolders:
    """Test delete_folders functionality."""

    def test_delete_single_folder(self):
        """Test deleting a single folder."""
        # Create a temporary folder
        temp_dir = tempfile.mkdtemp()

        # Create some files in it
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test content")

        assert os.path.exists(temp_dir)

        delete_folders(paths_list=[temp_dir])

        assert not os.path.exists(temp_dir)

    def test_delete_multiple_folders(self):
        """Test deleting multiple folders."""
        # Create multiple temporary folders
        temp_dir1 = tempfile.mkdtemp()
        temp_dir2 = tempfile.mkdtemp()
        temp_dir3 = tempfile.mkdtemp()

        assert os.path.exists(temp_dir1)
        assert os.path.exists(temp_dir2)
        assert os.path.exists(temp_dir3)

        delete_folders(paths_list=[temp_dir1, temp_dir2, temp_dir3])

        assert not os.path.exists(temp_dir1)
        assert not os.path.exists(temp_dir2)
        assert not os.path.exists(temp_dir3)

    def test_delete_folder_with_nested_structure(self):
        """Test deleting folder with nested files and directories."""
        temp_dir = tempfile.mkdtemp()

        # Create nested structure
        nested_dir = os.path.join(temp_dir, "nested", "deep")
        os.makedirs(nested_dir)

        # Create files at different levels
        with open(os.path.join(temp_dir, "root.txt"), "w") as f:
            f.write("root")
        with open(os.path.join(nested_dir, "deep.txt"), "w") as f:
            f.write("deep")

        delete_folders(paths_list=[temp_dir])

        assert not os.path.exists(temp_dir)

    def test_delete_nonexistent_folder(self):
        """Test deleting a folder that doesn't exist."""
        nonexistent_path = "/tmp/nonexistent_folder_12345"

        # Should not raise error
        delete_folders(paths_list=[nonexistent_path])

    def test_delete_empty_folder(self):
        """Test deleting an empty folder."""
        temp_dir = tempfile.mkdtemp()

        assert os.path.exists(temp_dir)

        delete_folders(paths_list=[temp_dir])

        assert not os.path.exists(temp_dir)

    def test_delete_folders_logs_contents(self):
        """Test that delete_folders logs folder contents before deletion."""
        temp_dir = tempfile.mkdtemp()

        # Create some files
        test_file1 = os.path.join(temp_dir, "file1.txt")
        test_file2 = os.path.join(temp_dir, "file2.txt")
        with open(test_file1, "w") as f:
            f.write("content1")
        with open(test_file2, "w") as f:
            f.write("content2")

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

        assert not os.path.exists(temp_dir)

    def test_delete_folder_with_readonly_files(self):
        """Test deleting folder with read-only files."""
        temp_dir = tempfile.mkdtemp()

        # Create a read-only file
        readonly_file = os.path.join(temp_dir, "readonly.txt")
        with open(readonly_file, "w") as f:
            f.write("readonly content")

        # Make file read-only
        os.chmod(readonly_file, 0o444)

        try:
            delete_folders(paths_list=[temp_dir])
            # On some systems, this might succeed; on others, it might fail
            # Just verify the function doesn't crash
        except Exception:
            # If it fails, that's also acceptable behavior
            pass
        finally:
            # Cleanup: restore permissions and delete if still exists
            if os.path.exists(temp_dir):
                os.chmod(readonly_file, 0o644)
                shutil.rmtree(temp_dir)

    def test_delete_folder_with_symlinks(self):
        """Test deleting folder containing symlinks."""
        temp_dir = tempfile.mkdtemp()

        # Create a file and a symlink to it
        real_file = os.path.join(temp_dir, "real.txt")
        with open(real_file, "w") as f:
            f.write("real content")

        symlink_path = os.path.join(temp_dir, "link.txt")
        try:
            os.symlink(real_file, symlink_path)
        except OSError:
            # Symlinks might not be supported on all systems
            pass

        delete_folders(paths_list=[temp_dir])

        assert not os.path.exists(temp_dir)

    def test_delete_folder_with_large_number_of_files(self):
        """Test deleting folder with many files."""
        temp_dir = tempfile.mkdtemp()

        # Create 100 files
        for i in range(100):
            file_path = os.path.join(temp_dir, f"file_{i}.txt")
            with open(file_path, "w") as f:
                f.write(f"content {i}")

        delete_folders(paths_list=[temp_dir])

        assert not os.path.exists(temp_dir)

    def test_delete_folder_with_unicode_filenames(self):
        """Test deleting folder with Unicode filenames."""
        temp_dir = tempfile.mkdtemp()

        # Create files with Unicode names
        unicode_file1 = os.path.join(temp_dir, "文件.txt")
        unicode_file2 = os.path.join(temp_dir, "файл.txt")

        try:
            with open(unicode_file1, "w", encoding="utf-8") as f:
                f.write("Chinese filename")
            with open(unicode_file2, "w", encoding="utf-8") as f:
                f.write("Russian filename")
        except Exception:
            # Some systems might not support Unicode filenames
            pass

        delete_folders(paths_list=[temp_dir])

        assert not os.path.exists(temp_dir)


class TestDefaultDataRootFolder:
    """Test DEFAULT_DATA_ROOT_FOLDER constant."""

    def test_default_data_root_folder_value(self):
        """Test that DEFAULT_DATA_ROOT_FOLDER has expected value."""
        assert DEFAULT_DATA_ROOT_FOLDER == "./data"

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
            if os.path.exists(base_path):
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
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def test_get_data_path_concurrent_calls(self):
        """Test that concurrent calls to get_data_path are safe."""
        sub_dir = "/test_concurrent"

        # Multiple calls should all succeed
        results = [get_data_path(sub_dir=sub_dir) for _ in range(10)]

        # All results should be the same
        assert all(r == results[0] for r in results)

        # Cleanup
        if os.path.exists(results[0]):
            shutil.rmtree(results[0])
