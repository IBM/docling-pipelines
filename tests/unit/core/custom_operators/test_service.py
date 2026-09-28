"""Unit tests for CustomOperatorService."""

import uuid
from pathlib import Path

import pytest

from docpipe.core.custom_operators.file_store import LocalFileStore
from docpipe.core.custom_operators.models import CustomOperatorStatus
from docpipe.core.custom_operators.service import CustomOperatorService
from docpipe.exceptions.docpipe_exceptions import (
    CustomOperatorAlreadyExistsException,
    CustomOperatorInvalidDataException,
    CustomOperatorNotFoundException,
)
from docpipe.storage.file_system.key_value_file_system_storage import KeyValueFileSystemStorage

SAMPLE_OP_CODE = """
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
import pyarrow as pa

class SampleCustomOperator(AbstractOperator):
    short_name = "sample_custom_op"
    category = OperatorCategory.Quality
    owner = "custom"

    def transform(self, table: pa.Table):
        return [table], {}

    @staticmethod
    def get_metadata():
        return {"short_name": "sample_custom_op"}
"""


@pytest.fixture
def custom_operator_service(tmp_path: Path) -> CustomOperatorService:
    """Fixture providing an isolated CustomOperatorService."""
    file_store = LocalFileStore(base_dir=tmp_path / "custom_operators")
    metadata_storage = KeyValueFileSystemStorage(base_dir=tmp_path)
    return CustomOperatorService(file_store=file_store, metadata_storage=metadata_storage)


class TestCustomOperatorServiceCreate:
    """Test suite for create_operator."""

    def test_create_operator_success(self, *, custom_operator_service: CustomOperatorService, tmp_path: Path) -> None:
        """Test creating a valid custom operator."""
        op_file = tmp_path / "sample_op.py"
        op_file.write_text(SAMPLE_OP_CODE, encoding="utf-8")

        operator = custom_operator_service.create_operator(
            name="Sample Custom Operator",
            description="A sample test operator",
            operator_file_path=op_file,
        )

        assert operator.id is not None
        assert operator.name == "Sample Custom Operator"
        assert operator.short_name == "sample_custom_op"
        assert operator.status == CustomOperatorStatus.VALIDATED
        assert operator.created_at is not None
        assert operator.metadata["category"] == "Quality"

    def test_create_operator_duplicate_short_name_raises_conflict(
        self, *, custom_operator_service: CustomOperatorService, tmp_path: Path
    ) -> None:
        """Test duplicate short_name raises CustomOperatorAlreadyExistsException."""
        op_file = tmp_path / "sample_op.py"
        op_file.write_text(SAMPLE_OP_CODE, encoding="utf-8")

        custom_operator_service.create_operator(
            name="Op 1",
            description="First operator",
            operator_file_path=op_file,
        )

        with pytest.raises(CustomOperatorAlreadyExistsException, match="already exists"):
            custom_operator_service.create_operator(
                name="Op 2",
                description="Second operator with same short_name",
                operator_file_path=op_file,
            )

    def test_create_operator_empty_name_raises_exception(
        self, *, custom_operator_service: CustomOperatorService, tmp_path: Path
    ) -> None:
        """Test empty name raises CustomOperatorInvalidDataException."""
        op_file = tmp_path / "sample_op.py"
        op_file.write_text(SAMPLE_OP_CODE, encoding="utf-8")

        with pytest.raises(CustomOperatorInvalidDataException, match="Operator name cannot be empty"):
            custom_operator_service.create_operator(
                name="   ",
                description="desc",
                operator_file_path=op_file,
            )


class TestCustomOperatorServiceGetAndList:
    """Test suite for get_operator and list_operators."""

    def test_get_operator_by_id(self, *, custom_operator_service: CustomOperatorService, tmp_path: Path) -> None:
        """Test retrieving custom operator by valid UUID."""
        op_file = tmp_path / "sample_op.py"
        op_file.write_text(SAMPLE_OP_CODE, encoding="utf-8")

        created = custom_operator_service.create_operator(
            name="Sample Op",
            description="desc",
            operator_file_path=op_file,
        )
        assert created.id is not None

        retrieved = custom_operator_service.get_operator(operator_id=created.id)
        assert retrieved.id == created.id
        assert retrieved.short_name == created.short_name

    def test_get_operator_invalid_uuid_raises_exception(
        self, *, custom_operator_service: CustomOperatorService
    ) -> None:
        """Test malformed UUID raises CustomOperatorInvalidDataException."""
        with pytest.raises(CustomOperatorInvalidDataException, match="must be a valid UUID v4"):
            custom_operator_service.get_operator(operator_id="invalid-uuid-123")

    def test_get_operator_nonexistent_uuid_raises_not_found(
        self, *, custom_operator_service: CustomOperatorService
    ) -> None:
        """Test non-existent UUID raises CustomOperatorNotFoundException."""
        random_uuid = str(uuid.uuid4())
        with pytest.raises(CustomOperatorNotFoundException, match="not found"):
            custom_operator_service.get_operator(operator_id=random_uuid)

    def test_list_operators_marks_missing_file_as_invalid(
        self, *, custom_operator_service: CustomOperatorService, tmp_path: Path
    ) -> None:
        """Test list_operators consistency check when operator file was deleted from disk."""
        op_file = tmp_path / "sample_op.py"
        op_file.write_text(SAMPLE_OP_CODE, encoding="utf-8")

        created = custom_operator_service.create_operator(
            name="Sample Op",
            description="desc",
            operator_file_path=op_file,
        )
        assert created.id is not None

        # Manually delete file directory from disk to simulate external deletion
        custom_operator_service.file_store.delete(operator_id=created.id)

        operators = custom_operator_service.list_operators()
        assert len(operators) == 1
        assert operators[0].status == CustomOperatorStatus.INVALID
        assert "not found on disk" in operators[0].message


class TestCustomOperatorServiceUpdate:
    """Test suite for update_operator."""

    def test_update_metadata_only(self, *, custom_operator_service: CustomOperatorService, tmp_path: Path) -> None:
        """Test updating name and description without replacing file."""
        op_file = tmp_path / "sample_op.py"
        op_file.write_text(SAMPLE_OP_CODE, encoding="utf-8")

        created = custom_operator_service.create_operator(
            name="Original Name",
            description="Original Desc",
            operator_file_path=op_file,
        )
        assert created.id is not None

        updated = custom_operator_service.update_operator(
            operator_id=created.id,
            name="Updated Name",
            description="Updated Desc",
        )
        assert updated.name == "Updated Name"
        assert updated.description == "Updated Desc"
        assert updated.short_name == created.short_name

    def test_update_with_file_replacement(
        self, *, custom_operator_service: CustomOperatorService, tmp_path: Path
    ) -> None:
        """Test replacing operator file with same short_name."""
        op_file1 = tmp_path / "sample_op_v1.py"
        op_file1.write_text(SAMPLE_OP_CODE, encoding="utf-8")

        created = custom_operator_service.create_operator(
            name="Original Name",
            description="Original Desc",
            operator_file_path=op_file1,
        )
        assert created.id is not None

        # Create updated file with same short_name
        op_file2 = tmp_path / "sample_op_v2.py"
        op_file2.write_text(SAMPLE_OP_CODE.replace("Quality", "Extract"), encoding="utf-8")

        updated = custom_operator_service.update_operator(
            operator_id=created.id,
            operator_file_path=op_file2,
        )
        assert updated.operator_file == "sample_op_v2.py"
        assert updated.metadata["category"] == "Extract"

    def test_update_file_with_different_short_name_raises_exception(
        self, *, custom_operator_service: CustomOperatorService, tmp_path: Path
    ) -> None:
        """Test attempting to change short_name via update raises CustomOperatorInvalidDataException."""
        op_file1 = tmp_path / "sample_op_v1.py"
        op_file1.write_text(SAMPLE_OP_CODE, encoding="utf-8")

        created = custom_operator_service.create_operator(
            name="Original Name",
            description="Original Desc",
            operator_file_path=op_file1,
        )
        assert created.id is not None

        # Create updated file with different short_name
        op_file2 = tmp_path / "sample_op_v2.py"
        op_file2.write_text(SAMPLE_OP_CODE.replace("sample_custom_op", "different_op"), encoding="utf-8")

        with pytest.raises(CustomOperatorInvalidDataException, match="Cannot change short_name"):
            custom_operator_service.update_operator(
                operator_id=created.id,
                operator_file_path=op_file2,
            )


class TestCustomOperatorServiceDelete:
    """Test suite for delete_operator."""

    def test_delete_operator_success(self, *, custom_operator_service: CustomOperatorService, tmp_path: Path) -> None:
        """Test deleting operator removes both metadata and files."""
        op_file = tmp_path / "sample_op.py"
        op_file.write_text(SAMPLE_OP_CODE, encoding="utf-8")

        created = custom_operator_service.create_operator(
            name="Op to Delete",
            description="desc",
            operator_file_path=op_file,
        )
        assert created.id is not None

        custom_operator_service.delete_operator(operator_id=created.id)

        with pytest.raises(CustomOperatorNotFoundException):
            custom_operator_service.get_operator(operator_id=created.id)

        assert custom_operator_service.file_store.get_operator_dir(operator_id=created.id) is None
