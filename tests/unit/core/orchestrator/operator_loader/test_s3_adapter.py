"""Unit tests for S3Adapter operator loader — ExpectedBucketOwner security."""

from unittest.mock import Mock


class TestS3AdapterExpectedBucketOwnerPropagation:
    """Tests that ExpectedBucketOwner is injected into S3 calls when account ID resolves."""

    def _make_adapter_with_account(self, account_id: str | None):
        from datasift.core.orchestration.operator_loader.adapters.s3_adapter import S3Adapter

        adapter = S3Adapter.__new__(S3Adapter)
        adapter.bucket = "test-bucket"
        adapter.prefix = "operators/"
        adapter._aws_account_id = account_id
        adapter.s3_client = Mock()
        return adapter

    def test_list_objects_passes_expected_bucket_owner(self):
        """list_objects_v2 paginator receives ExpectedBucketOwner when account ID resolved."""
        adapter = self._make_adapter_with_account("123456789012")

        mock_paginator = Mock()
        mock_paginator.paginate.return_value = []  # no pages → no download_file calls
        adapter.s3_client.get_paginator.return_value = mock_paginator

        adapter._download_operators()

        mock_paginator.paginate.assert_called_once_with(
            Bucket="test-bucket", Prefix="operators/", ExpectedBucketOwner="123456789012"
        )

    def test_list_objects_omits_expected_bucket_owner_when_none(self):
        """list_objects_v2 paginator does NOT receive ExpectedBucketOwner when account ID is None."""
        adapter = self._make_adapter_with_account(None)

        mock_paginator = Mock()
        mock_paginator.paginate.return_value = []
        adapter.s3_client.get_paginator.return_value = mock_paginator

        adapter._download_operators()

        call_kwargs = mock_paginator.paginate.call_args[1]
        assert "ExpectedBucketOwner" not in call_kwargs

    def test_download_file_passes_expected_bucket_owner(self, tmp_path):
        """download_file receives ExtraArgs with ExpectedBucketOwner when account ID resolved."""
        adapter = self._make_adapter_with_account("123456789012")
        adapter.cache_dir = tmp_path

        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "operators/my_op.py"},
                ]
            }
        ]
        adapter.s3_client.get_paginator.return_value = mock_paginator
        adapter.s3_client.download_file = Mock()

        adapter._download_operators()

        adapter.s3_client.download_file.assert_called_once()
        _, _call_args, call_kwargs = adapter.s3_client.download_file.mock_calls[0]
        assert call_kwargs.get("ExtraArgs") == {"ExpectedBucketOwner": "123456789012"}

    def test_download_file_omits_extra_args_when_no_account_id(self, tmp_path):
        """download_file receives ExtraArgs=None when account ID is None."""
        adapter = self._make_adapter_with_account(None)
        adapter.cache_dir = tmp_path

        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "operators/my_op.py"},
                ]
            }
        ]
        adapter.s3_client.get_paginator.return_value = mock_paginator
        adapter.s3_client.download_file = Mock()

        adapter._download_operators()

        adapter.s3_client.download_file.assert_called_once()
        _, _call_args, call_kwargs = adapter.s3_client.download_file.mock_calls[0]
        assert call_kwargs.get("ExtraArgs") is None
