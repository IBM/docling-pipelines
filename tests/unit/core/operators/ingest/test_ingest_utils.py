"""Unit tests for ingest_utils."""

import pytest

from docpipe.core.operators.ingest.ingest_utils import (
    extract_msgraph_file_id_from_url,
    filter_based_on_extension,
    get_filter_extensions,
    handle_msgraph_resolution_result,
    is_doc_previously_processed,
)


class TestGetFilterExtensions:
    def test_none_returns_none(self):
        assert get_filter_extensions(None) is None

    def test_string_csv_returns_list_with_dots(self):
        result = get_filter_extensions("pdf,docx")
        assert result == [".pdf", ".docx"]

    def test_string_already_with_dot(self):
        result = get_filter_extensions(".pdf,.txt")
        assert result == [".pdf", ".txt"]

    def test_list_input(self):
        result = get_filter_extensions(["pdf", "docx"])
        assert result == [".pdf", ".docx"]

    def test_list_already_with_dot(self):
        result = get_filter_extensions([".pdf", ".docx"])
        assert result == [".pdf", ".docx"]

    def test_whitespace_stripped(self):
        result = get_filter_extensions("pdf, docx , txt")
        assert result == [".pdf", ".docx", ".txt"]


class TestFilterBasedOnExtension:
    def test_excluded_extension_returns_true(self):
        assert filter_based_on_extension("doc.pdf", [".pdf"], None) is True

    def test_not_in_included_returns_true(self):
        assert filter_based_on_extension("doc.xyz", None, [".pdf", ".docx"]) is True

    def test_in_included_returns_false(self):
        assert filter_based_on_extension("doc.pdf", None, [".pdf", ".docx"]) is False

    def test_no_filters_returns_false(self):
        assert filter_based_on_extension("doc.pdf", None, None) is False

    def test_extension_case_insensitive(self):
        assert filter_based_on_extension("DOC.PDF", None, [".pdf"]) is False


class TestIsDocPreviouslyProcessed:
    def test_empty_dict_returns_false(self):
        assert is_doc_previously_processed(previously_processed_docs_dict={}, doc_id="id1", modified_time=100) is False

    def test_doc_not_in_dict_returns_false(self):
        assert (
            is_doc_previously_processed(previously_processed_docs_dict={"other": {}}, doc_id="id1", modified_time=100)
            is False
        )

    def test_no_modified_time_in_entry_returns_false(self):
        assert (
            is_doc_previously_processed(previously_processed_docs_dict={"id1": {}}, doc_id="id1", modified_time=100)
            is False
        )

    def test_previous_time_older_returns_false(self):
        assert (
            is_doc_previously_processed(
                previously_processed_docs_dict={"id1": {"modified_time": 50}},
                doc_id="id1",
                modified_time=100,
            )
            is False
        )

    def test_previous_time_same_returns_true(self):
        assert (
            is_doc_previously_processed(
                previously_processed_docs_dict={"id1": {"modified_time": 100}},
                doc_id="id1",
                modified_time=100,
            )
            is True
        )

    def test_previous_time_newer_returns_true(self):
        assert (
            is_doc_previously_processed(
                previously_processed_docs_dict={"id1": {"modified_time": 200}},
                doc_id="id1",
                modified_time=100,
            )
            is True
        )


class TestExtractMsgraphFileIdFromUrl:
    def test_none_url_returns_none(self):
        assert extract_msgraph_file_id_from_url("") is None

    def test_id_parameter(self):
        url = "https://domain.sharepoint.com/?id=/path/to/file.docx"
        assert extract_msgraph_file_id_from_url(url) == "/path/to/file.docx"

    def test_sourcedoc_parameter(self):
        url = "https://domain.sharepoint.com/:w:/r/_layouts/15/Doc.aspx?sourcedoc={ABCD-1234}"
        result = extract_msgraph_file_id_from_url(url)
        assert result == "ABCD-1234"

    def test_no_known_params_returns_none(self):
        url = "https://domain.sharepoint.com/site/page"
        assert extract_msgraph_file_id_from_url(url) is None


class TestHandleMsgraphResolutionResult:
    def test_returns_resolved_ids(self):
        item_id, drive_id = handle_msgraph_resolution_result(
            file_id="file1",
            item_id="resolved_item",
            actual_drive_id="resolved_drive",
            fallback_drive_id="fallback",
        )
        assert item_id == "resolved_item"
        assert drive_id == "resolved_drive"

    def test_uses_fallback_drive_when_actual_is_none(self):
        _, drive_id = handle_msgraph_resolution_result(
            file_id="file1",
            item_id="resolved_item",
            actual_drive_id=None,
            fallback_drive_id="fallback_drive",
        )
        assert drive_id == "fallback_drive"

    def test_path_without_item_raises(self):
        with pytest.raises(ValueError, match="Could not resolve file path"):
            handle_msgraph_resolution_result(
                file_id="/some/path",
                item_id=None,
                actual_drive_id=None,
                fallback_drive_id="fb",
            )

    def test_guid_without_item_raises_when_no_fallback(self):
        with pytest.raises(ValueError):
            handle_msgraph_resolution_result(
                file_id="some-guid",
                item_id=None,
                actual_drive_id=None,
                fallback_drive_id="fb",
                allow_guid_fallback=False,
            )

    def test_guid_fallback_allowed(self):
        item_id, drive_id = handle_msgraph_resolution_result(
            file_id="some-guid",
            item_id=None,
            actual_drive_id=None,
            fallback_drive_id="fb",
            allow_guid_fallback=True,
        )
        assert item_id == "some-guid"
        assert drive_id == "fb"
