"""Unit tests for prefect/domain/models.BatchStrategyConstants.get_inline_size_limit()."""

import os
import sys
from unittest.mock import MagicMock, patch


def _ensure_prefect_mocked():
    """Pre-mock prefect to avoid import errors in environments without it."""
    for mod in ["prefect", "prefect.settings", "prefect.context"]:
        if mod not in sys.modules:
            sys.modules[mod] = MagicMock()


class TestGetInlineSizeLimit:
    """Tests for get_inline_size_limit covering all fallback paths."""

    def setup_method(self):
        _ensure_prefect_mocked()

    def test_returns_default_when_no_settings_and_no_env(self):
        """Returns default value when Prefect settings have no relevant attr and no env var."""
        mock_settings = MagicMock(spec=[])  # no attributes at all

        with patch.object(sys.modules["prefect.settings"], "get_current_settings", return_value=mock_settings):
            os.environ.pop("PREFECT_SERVER_API_MAX_PARAMETER_SIZE", None)
            from docpipe.core.orchestration.prefect.domain.models import BatchStrategyConstants

            result = BatchStrategyConstants.get_inline_size_limit()

        assert result == BatchStrategyConstants.DEFAULT_INLINE_SIZE_LIMIT_BYTES

    def test_returns_env_var_value_when_prefect_has_no_setting(self):
        """Returns env var value when Prefect settings have no relevant attr."""
        mock_settings = MagicMock(spec=[])  # no attributes at all

        from docpipe.core.orchestration.prefect.domain.models import BatchStrategyConstants

        with patch.object(sys.modules["prefect.settings"], "get_current_settings", return_value=mock_settings):
            with patch.dict(os.environ, {"PREFECT_SERVER_API_MAX_PARAMETER_SIZE": "2097152"}):
                result = BatchStrategyConstants.get_inline_size_limit()

        assert result == 2097152

    def test_falls_through_when_prefect_settings_raise(self):
        """If get_current_settings raises, falls through to env var or default."""
        from docpipe.core.orchestration.prefect.domain.models import BatchStrategyConstants

        with patch.object(
            sys.modules["prefect.settings"], "get_current_settings", side_effect=Exception("unavailable")
        ):
            os.environ.pop("PREFECT_SERVER_API_MAX_PARAMETER_SIZE", None)
            result = BatchStrategyConstants.get_inline_size_limit()

        assert result == BatchStrategyConstants.DEFAULT_INLINE_SIZE_LIMIT_BYTES
