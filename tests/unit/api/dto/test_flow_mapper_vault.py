"""Unit tests for FlowMapper Vault scrubbing and secret masking."""

from datetime import UTC, datetime

from docpipe.api.dto.mappers.flow_mapper import FlowMapper
from docpipe.core.assets.flows.domain.models.flow import Flow


def test_flow_mapper_authoring_dto_returns_plaintext_and_vault_refs() -> None:
    """domain_to_authoring_dto returns operator configs unmasked for round-trip editing."""
    domain_flow = Flow(
        asset_id="test-flow-123",
        name="Test Flow",
        description="A test flow with vault and plaintext credentials",
        definition={
            "flow_name": "Test Flow",
            "flow": [
                {
                    "type": "ingest_source",
                    "name": "ingest_node",
                    "config": {
                        "provider": "s3",
                        "credentials": "vault://hashicorp/s3/creds#json",
                    },
                },
                {
                    "type": "embeddings",
                    "name": "embed_node",
                    "config": {
                        "provider_config": {
                            "api_key": "sk-secret-plain-key-123",  # pragma: allowlist secret
                        },
                    },
                },
            ],
            "global_config": {},
        },
        tags=["test"],
        is_hidden=False,
        flow_version="2.0",
        created_on=datetime.now(tz=UTC),
        modified_on=datetime.now(tz=UTC),
    )

    dto = FlowMapper.domain_to_authoring_dto(domain=domain_flow)
    # Vault references must be preserved intact
    assert dto.flow[0].config["credentials"] == "vault://hashicorp/s3/creds#json"
    # Plaintext values must NOT be masked — returned as-is for the properties panel
    assert dto.flow[1].config["provider_config"]["api_key"] == "sk-secret-plain-key-123"  # pragma: allowlist secret

    # Verify domain definition was not mutated
    assert (
        domain_flow.definition["flow"][1]["config"]["provider_config"]["api_key"]
        == "sk-secret-plain-key-123"  # pragma: allowlist secret
    )


def test_flow_mapper_domain_to_dto_returns_values_unmasked() -> None:
    """domain_to_dto returns the definition as-is — no masking on either format path."""
    domain_flow = Flow(
        asset_id="test-flow-456",
        name="Test Flow 2",
        description="Elyra flow test",
        definition={
            "doc_type": "pipeline",
            "pipelines": [
                {
                    "nodes": [
                        {
                            "op": "vectordb",
                            "parameters": {
                                "password": "plaintext_password",  # pragma: allowlist secret
                                "vault_pwd": "vault://hashicorp/db#pwd",  # pragma: allowlist secret
                            },
                        }
                    ]
                }
            ],
        },
        tags=[],
        is_hidden=False,
        flow_version="2.0",
        created_on=datetime.now(tz=UTC),
        modified_on=datetime.now(tz=UTC),
    )

    flow_resp = FlowMapper.domain_to_dto(domain=domain_flow)
    params = flow_resp.definition["pipelines"][0]["nodes"][0]["parameters"]
    assert params["password"] == "plaintext_password"  # pragma: allowlist secret
    assert params["vault_pwd"] == "vault://hashicorp/db#pwd"  # pragma: allowlist secret
