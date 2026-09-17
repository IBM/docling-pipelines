"""Unit tests for IngestSourceOperator.get_metadata() provider schema structure."""

from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

EXPECTED_PROVIDERS = {"filesystem", "s3", "ibm_cos", "google_drive", "onedrive", "sharepoint", "box_driver", "web"}


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
