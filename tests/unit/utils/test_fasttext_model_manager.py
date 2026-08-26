"""Unit tests for FastTextModelManager._download_model().

All network I/O is mocked — no real HTTP or disk operations.
"""

import ssl
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestFastTextModelManagerDownload:
    """Tests for _download_model covering SSL fallback paths."""

    def _make_manager(self):
        """Import and construct FastTextModelManager with a mocked load path."""
        import sys
        from unittest.mock import Mock

        # Pre-mock fasttext to avoid import error in environments without it
        if "fasttext" not in sys.modules:
            sys.modules["fasttext"] = Mock()

        from docpipe.utils.infrastructure.fasttext_model_manager import FastTextModelManager

        return FastTextModelManager()

    def test_download_skips_when_model_already_exists(self, tmp_path):
        """If the model file already exists, download is skipped."""
        model_path = tmp_path / "model.bin"
        model_path.touch()  # create the file

        manager = self._make_manager()

        with patch("urllib.request.urlretrieve") as mock_retrieve:
            manager._download_model(model_path=model_path)
            mock_retrieve.assert_not_called()

    def test_download_uses_urlretrieve_with_ssl(self, tmp_path):
        """Happy path: urlretrieve succeeds on first attempt."""
        model_path = tmp_path / "model.bin"

        manager = self._make_manager()

        with patch("urllib.request.urlretrieve") as mock_retrieve:
            mock_retrieve.side_effect = lambda url, path: Path(path).touch()
            manager._download_model(model_path=model_path)
            mock_retrieve.assert_called_once()

    def test_download_falls_back_to_unverified_ssl_on_ssl_error(self, tmp_path):
        """SSL error triggers fallback to unverified context via urlopen."""
        model_path = tmp_path / "model.bin"

        manager = self._make_manager()

        mock_response = MagicMock()
        mock_response.read.return_value = b"fake model data"
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlretrieve", side_effect=ssl.SSLError("cert verify failed")):
            with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
                manager._download_model(model_path=model_path)
                mock_urlopen.assert_called_once()

    def test_download_raises_runtime_error_when_all_attempts_fail(self, tmp_path):
        """If both SSL attempts fail, RuntimeError is raised."""
        model_path = tmp_path / "model.bin"

        manager = self._make_manager()

        with patch("urllib.request.urlretrieve", side_effect=Exception("network failure")):
            with pytest.raises(RuntimeError, match="Download failed"):
                manager._download_model(model_path=model_path)
