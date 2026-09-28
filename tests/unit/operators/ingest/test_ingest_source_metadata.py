"""Unit tests for IngestSourceOperator.get_metadata() provider schema structure."""

import pytest

from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

EXPECTED_PROVIDERS = {"filesystem", "s3", "ibm_cos", "google_drive", "onedrive", "sharepoint", "box_driver", "web"}

EXPECTED_SENSITIVE_FIELDS: dict[str, set[str]] = {
    "s3": {"access_key", "secret_key"},
    "ibm_cos": {"access_key", "secret_key"},
    "onedrive": {"client_id", "client_secret", "tenant_id"},
    "sharepoint": {"client_id", "client_secret", "tenant_id"},
    "google_drive": {"credentials_path", "token_path", "service_account_json_path"},
    "box_driver": {"credentials_path"},
    "filesystem": set(),
    "web": set(),
}


def test_get_metadata_has_provider_schemas() -> None:
    metadata = IngestSourceOperator.get_metadata()
    providers = metadata["attributes"]["connection_params"]["providers"]
    assert isinstance(providers, dict)
    assert EXPECTED_PROVIDERS == set(providers.keys())


def test_each_provider_has_properties() -> None:
    metadata = IngestSourceOperator.get_metadata()
    providers = metadata["attributes"]["connection_params"]["providers"]
    for name, schema in providers.items():
        assert "properties" in schema, f"Provider '{name}' is missing 'properties' key"
        assert len(schema["properties"]) > 0, f"Provider '{name}' has empty 'properties'"


def test_ibm_cos_reuses_s3_schema() -> None:
    metadata = IngestSourceOperator.get_metadata()
    providers = metadata["attributes"]["connection_params"]["providers"]
    assert providers["ibm_cos"] == providers["s3"]


def test_custom_has_no_providers() -> None:
    metadata = IngestSourceOperator.get_metadata()
    providers = metadata["attributes"]["connection_params"]["providers"]
    assert "custom" not in providers


@pytest.mark.parametrize("provider", sorted(EXPECTED_PROVIDERS))
def test_sensitive_fields_flagged(provider: str) -> None:
    metadata = IngestSourceOperator.get_metadata()
    providers = metadata["attributes"]["connection_params"]["providers"]
    actual = {k for k, v in providers[provider]["properties"].items() if v.get("sensitive") is True}
    assert actual == EXPECTED_SENSITIVE_FIELDS[provider], (
        f"Provider '{provider}': expected sensitive={EXPECTED_SENSITIVE_FIELDS[provider]}, got {actual}"
    )


def test_credentials_attribute_is_not_required() -> None:
    metadata = IngestSourceOperator.get_metadata()
    credentials = metadata["attributes"]["credentials"]
    assert credentials.get("required") is not True
