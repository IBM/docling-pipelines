"""Tests for S3DestinationConfig."""

import pytest
from pydantic import ValidationError

from docpipe.core.operators.storage.adapters.outbound.destinations.s3.config import (
    S3DestinationConfig,
)

_VALID_CREDS = {
    "access_key": "AKIAIOSFODNN7EXAMPLE",  # pragma: allowlist secret
    "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",  # pragma: allowlist secret
    "bucket": "my-export-bucket",
}


class TestS3DestinationConfigRequiredFields:
    def test_valid_minimal_config(self):
        cfg = S3DestinationConfig(**_VALID_CREDS)
        assert cfg.access_key == _VALID_CREDS["access_key"]
        assert cfg.secret_key == _VALID_CREDS["secret_key"]
        assert cfg.bucket == _VALID_CREDS["bucket"]

    def test_missing_access_key_raises(self):
        with pytest.raises(ValidationError, match="access_key"):
            S3DestinationConfig(secret_key="s", bucket="b")

    def test_missing_secret_key_raises(self):
        with pytest.raises(ValidationError, match="secret_key"):
            S3DestinationConfig(access_key="a", bucket="b")

    def test_missing_bucket_raises(self):
        with pytest.raises(ValidationError, match="bucket"):
            S3DestinationConfig(access_key="a", secret_key="s")

    def test_empty_access_key_raises(self):
        with pytest.raises(ValidationError):
            S3DestinationConfig(access_key="   ", secret_key="s", bucket="b")

    def test_empty_bucket_raises(self):
        with pytest.raises(ValidationError):
            S3DestinationConfig(access_key="a", secret_key="s", bucket="")


class TestS3DestinationConfigDefaults:
    def test_key_prefix_default_is_empty(self):
        cfg = S3DestinationConfig(**_VALID_CREDS)
        assert cfg.key_prefix == ""

    def test_endpoint_url_default_is_none(self):
        cfg = S3DestinationConfig(**_VALID_CREDS)
        assert cfg.endpoint_url is None

    def test_region_default_is_none(self):
        cfg = S3DestinationConfig(**_VALID_CREDS)
        assert cfg.region is None

    def test_verify_expected_bucket_owner_default_is_false(self):
        cfg = S3DestinationConfig(**_VALID_CREDS)
        assert cfg.verify_expected_bucket_owner is False

    def test_content_type_map_default_contains_md_override(self):
        cfg = S3DestinationConfig(**_VALID_CREDS)
        assert cfg.content_type_map == {"md": "text/markdown"}


class TestS3DestinationConfigKeyPrefixNormalisation:
    def test_trailing_slash_added_when_missing(self):
        cfg = S3DestinationConfig(**_VALID_CREDS, key_prefix="exports/docs")
        assert cfg.key_prefix == "exports/docs/"

    def test_trailing_slash_preserved_when_present(self):
        cfg = S3DestinationConfig(**_VALID_CREDS, key_prefix="exports/docs/")
        assert cfg.key_prefix == "exports/docs/"

    def test_leading_slash_stripped(self):
        cfg = S3DestinationConfig(**_VALID_CREDS, key_prefix="/exports/docs/")
        assert cfg.key_prefix == "exports/docs/"

    def test_empty_prefix_stays_empty(self):
        cfg = S3DestinationConfig(**_VALID_CREDS, key_prefix="")
        assert cfg.key_prefix == ""


class TestS3DestinationConfigEndpointUrlValidation:
    def test_valid_https_endpoint(self):
        cfg = S3DestinationConfig(**_VALID_CREDS, endpoint_url="https://s3.example.com")
        assert cfg.endpoint_url == "https://s3.example.com"

    def test_valid_http_endpoint(self):
        cfg = S3DestinationConfig(**_VALID_CREDS, endpoint_url="http://minio.local:9000")
        assert cfg.endpoint_url == "http://minio.local:9000"

    def test_trailing_slash_stripped_from_endpoint(self):
        cfg = S3DestinationConfig(**_VALID_CREDS, endpoint_url="https://s3.example.com/")
        assert cfg.endpoint_url == "https://s3.example.com"

    def test_invalid_endpoint_raises(self):
        with pytest.raises(ValidationError, match="endpoint_url"):
            S3DestinationConfig(**_VALID_CREDS, endpoint_url="s3.example.com")


class TestS3DestinationConfigHelpers:
    def test_is_s3_compatible_false_for_aws(self):
        cfg = S3DestinationConfig(**_VALID_CREDS)
        assert cfg.is_s3_compatible() is False

    def test_is_s3_compatible_true_when_endpoint_url_set(self):
        cfg = S3DestinationConfig(**_VALID_CREDS, endpoint_url="https://s3.example.com")
        assert cfg.is_s3_compatible() is True

    def test_get_content_type_override_takes_precedence(self):
        cfg = S3DestinationConfig(**_VALID_CREDS)
        assert cfg.get_content_type(extension="md") == "text/markdown"

    def test_get_content_type_stdlib_fallback(self):
        cfg = S3DestinationConfig(**_VALID_CREDS)
        assert cfg.get_content_type(extension="json") == "application/json"
        assert cfg.get_content_type(extension=".pdf") == "application/pdf"

    def test_get_content_type_unknown_extension_returns_none(self):
        cfg = S3DestinationConfig(**_VALID_CREDS)
        assert cfg.get_content_type(extension="xyzunknown123") is None
