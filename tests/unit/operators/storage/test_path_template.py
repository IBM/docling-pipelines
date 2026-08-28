"""Tests for path template resolver."""

from datetime import UTC, datetime
from unittest.mock import patch

from docpipe.core.operators.storage.storage_output_operator import resolve_path_template


class TestResolvePathTemplate:
    def _fixed_utc(self):
        return datetime(2026, 6, 26, tzinfo=UTC)

    def test_resolves_all_variables(self):
        with patch("docpipe.core.operators.storage.storage_output_operator.datetime") as mock_dt:
            mock_dt.now.return_value = self._fixed_utc()
            result = resolve_path_template(
                template="{year}/{month}/{day}/{doc_id}.{ext}",
                doc_id="abc123",
                name="my_doc.pdf",
                ext="md",
            )
        assert result == "2026/06/26/abc123.md"

    def test_resolves_name_without_extension(self):
        with patch("docpipe.core.operators.storage.storage_output_operator.datetime") as mock_dt:
            mock_dt.now.return_value = self._fixed_utc()
            result = resolve_path_template(
                template="{name}.{ext}",
                doc_id="abc123",
                name="report.pdf",
                ext="txt",
            )
        assert result == "report.txt"

    def test_name_stem_strips_extension(self):
        with patch("docpipe.core.operators.storage.storage_output_operator.datetime") as mock_dt:
            mock_dt.now.return_value = self._fixed_utc()
            result = resolve_path_template(
                template="{name}.{ext}",
                doc_id="x",
                name="file.with.dots.pdf",
                ext="md",
            )
        assert result == "file.with.dots.md"

    def test_no_template_falls_back_to_flat(self):
        with patch("docpipe.core.operators.storage.storage_output_operator.datetime") as mock_dt:
            mock_dt.now.return_value = self._fixed_utc()
            result = resolve_path_template(
                template=None,
                doc_id="abc",
                name="doc.pdf",
                ext="md",
            )
        assert result == "doc.md"

    def test_month_and_day_are_zero_padded(self):
        with patch("docpipe.core.operators.storage.storage_output_operator.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 5, tzinfo=UTC)
            result = resolve_path_template(
                template="{year}/{month}/{day}",
                doc_id="x",
                name="f",
                ext="md",
            )
        assert result == "2026/01/05"

    def test_hierarchical_no_template_uses_source_relative_path(self):
        result = resolve_path_template(
            template=None,
            doc_id="abc",
            name="report.pdf",
            ext="pdf",
            hierarchical=True,
            source_relative_path="sub01/report.pdf",
        )
        assert result == "sub01/report.pdf"

    def test_hierarchical_no_template_falls_back_to_flat_when_no_relative_path(self):
        result = resolve_path_template(
            template=None,
            doc_id="abc",
            name="report.pdf",
            ext="pdf",
            hierarchical=True,
            source_relative_path=None,
        )
        assert result == "report.pdf"

    def test_flat_no_template_ignores_source_relative_path(self):
        result = resolve_path_template(
            template=None,
            doc_id="abc",
            name="report.pdf",
            ext="pdf",
            hierarchical=False,
            source_relative_path="sub01/report.pdf",
        )
        assert result == "report.pdf"

    def test_template_takes_precedence_over_hierarchical(self):
        result = resolve_path_template(
            template="{doc_id}.{ext}",
            doc_id="abc",
            name="report.pdf",
            ext="pdf",
            hierarchical=True,
            source_relative_path="sub01/report.pdf",
        )
        assert result == "abc.pdf"
