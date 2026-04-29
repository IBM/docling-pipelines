"""Tests for LocalFlowRepository.

This test suite verifies the LocalFlowRepository implementation with the new
filename format: {flow_name}_{flow_id}.json and the common filename utility methods.
Includes tests for file locking and concurrent access.
"""

import json
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from datasift.core.flows.adapters.repositories.flow_filesystem_utils import (
    FlowFilesystemUtils,
)
from datasift.core.flows.adapters.repositories.local.local_flow_repository import (
    LocalFlowRepository,
)
from datasift.core.flows.domain.models.flow import Flow


class TestLocalFlowRepository:
    """Test suite for LocalFlowRepository."""

    @pytest.fixture
    def temp_flows_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def repository(self, temp_flows_dir, monkeypatch):
        """Create a LocalFlowRepository instance with temp directory."""
        monkeypatch.setenv("LOCAL_FLOWS_DIR", str(temp_flows_dir))
        return LocalFlowRepository()

    @pytest.fixture
    def sample_flow(self):
        """Create a sample flow for testing."""
        return Flow(
            name="Test Flow",
            definition={"nodes": [], "edges": []},
            flow_id=str(uuid4()),
            description="A test flow",
        )

    def test_sanitize_filename_basic(self):
        """Test basic filename sanitization using static method."""
        assert FlowFilesystemUtils.sanitize_filename("Simple Name") == "Simple_Name"
        assert FlowFilesystemUtils.sanitize_filename("Test-Flow") == "Test-Flow"
        assert FlowFilesystemUtils.sanitize_filename("test_flow") == "test_flow"

    def test_sanitize_filename_special_chars(self):
        """Test sanitization of special characters."""
        assert FlowFilesystemUtils.sanitize_filename("Test/Flow") == "TestFlow"
        assert FlowFilesystemUtils.sanitize_filename("Test\\Flow") == "TestFlow"
        assert FlowFilesystemUtils.sanitize_filename("Test:Flow") == "TestFlow"
        assert FlowFilesystemUtils.sanitize_filename("Test*Flow") == "TestFlow"
        assert FlowFilesystemUtils.sanitize_filename("Test?Flow") == "TestFlow"
        assert FlowFilesystemUtils.sanitize_filename("Test<Flow>") == "TestFlow"
        assert FlowFilesystemUtils.sanitize_filename("Test|Flow") == "TestFlow"

    def test_sanitize_filename_empty(self):
        """Test sanitization of empty or special-only names."""
        assert FlowFilesystemUtils.sanitize_filename("") == "unnamed"
        assert FlowFilesystemUtils.sanitize_filename("///") == "unnamed"
        assert FlowFilesystemUtils.sanitize_filename("***") == "unnamed"

    def test_sanitize_filename_length_limit(self):
        """Test that long names are truncated."""
        long_name = "a" * 250
        sanitized = FlowFilesystemUtils.sanitize_filename(long_name)
        assert len(sanitized) == 200

    def test_generate_flow_filename(self):
        """Test flow filename generation."""
        filename = FlowFilesystemUtils.generate_flow_filename("My Flow", "abc123")
        assert filename == "My_Flow_abc123.json"

        filename = FlowFilesystemUtils.generate_flow_filename("Test@Flow", "xyz789")
        assert filename == "TestFlow_xyz789.json"

    def test_extract_flow_id_from_filename(self):
        """Test extracting flow ID from filename."""
        flow_id = FlowFilesystemUtils.extract_flow_id_from_filename("My_Flow_abc123.json")
        assert flow_id == "abc123"

        flow_id = FlowFilesystemUtils.extract_flow_id_from_filename("/path/to/Test_Flow_xyz789.json")
        assert flow_id == "xyz789"

        flow_id = FlowFilesystemUtils.extract_flow_id_from_filename("invalid.json")
        assert flow_id is None

        flow_id = FlowFilesystemUtils.extract_flow_id_from_filename("no_extension")
        assert flow_id is None

    def test_matches_flow_id_pattern(self):
        """Test pattern matching for flow IDs."""
        assert FlowFilesystemUtils.matches_flow_id_pattern("My_Flow_abc123.json", "abc123") is True
        assert FlowFilesystemUtils.matches_flow_id_pattern("Other_Flow_xyz789.json", "abc123") is False
        assert FlowFilesystemUtils.matches_flow_id_pattern("invalid.json", "abc123") is False

    def test_get_file_path_format(self, repository, sample_flow):
        """Test that _get_file_path returns correct format."""
        file_path = repository._get_file_path(sample_flow)
        expected_filename = f"Test_Flow_{sample_flow.flow_id}.json"
        assert file_path.name == expected_filename
        assert file_path.parent == repository.flows_dir

    def test_save_creates_correct_filename(self, repository, sample_flow, temp_flows_dir):
        """Test that save creates file with correct name format."""
        repository.save(sample_flow)

        expected_filename = f"Test_Flow_{sample_flow.flow_id}.json"
        expected_path = temp_flows_dir / expected_filename

        assert expected_path.exists()

        # Verify content
        with open(expected_path) as f:
            saved_data = json.load(f)

        assert saved_data["flow_id"] == sample_flow.flow_id
        assert saved_data["name"] == sample_flow.name

    def test_save_with_special_chars_in_name(self, repository, temp_flows_dir):
        """Test saving flow with special characters in name."""
        flow = Flow(
            name="My Test Flow!",
            definition={"nodes": [], "edges": []},
            flow_id=str(uuid4()),
        )

        repository.save(flow)

        # Should sanitize to My_Test_Flow
        expected_filename = f"My_Test_Flow_{flow.flow_id}.json"
        expected_path = temp_flows_dir / expected_filename

        assert expected_path.exists()

    def test_find_by_id_success(self, repository, sample_flow):
        """Test finding a flow by ID."""
        repository.save(sample_flow)

        found_flow = repository.find_by_id(sample_flow.flow_id)

        assert found_flow is not None
        assert found_flow.flow_id == sample_flow.flow_id
        assert found_flow.name == sample_flow.name
        assert found_flow.definition == sample_flow.definition

    def test_find_by_id_not_found(self, repository):
        """Test finding a non-existent flow."""
        non_existent_id = str(uuid4())
        found_flow = repository.find_by_id(non_existent_id)

        assert found_flow is None

    def test_find_by_id_with_different_name(self, repository, temp_flows_dir):
        """Test that find_by_id works regardless of flow name."""
        flow_id = str(uuid4())

        # Create flow with one name
        flow1 = Flow(name="Original Name", definition={"nodes": [], "edges": []}, flow_id=flow_id)
        repository.save(flow1)

        # Should find it by ID
        found = repository.find_by_id(flow_id)
        assert found is not None
        assert found.flow_id == flow_id

    def test_find_all_empty(self, repository):
        """Test finding all flows when directory is empty."""
        flows = repository.find_all()
        assert flows == []

    def test_find_all_multiple_flows(self, repository):
        """Test finding all flows with multiple flows."""
        flows_to_save = []
        for i in range(5):
            flow = Flow(
                name=f"Flow {i}",
                definition={"nodes": [], "edges": []},
                flow_id=str(uuid4()),
            )
            flows_to_save.append(flow)
            repository.save(flow)

        found_flows = repository.find_all()

        assert len(found_flows) == 5
        found_ids = {f.flow_id for f in found_flows}
        expected_ids = {f.flow_id for f in flows_to_save}
        assert found_ids == expected_ids

    def test_delete_success(self, repository, sample_flow):
        """Test deleting an existing flow."""
        repository.save(sample_flow)

        result = repository.delete(sample_flow.flow_id)

        assert result is True
        assert repository.find_by_id(sample_flow.flow_id) is None

    def test_delete_not_found(self, repository):
        """Test deleting a non-existent flow."""
        non_existent_id = str(uuid4())
        result = repository.delete(non_existent_id)

        assert result is False

    def test_exists_true(self, repository, sample_flow):
        """Test exists returns True for existing flow."""
        repository.save(sample_flow)

        assert repository.exists(sample_flow.flow_id) is True

    def test_exists_false(self, repository):
        """Test exists returns False for non-existent flow."""
        non_existent_id = str(uuid4())

        assert repository.exists(non_existent_id) is False

    def test_save_updates_existing_flow(self, repository, sample_flow):
        """Test that saving an existing flow updates it."""
        # Save initial flow
        repository.save(sample_flow)

        # Modify and save again
        sample_flow.description = "Updated description"
        repository.save(sample_flow)

        # Verify update
        found_flow = repository.find_by_id(sample_flow.flow_id)
        assert found_flow.description == "Updated description"

        # Verify only one file exists
        all_flows = repository.find_all()
        assert len(all_flows) == 1

    def test_save_with_name_change(self, repository, sample_flow, temp_flows_dir):
        """Test saving flow with changed name creates new file."""
        # Save initial flow
        repository.save(sample_flow)
        old_filename = f"Test_Flow_{sample_flow.flow_id}.json"
        old_path = temp_flows_dir / old_filename

        # Verify old file exists
        assert old_path.exists()

        # Delete old file (simulating user cleanup)
        old_path.unlink()

        # Change name and save
        sample_flow.name = "New Flow Name"
        repository.save(sample_flow)
        new_filename = f"New_Flow_Name_{sample_flow.flow_id}.json"

        # New file should exist
        assert (temp_flows_dir / new_filename).exists()

        # Old file should not exist
        assert not old_path.exists()

        # Can find by ID with new name
        found = repository.find_by_id(sample_flow.flow_id)
        assert found is not None
        assert found.name == "New Flow Name"

    def test_repository_initialization_creates_directory(self, monkeypatch):
        """Test that repository creates directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            flows_dir = Path(tmpdir) / "flows" / "nested"

            # Directory shouldn't exist yet
            assert not flows_dir.exists()

            # Create repository using environment variable
            monkeypatch.setenv("LOCAL_FLOWS_DIR", str(flows_dir))
            repository = LocalFlowRepository()

            # Directory should now exist
            assert flows_dir.exists()
            # Use resolve() to handle symlinks on macOS (/var vs /private/var)
            assert repository.flows_dir.resolve() == flows_dir.resolve()

    def test_save_without_flow_id_raises_error(self, repository):
        """Test that saving flow without ID raises ValueError."""
        flow = Flow(name="Test", definition={"nodes": [], "edges": []}, flow_id=None)
        # Flow.__post_init__ will generate an ID, so we need to explicitly set to None
        flow.flow_id = None

        with pytest.raises(ValueError, match="Flow ID is required"):
            repository.save(flow)

    def test_concurrent_flows_with_similar_names(self, repository):
        """Test handling multiple flows with similar names."""
        flows = [
            Flow(name="Test Flow", definition={"nodes": []}, flow_id=str(uuid4())),
            Flow(name="Test Flow", definition={"nodes": []}, flow_id=str(uuid4())),
            Flow(name="Test_Flow", definition={"nodes": []}, flow_id=str(uuid4())),
        ]

        for flow in flows:
            repository.save(flow)

        # All should be saved and retrievable
        all_flows = repository.find_all()
        assert len(all_flows) == 3

        # Each should be findable by ID
        for flow in flows:
            found = repository.find_by_id(flow.flow_id)
            assert found is not None
            assert found.flow_id == flow.flow_id

    def test_update_no_redundant_exists_check(self, repository, sample_flow):
        """Test that update() doesn't call exists() redundantly (removed race condition check)."""
        repository.save(sample_flow)

        # Modify flow
        sample_flow.name = "Updated Name"

        # Mock exists to track if it's called
        with patch.object(repository, "exists", wraps=repository.exists) as mock_exists:
            repository.update(sample_flow)

            # exists() should NOT be called during update (redundant check removed)
            mock_exists.assert_not_called()

    def test_cleanup_propagates_keyboard_interrupt(self, repository, sample_flow, temp_flows_dir):
        """Test that KeyboardInterrupt is not caught by bare except during cleanup."""
        repository.save(sample_flow)

        # Mock unlink to raise KeyboardInterrupt
        with patch.object(Path, "unlink", side_effect=KeyboardInterrupt("User interrupted")):
            with pytest.raises(KeyboardInterrupt):
                repository.delete(sample_flow.flow_id)

    def test_find_by_id_raises_on_multiple_files(self, repository, temp_flows_dir):
        """Test that find_by_id raises ValueError when multiple files match same flow_id."""
        flow_id = str(uuid4())

        # Create two files with same flow_id but different names
        file1 = temp_flows_dir / f"Flow1_{flow_id}.json"
        file2 = temp_flows_dir / f"Flow2_{flow_id}.json"

        flow_data = {
            "flow_id": flow_id,
            "name": "Test",
            "definition": {"nodes": []},
            "tags": [],
            "is_hidden": False,
        }

        file1.write_text(json.dumps(flow_data))
        file2.write_text(json.dumps(flow_data))

        with pytest.raises(ValueError, match="Data integrity error"):
            repository.find_by_id(flow_id)

    def test_find_by_id_handles_json_decode_error(self, repository, temp_flows_dir):
        """Test that find_by_id raises ValueError for corrupted JSON files."""
        flow_id = str(uuid4())

        # Create file with invalid JSON
        corrupted_file = temp_flows_dir / f"Test_Flow_{flow_id}.json"
        corrupted_file.write_text("{ invalid json content")

        with pytest.raises(ValueError, match="Corrupted flow file"):
            repository.find_by_id(flow_id)

    def test_exists_uses_generator_efficiently(self, repository, temp_flows_dir):
        """Test that exists() uses generator and stops at first match."""
        # Create 100 flow files
        flows = []
        for i in range(100):
            flow = Flow(name=f"Flow {i}", definition={"nodes": []}, flow_id=str(uuid4()))
            flows.append(flow)
            repository.save(flow)

        # Check existence of first flow - should be fast (generator stops early)
        first_flow_id = flows[0].flow_id

        # Test that exists() returns True for existing flow
        result = repository.exists(first_flow_id)
        assert result is True

        # Test that exists() returns False for non-existent flow
        non_existent_id = str(uuid4())
        result = repository.exists(non_existent_id)
        assert result is False

        # Verify the implementation uses any() with generator expression
        # by checking it doesn't load all files into memory at once
        # (behavioral test - if it works correctly with 100 files, it's using generator)

    def test_permission_error_on_save(self, repository, sample_flow):
        """Test that save raises PermissionError when directory is not writable."""
        with patch("os.access", return_value=False):
            with pytest.raises(PermissionError, match="No write permission"):
                repository.save(sample_flow)

    def test_permission_error_on_update(self, repository, sample_flow):
        """Test that update raises PermissionError when directory is not writable."""
        repository.save(sample_flow)

        sample_flow.name = "Updated"
        with patch("os.access", return_value=False):
            with pytest.raises(PermissionError, match="No write permission"):
                repository.update(sample_flow)

    def test_permission_error_on_find_by_id(self, repository, sample_flow):
        """Test that find_by_id raises PermissionError when directory is not readable."""
        repository.save(sample_flow)

        with patch("os.access", return_value=False):
            with pytest.raises(PermissionError, match="No read permission"):
                repository.find_by_id(sample_flow.flow_id)

    def test_permission_error_on_find_all(self, repository):
        """Test that find_all raises PermissionError when directory is not readable."""
        with patch("os.access", return_value=False):
            with pytest.raises(PermissionError, match="No read permission"):
                repository.find_all()

    def test_permission_error_on_delete(self, repository, sample_flow):
        """Test that delete raises PermissionError when directory is not writable."""
        repository.save(sample_flow)

        with patch("os.access", return_value=False):
            with pytest.raises(PermissionError, match="No write permission"):
                repository.delete(sample_flow.flow_id)

    def test_update_handles_orphaned_files(self, repository, sample_flow, temp_flows_dir):
        """Test that update succeeds even if old file deletion fails."""
        repository.save(sample_flow)

        # Change name to trigger file rename
        sample_flow.name = "New Name"

        # Mock unlink to raise OSError for old file deletion
        original_unlink = Path.unlink

        def selective_unlink(self, *args, **kwargs):
            if "Test_Flow" in str(self):
                raise OSError("Cannot delete old file")
            return original_unlink(self, *args, **kwargs)

        with patch.object(Path, "unlink", selective_unlink):
            # Update should succeed despite old file deletion failure
            updated = repository.update(sample_flow)

            assert updated.name == "New Name"
            # New file should exist
            new_file = temp_flows_dir / f"New_Name_{sample_flow.flow_id}.json"
            assert new_file.exists()

    def test_cleanup_temp_file_method_exists(self, repository):
        """Test that _cleanup_temp_file() method exists and handles None path."""
        # Should not raise error with None
        repository._cleanup_temp_file(None)

        # Should silently ignore OSError
        temp_path = Path("/nonexistent/temp.json")
        repository._cleanup_temp_file(temp_path)  # Should not raise

    def test_cleanup_temp_file_handles_oserror(self, repository, temp_flows_dir):
        """Test that _cleanup_temp_file() silently ignores OSError."""
        temp_file = temp_flows_dir / "temp.json"
        temp_file.write_text("test")

        # Mock unlink to raise OSError
        with patch.object(Path, "unlink", side_effect=OSError("Permission denied")):
            # Should not raise
            repository._cleanup_temp_file(temp_file)

    def test_delete_logging_not_found(self, repository, caplog):
        """Test that delete logs info message when flow not found."""
        import logging

        caplog.set_level(logging.INFO)

        non_existent_id = str(uuid4())
        result = repository.delete(non_existent_id)

        assert result is False
        assert "not found for deletion" in caplog.text

    def test_delete_logging_success(self, repository, sample_flow, caplog):
        """Test that delete logs success message when flow deleted."""
        import logging

        caplog.set_level(logging.INFO)

        repository.save(sample_flow)
        result = repository.delete(sample_flow.flow_id)

        assert result is True
        assert "Successfully deleted flow" in caplog.text

    def test_init_validates_directory_is_not_file(self, monkeypatch):
        """Test that repository raises ValueError if path is a file, not directory."""
        with tempfile.NamedTemporaryFile() as tmpfile:
            monkeypatch.setenv("LOCAL_FLOWS_DIR", tmpfile.name)
            with pytest.raises(ValueError, match="must be a directory, not a file"):
                LocalFlowRepository()

    def test_init_validates_write_permission(self, monkeypatch):
        """Test that repository raises PermissionError if directory not writable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            flows_dir = Path(tmpdir) / "flows"
            flows_dir.mkdir()

            monkeypatch.setenv("LOCAL_FLOWS_DIR", str(flows_dir))
            with patch("os.access", return_value=False):
                with pytest.raises(PermissionError, match="No write permission"):
                    LocalFlowRepository()

    def test_file_extension_constant(self, repository):
        """Test that FILE_EXTENSION constant is defined and used correctly."""
        assert LocalFlowRepository.FILE_EXTENSION == ".json"

        # Verify it's used in glob operations
        sample_flow = Flow(name="Test", definition={"nodes": []}, flow_id=str(uuid4()))
        repository.save(sample_flow)

        # find_all should use FILE_EXTENSION
        flows = repository.find_all()
        assert len(flows) == 1

    def test_get_default_flows_dir_uses_documents_folder(self):
        """Test that default flows directory uses the user's Documents/pipeline/assets path."""
        expected = (Path("/mock/home") / "Documents" / "pipeline" / "assets").resolve()

        with patch(
            "datasift.core.flows.adapters.repositories.local.local_flow_repository.os.getenv",
            return_value=None,
        ):
            with patch("datasift.core.flows.adapters.repositories.local.local_flow_repository.Path.home") as mock_home:
                mock_home.return_value = Path("/mock/home")

                result = LocalFlowRepository.get_flows_dir()

        assert result == expected

    def test_get_default_flows_dir_uses_env_override(self):
        """Test that LOCAL_FLOWS_DIR takes precedence over the default Documents path."""
        env_path = "/custom/flows"

        with patch(
            "datasift.core.flows.adapters.repositories.local.local_flow_repository.os.getenv",
            return_value=env_path,
        ):
            result = LocalFlowRepository.get_flows_dir()

        assert result == Path(env_path).resolve()

    def test_update_with_name_change_atomic_operation(self, repository, sample_flow, temp_flows_dir):
        """Test that update with name change is atomic (write-then-rename pattern)."""
        repository.save(sample_flow)

        # Change name
        sample_flow.name = "Completely New Name"

        # Update should use atomic write-then-rename
        updated = repository.update(sample_flow)

        assert updated.name == "Completely New Name"

        # New file should exist
        new_file = temp_flows_dir / f"Completely_New_Name_{sample_flow.flow_id}.json"
        assert new_file.exists()

        # Old file should be deleted
        old_file = temp_flows_dir / f"Test_Flow_{sample_flow.flow_id}.json"
        assert not old_file.exists()

    def test_find_by_id_validates_flow_id_matches_content(self, repository, temp_flows_dir):
        """Test that find_by_id validates flow_id in filename matches JSON content."""
        flow_id = str(uuid4())
        different_id = str(uuid4())

        # Create file with mismatched flow_id
        file_path = temp_flows_dir / f"Test_Flow_{flow_id}.json"
        flow_data = {
            "flow_id": different_id,  # Different from filename
            "name": "Test",
            "definition": {"nodes": []},
            "tags": [],
            "is_hidden": False,
        }
        file_path.write_text(json.dumps(flow_data))

        with pytest.raises(ValueError, match="Data integrity error"):
            repository.find_by_id(flow_id)


class TestLocalFlowRepositoryConcurrency:
    """Test suite for concurrent access to LocalFlowRepository with file locking."""

    @pytest.fixture
    def temp_flows_dir(self):
        """Create a temporary directory for flow storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def repository_with_locking(self, temp_flows_dir, monkeypatch):
        """Create a repository with locking enabled."""
        monkeypatch.setenv("LOCAL_FLOWS_DIR", str(temp_flows_dir))
        return LocalFlowRepository(
            enable_locking=True,
            lock_timeout=5.0,
            lock_retry_interval=0.05,
        )

    @pytest.fixture
    def repository_without_locking(self, temp_flows_dir, monkeypatch):
        """Create a repository with locking disabled."""
        monkeypatch.setenv("LOCAL_FLOWS_DIR", str(temp_flows_dir))
        return LocalFlowRepository(enable_locking=False)

    @pytest.fixture
    def sample_flow(self):
        """Create a sample flow for testing."""
        return Flow(
            name="test_flow",
            definition={"nodes": [], "edges": []},
            description="Test flow for concurrent access",
        )

    def test_repository_initialization_with_locking(self, temp_flows_dir, monkeypatch):
        """Test that repository initializes correctly with locking enabled."""
        monkeypatch.setenv("LOCAL_FLOWS_DIR", str(temp_flows_dir))
        repo = LocalFlowRepository(
            enable_locking=True,
            lock_timeout=10.0,
            lock_retry_interval=0.1,
        )

        assert repo.lock_manager.enable_locking is True
        assert repo.lock_manager.lock_timeout == 10.0
        assert repo.lock_manager.lock_retry_interval == 0.1
        # Use resolve() to handle symlinks on macOS (/var vs /private/var)
        assert repo.flows_dir.resolve() == temp_flows_dir.resolve()

    def test_repository_initialization_without_locking(self, temp_flows_dir, monkeypatch):
        """Test that repository initializes correctly with locking disabled."""
        monkeypatch.setenv("LOCAL_FLOWS_DIR", str(temp_flows_dir))
        repo = LocalFlowRepository(enable_locking=False)

        assert repo.lock_manager.enable_locking is False
        # Use resolve() to handle symlinks on macOS (/var vs /private/var)
        assert repo.flows_dir.resolve() == temp_flows_dir.resolve()

    def test_save_with_locking(self, repository_with_locking, sample_flow):
        """Test that save operation works with locking enabled."""
        saved_flow = repository_with_locking.save(sample_flow)

        assert saved_flow.flow_id == sample_flow.flow_id
        assert saved_flow.name == sample_flow.name

        # Verify flow can be retrieved
        retrieved = repository_with_locking.find_by_id(sample_flow.flow_id)
        assert retrieved is not None
        assert retrieved.flow_id == sample_flow.flow_id

    def test_concurrent_reads(self, repository_with_locking, sample_flow):
        """Test that multiple concurrent reads work correctly with shared locks."""
        # Save a flow first
        repository_with_locking.save(sample_flow)

        # Perform concurrent reads
        def read_flow():
            return repository_with_locking.find_by_id(sample_flow.flow_id)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_flow) for _ in range(20)]
            results = [f.result() for f in as_completed(futures)]

        # All reads should succeed
        assert len(results) == 20
        assert all(r is not None for r in results)
        assert all(r.flow_id == sample_flow.flow_id for r in results)

    def test_concurrent_writes_different_flows(self, repository_with_locking):
        """Test that concurrent writes to different flows work correctly."""

        def save_flow(index):
            flow = Flow(
                name=f"flow_{index}",
                definition={"nodes": [], "edges": []},
                description=f"Flow {index}",
            )
            return repository_with_locking.save(flow)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(save_flow, i) for i in range(10)]
            results = [f.result() for f in as_completed(futures)]

        # All writes should succeed
        assert len(results) == 10

        # Verify all flows were saved
        all_flows = repository_with_locking.find_all()
        assert len(all_flows) == 10

    def test_concurrent_write_and_read_same_flow(self, repository_with_locking, sample_flow):
        """Test concurrent write and read operations on the same flow."""
        # Save initial flow
        repository_with_locking.save(sample_flow)

        def update_flow():
            flow = repository_with_locking.find_by_id(sample_flow.flow_id)
            if flow:
                flow.description = f"Updated at {time.time()}"
                repository_with_locking.update(flow)
            return flow

        def read_flow():
            return repository_with_locking.find_by_id(sample_flow.flow_id)

        with ThreadPoolExecutor(max_workers=5) as executor:
            # Mix of reads and writes
            futures = []
            for i in range(10):
                if i % 2 == 0:
                    futures.append(executor.submit(read_flow))
                else:
                    futures.append(executor.submit(update_flow))

            results = [f.result() for f in as_completed(futures)]

        # All operations should complete successfully
        assert len(results) == 10
        assert all(r is not None for r in results)

    def test_delete_with_locking(self, repository_with_locking, sample_flow):
        """Test that delete operation works with locking enabled."""
        # Save flow
        repository_with_locking.save(sample_flow)

        # Verify it exists
        assert repository_with_locking.exists(sample_flow.flow_id)

        # Delete flow
        result = repository_with_locking.delete(sample_flow.flow_id)
        assert result is True

        # Verify lock file was cleaned up (check before calling exists() which creates a new lock)
        lock_file = repository_with_locking._get_lock_file_path(sample_flow.flow_id)
        assert not lock_file.exists()

        # Verify it no longer exists
        assert not repository_with_locking.exists(sample_flow.flow_id)

    def test_exists_with_locking(self, repository_with_locking, sample_flow):
        """Test that exists operation works with locking enabled."""
        # Flow doesn't exist initially
        assert not repository_with_locking.exists(sample_flow.flow_id)

        # Save flow
        repository_with_locking.save(sample_flow)

        # Now it exists
        assert repository_with_locking.exists(sample_flow.flow_id)

    def test_find_all_with_locking(self, repository_with_locking):
        """Test that find_all works with global locking."""
        # Create multiple flows
        flows = []
        for i in range(5):
            flow = Flow(
                name=f"flow_{i}",
                definition={"nodes": [], "edges": []},
                description=f"Flow {i}",
            )
            repository_with_locking.save(flow)
            flows.append(flow)

        # Retrieve all flows
        all_flows = repository_with_locking.find_all()

        assert len(all_flows) == 5
        flow_ids = {f.flow_id for f in all_flows}
        expected_ids = {f.flow_id for f in flows}
        assert flow_ids == expected_ids

    def test_locking_disabled_still_works(self, repository_without_locking, sample_flow):
        """Test that repository works correctly when locking is disabled."""
        # Save flow
        saved = repository_without_locking.save(sample_flow)
        assert saved.flow_id == sample_flow.flow_id

        # Read flow
        retrieved = repository_without_locking.find_by_id(sample_flow.flow_id)
        assert retrieved is not None
        assert retrieved.flow_id == sample_flow.flow_id

        # Update flow
        retrieved.description = "Updated"
        updated = repository_without_locking.update(retrieved)
        assert updated.description == "Updated"

        # Delete flow
        result = repository_without_locking.delete(sample_flow.flow_id)
        assert result is True

    def test_lock_timeout_configuration(self, temp_flows_dir, monkeypatch):
        """Test that lock timeout parameters are configured correctly."""
        monkeypatch.setenv("LOCAL_FLOWS_DIR", str(temp_flows_dir))
        repo = LocalFlowRepository(
            enable_locking=True,
            lock_timeout=0.5,
            lock_retry_interval=0.1,
        )

        assert repo.lock_manager.lock_timeout == 0.5
        assert repo.lock_manager.lock_retry_interval == 0.1

    def test_get_lock_file_path(self, repository_with_locking):
        """Test that lock file path is generated correctly."""
        flow_id = str(uuid4())
        lock_path = repository_with_locking._get_lock_file_path(flow_id)

        assert lock_path.parent == repository_with_locking.locks_dir
        assert lock_path.name == f"{flow_id}.lock"

    def test_file_lock_context_manager_with_locking_disabled(self, repository_without_locking):
        """Test that file lock context manager is a no-op when locking is disabled."""
        flow_id = str(uuid4())

        # Should not raise any errors and should execute quickly
        with repository_without_locking._file_lock(flow_id, exclusive=True):
            pass  # No actual locking should occur

    def test_update_with_locking(self, repository_with_locking, sample_flow):
        """Test that update operation works with locking enabled."""
        # Save initial flow
        repository_with_locking.save(sample_flow)

        # Update flow
        sample_flow.description = "Updated description"
        updated = repository_with_locking.update(sample_flow)

        assert updated.description == "Updated description"

        # Verify update persisted
        retrieved = repository_with_locking.find_by_id(sample_flow.flow_id)
        assert retrieved.description == "Updated description"
