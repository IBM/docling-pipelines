"""Unit tests for AttachmentRepositoryFactory.

Coverage:
- register() — stores adapter and metadata; overwrites on duplicate name
- create() — happy path, unknown adapter, invalid config, adapter.create() failure
- list_adapters() — returns metadata for all registered adapters
- get_adapter_info() — returns metadata for a known adapter; raises for unknown
"""

import pytest

from docpipe.core.assets.common.domain.models.attachment_ref import AttachmentRef
from docpipe.core.assets.common.domain.ports.attachment_repository import AttachmentRepository
from docpipe.core.assets.common.factories.attachment_repository_factory import AttachmentRepositoryFactory
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode

# ---------------------------------------------------------------------------
# Helpers — minimal stub adapter that never touches real storage
# ---------------------------------------------------------------------------


class _StubAttachmentRepository(AttachmentRepository):
    """Minimal in-memory stub used only within this test module."""

    def __init__(self, *, config: dict) -> None:
        self._config = config

    def save(self, *, asset_id: str, data: AttachmentRef) -> None:
        pass

    def get(self, *, asset_id: str) -> AttachmentRef | None:
        return None

    def delete(self, *, asset_id: str) -> bool:
        return False

    def exists(self, *, asset_id: str) -> bool:
        return False

    @classmethod
    def validate_config(cls, *, config: dict) -> list[str]:
        errors = []
        if "database_path" not in config:
            errors.append("Missing required configuration: 'database_path'")
        return errors

    @classmethod
    def create(cls, *, config: dict) -> "_StubAttachmentRepository":
        return cls(config=config)


class _FailingAttachmentRepository(_StubAttachmentRepository):
    """Stub whose create() always raises a plain RuntimeError."""

    @classmethod
    def create(cls, *, config: dict) -> "_FailingAttachmentRepository":
        raise RuntimeError("storage backend unavailable")


class _DocpipeFailingAttachmentRepository(_StubAttachmentRepository):
    """Stub whose create() always raises a DocpipeException."""

    @classmethod
    def create(cls, *, config: dict) -> "_DocpipeFailingAttachmentRepository":
        raise DocpipeException("adapter initialisation failed", status_code=503)


# ---------------------------------------------------------------------------
# Fixture — isolate registry mutations so tests don't bleed into each other
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_registry():
    """Snapshot and restore the class-level registry after each test.

    AttachmentRepositoryFactory uses ClassVar dicts that persist across tests.
    Saving/restoring the snapshot means stub adapters registered during a test
    are invisible to every other test, including the real 'duckdb' adapter.
    """
    adapters_snapshot = dict(AttachmentRepositoryFactory._adapters)
    metadata_snapshot = dict(AttachmentRepositoryFactory._adapter_metadata)
    yield
    AttachmentRepositoryFactory._adapters = adapters_snapshot
    AttachmentRepositoryFactory._adapter_metadata = metadata_snapshot


@pytest.fixture
def registered_stub():
    """Register a working stub adapter and return its name."""
    AttachmentRepositoryFactory._adapters["stub"] = _StubAttachmentRepository
    AttachmentRepositoryFactory._adapter_metadata["stub"] = {
        "name": "stub",
        "display_name": "Stub",
        "class": _StubAttachmentRepository.__name__,
    }
    return "stub"


# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------


class TestRegister:
    """register() is a decorator that populates _adapters and _adapter_metadata."""

    def test_register_adds_adapter_to_registry(self):
        @AttachmentRepositoryFactory.register(name="test_adapter", display_name="Test Adapter")
        class _LocalStub(_StubAttachmentRepository):
            pass

        assert "test_adapter" in AttachmentRepositoryFactory._adapters
        assert AttachmentRepositoryFactory._adapters["test_adapter"] is _LocalStub

    def test_register_stores_metadata(self):
        @AttachmentRepositoryFactory.register(name="meta_adapter", display_name="Meta Adapter")
        class _LocalStub(_StubAttachmentRepository):
            pass

        meta = AttachmentRepositoryFactory._adapter_metadata["meta_adapter"]
        assert meta["name"] == "meta_adapter"
        assert meta["display_name"] == "Meta Adapter"
        assert meta["class"] == "_LocalStub"

    def test_register_returns_the_original_class(self):
        """The decorator must return the class unchanged so it can still be used directly."""

        @AttachmentRepositoryFactory.register(name="passthrough_adapter", display_name="Passthrough")
        class _LocalStub(_StubAttachmentRepository):
            pass

        assert _LocalStub.__name__ == "_LocalStub"
        assert issubclass(_LocalStub, AttachmentRepository)

    def test_register_overwrites_duplicate_name(self):
        @AttachmentRepositoryFactory.register(name="dup_adapter", display_name="First")
        class _First(_StubAttachmentRepository):
            pass

        @AttachmentRepositoryFactory.register(name="dup_adapter", display_name="Second")
        class _Second(_StubAttachmentRepository):
            pass

        assert AttachmentRepositoryFactory._adapters["dup_adapter"] is _Second
        assert AttachmentRepositoryFactory._adapter_metadata["dup_adapter"]["display_name"] == "Second"


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


class TestCreate:
    """create() resolves the adapter, validates config, and delegates instantiation."""

    def test_create_returns_adapter_instance(self, registered_stub):
        result = AttachmentRepositoryFactory.create(adapter_name=registered_stub, config={"database_path": "test.db"})
        assert isinstance(result, _StubAttachmentRepository)

    def test_create_unknown_adapter_raises_docpipe_exception(self):
        with pytest.raises(DocpipeException) as exc_info:
            AttachmentRepositoryFactory.create(adapter_name="nonexistent", config={})

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == ErrorCode.OPERATOR_CONFIGURATION_INVALID
        assert "nonexistent" in str(exc_info.value)

    def test_create_unknown_adapter_error_lists_available_adapters(self, registered_stub):
        with pytest.raises(DocpipeException) as exc_info:
            AttachmentRepositoryFactory.create(adapter_name="nonexistent", config={})

        assert registered_stub in str(exc_info.value)

    def test_create_invalid_config_raises_docpipe_exception(self, registered_stub):
        """validate_config() returning errors must block instantiation."""
        with pytest.raises(DocpipeException) as exc_info:
            AttachmentRepositoryFactory.create(adapter_name=registered_stub, config={})  # missing database_path

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == ErrorCode.OPERATOR_CONFIGURATION_INVALID
        assert "database_path" in str(exc_info.value)

    def test_create_wraps_unexpected_adapter_exception(self):
        AttachmentRepositoryFactory._adapters["failing"] = _FailingAttachmentRepository
        AttachmentRepositoryFactory._adapter_metadata["failing"] = {
            "name": "failing",
            "display_name": "Failing",
            "class": _FailingAttachmentRepository.__name__,
        }

        with pytest.raises(DocpipeException) as exc_info:
            AttachmentRepositoryFactory.create(adapter_name="failing", config={"database_path": "test.db"})

        assert exc_info.value.status_code == 500
        assert "storage backend unavailable" in str(exc_info.value)

    def test_create_reraises_docpipe_exception_from_adapter_unchanged(self):
        AttachmentRepositoryFactory._adapters["docpipe_failing"] = _DocpipeFailingAttachmentRepository
        AttachmentRepositoryFactory._adapter_metadata["docpipe_failing"] = {
            "name": "docpipe_failing",
            "display_name": "Docpipe Failing",
            "class": _DocpipeFailingAttachmentRepository.__name__,
        }

        with pytest.raises(DocpipeException) as exc_info:
            AttachmentRepositoryFactory.create(adapter_name="docpipe_failing", config={"database_path": "test.db"})

        assert exc_info.value.status_code == 503
        assert "adapter initialisation failed" in str(exc_info.value)

    def test_create_with_no_registered_adapters_mentions_none_in_error(self):
        """When the registry is empty the error message says 'none'."""
        AttachmentRepositoryFactory._adapters.clear()
        AttachmentRepositoryFactory._adapter_metadata.clear()

        with pytest.raises(DocpipeException) as exc_info:
            AttachmentRepositoryFactory.create(adapter_name="anything", config={})

        assert "none" in str(exc_info.value)


# ---------------------------------------------------------------------------
# list_adapters()
# ---------------------------------------------------------------------------


class TestListAdapters:
    """list_adapters() returns metadata dicts for every registered adapter."""

    def test_list_adapters_includes_registered_adapter(self, registered_stub):
        adapters = AttachmentRepositoryFactory.list_adapters()
        names = [a["name"] for a in adapters]
        assert registered_stub in names

    def test_list_adapters_returns_correct_metadata_shape(self, registered_stub):
        adapters = AttachmentRepositoryFactory.list_adapters()
        stub_meta = next(a for a in adapters if a["name"] == registered_stub)

        assert "name" in stub_meta
        assert "display_name" in stub_meta
        assert "class" in stub_meta

    def test_list_adapters_returns_empty_list_when_registry_is_empty(self):
        AttachmentRepositoryFactory._adapters.clear()
        AttachmentRepositoryFactory._adapter_metadata.clear()

        assert AttachmentRepositoryFactory.list_adapters() == []

    def test_list_adapters_returns_copy_not_the_live_dict(self, registered_stub):
        """Mutations to the returned list must not affect the internal registry."""
        result = AttachmentRepositoryFactory.list_adapters()
        result.clear()

        assert len(AttachmentRepositoryFactory.list_adapters()) > 0

    def test_list_adapters_includes_duckdb_when_adapter_is_imported(self):
        """Importing the DuckDB adapter auto-registers it via @register."""
        import docpipe.core.assets.common.adapters.repositories.duckdb_attachment_repository  # noqa: F401

        names = [a["name"] for a in AttachmentRepositoryFactory.list_adapters()]
        assert "duckdb" in names


# ---------------------------------------------------------------------------
# get_adapter_info()
# ---------------------------------------------------------------------------


class TestGetAdapterInfo:
    """get_adapter_info() returns a copy of the metadata dict for one adapter."""

    def test_get_adapter_info_returns_correct_metadata(self, registered_stub):
        info = AttachmentRepositoryFactory.get_adapter_info(adapter_name=registered_stub)

        assert info["name"] == registered_stub
        assert info["display_name"] == "Stub"
        assert info["class"] == _StubAttachmentRepository.__name__

    def test_get_adapter_info_raises_for_unknown_adapter(self):
        with pytest.raises(DocpipeException) as exc_info:
            AttachmentRepositoryFactory.get_adapter_info(adapter_name="nonexistent")

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == ErrorCode.OPERATOR_CONFIGURATION_INVALID
        assert "nonexistent" in str(exc_info.value)

    def test_get_adapter_info_returns_copy(self, registered_stub):
        """Mutations to the returned dict must not affect the internal registry."""
        info = AttachmentRepositoryFactory.get_adapter_info(adapter_name=registered_stub)
        info["display_name"] = "mutated"

        fresh = AttachmentRepositoryFactory.get_adapter_info(adapter_name=registered_stub)
        assert fresh["display_name"] == "Stub"

    def test_get_adapter_info_with_empty_registry_mentions_none(self):
        AttachmentRepositoryFactory._adapters.clear()
        AttachmentRepositoryFactory._adapter_metadata.clear()

        with pytest.raises(DocpipeException) as exc_info:
            AttachmentRepositoryFactory.get_adapter_info(adapter_name="anything")

        assert "none" in str(exc_info.value)
