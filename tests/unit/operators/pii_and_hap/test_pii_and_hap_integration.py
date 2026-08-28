"""
Integration tests for PII and HAP Annotator operator with a real OpenAI-compatible backend.

These tests require an OpenAI-compatible endpoint to be running locally.
For Ollama, expose the OpenAI-compatible API and use the [`litellm`](src/docpipe/core/operators/quality/pii_and_hap/services/pii_hap_service.py:90) provider.
They will be skipped if Ollama is not available.

Run these tests separately when you want to verify real LLM behavior:
    pytest tests/test_pii_and_hap_integration.py -v

For fast, consistent unit tests, use test_pii_and_hap_annotator.py instead.
"""

import pyarrow as pa
import pytest
import requests

from docpipe.core.operators.quality.pii_and_hap.pii_and_hap_annotator import (
    PIIAndHAPAnnotator,
)


def is_openai_compatible_api_running():
    """Check if an OpenAI-compatible API is running."""
    try:
        response = requests.get("http://localhost:11434/v1/models", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


# Skip all tests in this file if the local OpenAI-compatible API is unavailable
pytestmark = pytest.mark.skipif(
    not is_openai_compatible_api_running(),
    reason="OpenAI-compatible API is not running at http://localhost:11434/v1.",
)


def test_real_pii_detection_with_ollama():
    """Integration test with Ollama through the OpenAI-compatible LiteLLM path for PII detection."""
    operator = PIIAndHAPAnnotator(
        {
            "doc_column": "content",
            "provider": "litellm",
            "provider_config": {
                "model_id": "openai/granite4",
                "api_base": "http://localhost:11434/v1",
                "api_key": "<ollama>",  # pragma: allowlist secret
            },
            "redaction": True,
            "redaction_character": "*",
            "validate_model": False,
        }
    )

    content = pa.array(
        [
            "Contact me at john.doe@example.com or call 555-123-4567",
        ]
    )
    ids = [1]
    names = ["test_doc"]
    col_names = ["id", "content", "name"]
    input_table = pa.Table.from_arrays([ids, content, names], names=col_names)

    table_list, metadata = operator.transform(input_table)

    # Verify basic structure
    assert len(table_list) > 0
    assert metadata["documents_in_scope"] == 1
    assert metadata["processed_docs"] == 1
    assert metadata["node_status"] == "Completed"

    # Note: Exact counts may vary with real LLM
    print(f"Detected PII types: {metadata}")


def test_real_hap_detection_with_ollama():
    """Integration test with Ollama through the OpenAI-compatible LiteLLM path for HAP detection."""
    operator = PIIAndHAPAnnotator(
        {
            "doc_column": "content",
            "provider": "litellm",
            "provider_config": {
                "model_id": "openai/granite4",
                "api_base": "http://localhost:11434/v1",
                "api_key": "<ollama>",  # pragma: allowlist secret
            },
            "hap_redaction": True,
            "hap_redaction_character": "*",
            "hap_threshold": 0.8,
            "validate_model": False,
        }
    )

    content = pa.array(
        [
            "This is a normal message.",
            "You are stupid and worthless.",
        ]
    )
    ids = [1, 2]
    names = ["doc1", "doc2"]
    col_names = ["id", "content", "name"]
    input_table = pa.Table.from_arrays([ids, content, names], names=col_names)

    table_list, metadata = operator.transform(input_table)

    # Verify basic structure
    assert len(table_list) > 0
    assert metadata["documents_in_scope"] == 2
    assert metadata["processed_docs"] == 2
    assert metadata["node_status"] == "Completed"

    # Note: Exact HAP detection may vary with real LLM
    print(f"Detected HAP: {metadata.get('HAP', 0)}")


def test_real_combined_pii_and_hap_with_ollama():
    """Integration test with Ollama through the OpenAI-compatible LiteLLM path for combined detection."""
    operator = PIIAndHAPAnnotator(
        {
            "doc_column": "content",
            "provider": "litellm",
            "provider_config": {
                "model_id": "openai/granite4",
                "api_base": "http://localhost:11434/v1",
                "api_key": "<api-key>",  # pragma: allowlist secret
            },
            "redaction": True,
            "redaction_character": "*",
            "hap_redaction": True,
            "hap_redaction_character": "*",
            "hap_threshold": 0.8,
            "display_pii": True,
            "validate_model": False,
        }
    )

    content = pa.array(
        [
            "Email me at test@example.com with your SSN 123-45-6789",
            "You idiot, send it to admin@test.com",
        ]
    )
    ids = [1, 2]
    names = ["doc1", "doc2"]
    col_names = ["id", "content", "name"]
    input_table = pa.Table.from_arrays([ids, content, names], names=col_names)

    table_list, metadata = operator.transform(input_table)

    # Verify basic structure
    assert len(table_list) > 0
    table = table_list[0]

    assert metadata["documents_in_scope"] == 2
    assert metadata["processed_docs"] == 2
    assert metadata["node_status"] == "Completed"

    # Verify columns exist
    assert "pii_email_address" in table.column_names
    assert "hap" in table.column_names
    assert "content" in table.column_names

    # Note: Exact detection counts may vary with real LLM
    print(f"Metadata: {metadata}")
    print(f"Email detections: {table['pii_email_address'].to_pandas().to_list()}")
    print(f"HAP detections: {table['hap'].to_pandas().to_list()}")


def test_real_openai_compatible_api():
    """Integration test with OpenAI-compatible API (e.g., vLLM)."""
    # This test assumes you have a vLLM or similar server running
    # Skip if not available
    try:
        response = requests.get("http://localhost:8000/v1/models", timeout=2)
        if response.status_code != 200:
            pytest.skip("OpenAI-compatible API not available at localhost:8000")
    except Exception:
        pytest.skip("OpenAI-compatible API not available at localhost:8000")

    operator = PIIAndHAPAnnotator(
        {
            "doc_column": "content",
            "provider": "openai",
            "provider_config": {
                "model_id": "llama-3-8b",
                "base_url": "http://localhost:8000/v1",
                "api_key": "not-needed",  # pragma: allowlist secret
            },
            "redaction": True,
            "redaction_character": "*",
        }
    )

    content = pa.array(
        [
            "My email is user@domain.com and phone is 555-0123",
        ]
    )
    ids = [1]
    names = ["test"]
    col_names = ["id", "content", "name"]
    input_table = pa.Table.from_arrays([ids, content, names], names=col_names)

    table_list, metadata = operator.transform(input_table)

    # Verify basic structure
    assert len(table_list) > 0
    assert metadata["documents_in_scope"] == 1
    assert metadata["processed_docs"] == 1
    assert metadata["node_status"] == "Completed"

    print(f"OpenAI API Metadata: {metadata}")


if __name__ == "__main__":
    if is_openai_compatible_api_running():
        print("\n" + "=" * 60)
        print("Running integration tests with local OpenAI-compatible API")
        print("=" * 60 + "\n")
        pytest.main([__file__, "-v", "-s"])
    else:
        print("\n" + "=" * 60)
        print("OpenAI-compatible API is not running!")
        print("Start Ollama to run integration tests:")
        print("  ollama serve")
        print("  ollama pull granite4")
        print("Use endpoint: http://localhost:11434/v1")
        print("=" * 60 + "\n")
