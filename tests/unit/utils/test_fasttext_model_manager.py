"""Unit tests for FastTextModelManager."""

from unittest.mock import MagicMock, Mock, patch

import pytest


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the FastTextModelManager singleton between tests."""
    from docpipe.utils.infrastructure.fasttext_model_manager import FastTextModelManager

    # Save old state
    old_instance = FastTextModelManager._instance
    yield
    # Reset singleton
    FastTextModelManager._instance = old_instance


def make_manager():
    from docpipe.utils.infrastructure.fasttext_model_manager import FastTextModelManager

    # Reset singleton so each test gets a fresh one
    FastTextModelManager._instance = None
    return FastTextModelManager()


@pytest.mark.unit
class TestFastTextModelManagerInit:
    def test_singleton_returns_same_instance(self):
        from docpipe.utils.infrastructure.fasttext_model_manager import FastTextModelManager

        FastTextModelManager._instance = None
        m1 = FastTextModelManager()
        m2 = FastTextModelManager()
        assert m1 is m2

    def test_initial_state(self):
        mgr = make_manager()
        assert mgr._model is None
        assert mgr._ref_count == 0
        assert mgr._load_failed is False


@pytest.mark.unit
class TestDownloadModel:
    def test_skips_download_if_model_exists(self, tmp_path):
        mgr = make_manager()
        model_path = tmp_path / "model.ftz"
        model_path.write_bytes(b"fake model")

        # Should not call urlretrieve if file exists
        with patch("urllib.request.urlretrieve") as mock_dl:
            mgr._download_model(model_path)
            mock_dl.assert_not_called()

    def test_downloads_model_when_not_present(self, tmp_path):
        mgr = make_manager()
        model_path = tmp_path / "model.ftz"

        with patch("urllib.request.urlretrieve") as mock_dl:
            mgr._download_model(model_path)
            mock_dl.assert_called_once()

    def test_falls_back_to_ssl_unverified_on_ssl_error(self, tmp_path):
        import ssl

        mgr = make_manager()
        model_path = tmp_path / "model.ftz"

        mock_response = MagicMock()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_response.read.return_value = b"model data"

        with patch("urllib.request.urlretrieve", side_effect=ssl.SSLError("ssl fail")):
            with patch("urllib.request.urlopen", return_value=mock_response):
                mgr._download_model(model_path)
        assert model_path.read_bytes() == b"model data"

    def test_raises_runtime_error_on_download_failure(self, tmp_path):
        mgr = make_manager()
        model_path = tmp_path / "no_such_model.ftz"

        with patch("urllib.request.urlretrieve", side_effect=Exception("network error")):
            with pytest.raises(RuntimeError, match="Download failed"):
                mgr._download_model(model_path)


@pytest.mark.unit
class TestLoadModel:
    def test_load_model_success(self, tmp_path):
        mgr = make_manager()
        mgr._model_path = tmp_path / "model.ftz"
        (mgr._model_path).write_bytes(b"fake model")

        mock_ft = MagicMock()
        mock_fasttext_module = MagicMock()
        mock_fasttext_module.load_model.return_value = mock_ft

        with patch.dict("sys.modules", {"fasttext": mock_fasttext_module}):
            mgr._load_model()

        assert mgr._model is mock_ft
        assert mgr._load_failed is False

    def test_load_model_skips_if_already_loaded(self):
        mgr = make_manager()
        existing_model = MagicMock()
        mgr._model = existing_model

        # Should not try to load again
        with patch("builtins.__import__") as mock_import:
            mgr._load_model()
            mock_import.assert_not_called()

        assert mgr._model is existing_model

    def test_load_model_failure_sets_load_failed(self, tmp_path):
        mgr = make_manager()
        mgr._model_path = tmp_path / "model.ftz"
        (mgr._model_path).write_bytes(b"fake")

        mock_fasttext_module = MagicMock()
        mock_fasttext_module.load_model.side_effect = RuntimeError("bad model")

        with patch.dict("sys.modules", {"fasttext": mock_fasttext_module}):
            with pytest.raises(RuntimeError, match="Failed to load"):
                mgr._load_model()

        assert mgr._load_failed is True
        assert mgr._model is None


@pytest.mark.unit
class TestAcquireAndRelease:
    def test_acquire_model_increments_ref_count(self):
        mgr = make_manager()
        mock_model = MagicMock()

        with patch.object(mgr, "_load_model"):
            mgr._model = mock_model
            result = mgr.acquire_model()

        assert mgr._ref_count == 1
        assert result is mock_model

    def test_acquire_model_raises_if_load_previously_failed(self):
        mgr = make_manager()
        mgr._load_failed = True
        mgr._load_error = RuntimeError("prev error")

        with pytest.raises(RuntimeError, match="previously failed"):
            mgr.acquire_model()

    def test_acquire_model_lock_timeout_raises(self):
        mgr = make_manager()
        mgr._model_lock.acquire()  # Hold lock forever
        try:
            with pytest.raises(RuntimeError, match="Failed to acquire"):
                mgr.acquire_model(timeout=0.01)
        finally:
            mgr._model_lock.release()

    def test_release_model_decrements_ref_count(self):
        mgr = make_manager()
        mgr._ref_count = 2
        mgr._model = MagicMock()

        mgr.release_model()

        assert mgr._ref_count == 1
        assert mgr._model is not None  # Not unloaded yet

    def test_release_model_unloads_at_zero(self):
        mgr = make_manager()
        mgr._ref_count = 1
        mgr._model = MagicMock()

        mgr.release_model()

        assert mgr._ref_count == 0
        assert mgr._model is None

    def test_release_model_zero_ref_count_warns(self):
        mgr = make_manager()
        mgr._ref_count = 0
        # Should not raise, just log warning
        mgr.release_model()
        assert mgr._ref_count == 0

    def test_release_model_lock_timeout_raises(self):
        mgr = make_manager()
        mgr._model_lock.acquire()
        try:
            with pytest.raises(RuntimeError, match="Failed to acquire"):
                mgr.release_model(timeout=0.01)
        finally:
            mgr._model_lock.release()
