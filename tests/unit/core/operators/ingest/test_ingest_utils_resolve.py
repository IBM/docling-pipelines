"""Additional ingest_utils tests to cover resolve_msgraph functions."""

from unittest.mock import MagicMock

from docpipe.core.operators.ingest.ingest_utils import resolve_msgraph_file_id_to_item_id


def make_rest_client(response=None, raises=None):
    client = MagicMock()
    if raises:
        client.call_rest_json.side_effect = raises
    else:
        client.call_rest_json.return_value = response or {}
    return client


class TestResolveMsgraphFileIdToItemId:
    def test_path_with_direct_api_success(self):
        client = make_rest_client({"id": "item123"})
        item_id, drive_id = resolve_msgraph_file_id_to_item_id(
            file_id="/some/path/file.docx",
            drive_id="drive1",
            rest_client=client,
            token="tok",
        )
        assert item_id == "item123"
        assert drive_id == "drive1"

    def test_path_with_shares_endpoint_success(self):
        def side_effect(method, url, headers, **kwargs):
            if "shares" in url:
                return {"id": "from_shares", "parentReference": {"driveId": "drivex"}}
            return {"id": "fallback"}

        client = MagicMock()
        client.call_rest_json.side_effect = side_effect

        item_id, drive_id = resolve_msgraph_file_id_to_item_id(
            file_id="/path/file.docx",
            drive_id="drive1",
            rest_client=client,
            token="tok",
            original_url="https://domain.sharepoint.com/path/file.docx",
        )
        assert item_id == "from_shares"
        assert drive_id == "drivex"

    def test_path_api_fails_returns_none(self):
        client = make_rest_client(raises=RuntimeError("not found"))
        item_id, drive_id = resolve_msgraph_file_id_to_item_id(
            file_id="/missing/file.docx",
            drive_id="drive1",
            rest_client=client,
            token="tok",
        )
        assert item_id is None
        assert drive_id is None

    def test_guid_direct_access_success(self):
        client = make_rest_client({"id": "guid_resolved"})
        item_id, _ = resolve_msgraph_file_id_to_item_id(
            file_id="some-guid-1234",
            drive_id="drive1",
            rest_client=client,
            token="tok",
        )
        assert item_id == "guid_resolved"

    def test_guid_all_methods_fail_returns_none(self):
        client = make_rest_client(raises=RuntimeError("all fail"))
        item_id, drive_id = resolve_msgraph_file_id_to_item_id(
            file_id="bad-guid",
            drive_id="drive1",
            rest_client=client,
            token="tok",
        )
        assert item_id is None
        assert drive_id is None

    def test_guid_with_shares_endpoint(self):
        def side_effect(method, url, headers, **kwargs):
            if "shares" in url:
                return {"id": "from_shares_guid", "parentReference": {"driveId": "drivex"}}
            raise RuntimeError("direct failed")

        client = MagicMock()
        client.call_rest_json.side_effect = side_effect

        item_id, _ = resolve_msgraph_file_id_to_item_id(
            file_id="some-guid",
            drive_id="drive1",
            rest_client=client,
            token="tok",
            original_url="https://domain.sharepoint.com/file",
        )
        assert item_id == "from_shares_guid"

    def test_path_with_strip_prefix_fallback(self):
        call_count = [0]

        def side_effect(method, url, headers, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("initial fail")
            return {"id": "stripped_item"}

        client = MagicMock()
        client.call_rest_json.side_effect = side_effect

        item_id, _ = resolve_msgraph_file_id_to_item_id(
            file_id="/Shared Documents/file.docx",
            drive_id="drive1",
            rest_client=client,
            token="tok",
            strip_path_prefixes=["Shared Documents/"],
        )
        assert item_id == "stripped_item"
