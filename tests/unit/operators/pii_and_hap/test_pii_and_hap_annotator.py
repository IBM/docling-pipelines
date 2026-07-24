"""
Unit tests for PII and HAP Annotator operator.

These tests use mocked responses for consistent, reproducible results.
For integration tests with real Ollama, see test_pii_and_hap_integration.py

Tests verify the same output format as the enterprise version, including:
- PII detection with and without redaction
- HAP detection with and without redaction
- Combined PII and HAP detection
- Display PII information
- Metadata validation
- Column naming conventions
"""

import os
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.quality.pii_and_hap.domain.models import (
    DetectionResult,
    PIIHAPDetectionResponse,
)
from docpipe.core.operators.quality.pii_and_hap.pii_and_hap_annotator import (
    PIIAndHAPAnnotator,
)

_TEST_SSN = os.environ.get("TEST_SSN", "000-00-0000")


def mock_detect_pii_hap(payload: dict):
    """Mock detection function that returns deterministic results."""
    text = payload.get("input", "")
    detections = []

    # Check for email addresses
    if "support@ibm.com" in text:
        detections.append(
            {
                "detection": "EmailAddress",
                "detection_type": "pii",
                "start": text.find("support@ibm.com"),
                "end": text.find("support@ibm.com") + len("support@ibm.com"),
                "score": 0.8,
                "text": "support@ibm.com",
            }
        )
    if "test@ibm.com" in text:
        detections.append(
            {
                "detection": "EmailAddress",
                "detection_type": "pii",
                "start": text.find("test@ibm.com"),
                "end": text.find("test@ibm.com") + len("test@ibm.com"),
                "score": 0.8,
                "text": "test@ibm.com",
            }
        )
    if "adityars@ibm.com" in text:
        detections.append(
            {
                "detection": "EmailAddress",
                "detection_type": "pii",
                "start": text.find("adityars@ibm.com"),
                "end": text.find("adityars@ibm.com") + len("adityars@ibm.com"),
                "score": 0.8,
                "text": "adityars@ibm.com",
            }
        )

    # Check for SSN
    if _TEST_SSN in text:
        detections.append(
            {
                "detection": "NationalNumber.SocialSecurityNumber.US",
                "detection_type": "pii",
                "start": text.find(_TEST_SSN),
                "end": text.find(_TEST_SSN) + len(_TEST_SSN),
                "score": 0.8,
                "text": _TEST_SSN,
            }
        )

    # Check for phone number
    if "123-456-7890" in text:
        detections.append(
            {
                "detection": "PhoneNumber",
                "detection_type": "pii",
                "start": text.find("123-456-7890"),
                "end": text.find("123-456-7890") + len("123-456-7890"),
                "score": 0.8,
                "text": "123-456-7890",
            }
        )

    # Check for credit card
    if "5340904586541378" in text:
        detections.append(
            {
                "detection": "CreditCardNumber",
                "detection_type": "pii",
                "start": text.find("5340904586541378"),
                "end": text.find("5340904586541378") + len("5340904586541378"),
                "score": 0.8,
                "text": "5340904586541378",
            }
        )

    # Check for IP address
    if "127.0.0.1" in text:
        detections.append(
            {
                "detection": "IPAddress",
                "detection_type": "pii",
                "start": text.find("127.0.0.1"),
                "end": text.find("127.0.0.1") + len("127.0.0.1"),
                "score": 0.8,
                "text": "127.0.0.1",
            }
        )

    # Check for HAP content
    normalized_text = text.replace("\u2019", "'")
    if "shouldn't even be allowed to speak" in normalized_text or "fool" in text.lower():
        detections.append(
            {
                "detection": "HAP",  # Must match METADATA_HAP_FIELD_NAME
                "detection_type": "hap",
                "start": 0,
                "end": len(text),
                "score": 0.9,
                "text": text[:100],  # First 100 chars
            }
        )

    # Convert dict detections to DetectionResult objects
    detection_results = [
        DetectionResult(
            detection=d["detection"],
            detection_type=d["detection_type"],
            score=d["score"],
            start=d["start"],
            end=d["end"],
            text=d.get("text"),  # Include text field for display_pii
        )
        for d in detections
    ]

    # Return PIIHAPDetectionResponse as expected by the service
    return PIIHAPDetectionResponse(detections=detection_results, input_text=text)


@pytest.fixture
def mock_pii_hap_service():
    """Mock the PIIHAPService for all tests."""
    with patch("docpipe.core.operators.quality.pii_and_hap.pii_and_hap_annotator.PIIHAPService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.detect_pii_hap.side_effect = mock_detect_pii_hap
        mock_service_class.return_value = mock_service
        yield mock_service


def test_both_pii_and_hap_redactions(mock_pii_hap_service):
    """Test PII and HAP detection with redaction enabled for both."""
    # 1. Construct the operator with the required configuration
    operator = PIIAndHAPAnnotator(
        {
            "doc_column": "content",
            "provider": "litellm",
            "provider_config": {
                "model_id": "openai/granite4",
                "api_key": "<ollama>",  # pragma: allowlist secret
                "api_base": "http://localhost:11434/v1",
            },
            "redaction": True,
            "redaction_character": "*",
            "hap_redaction": True,
            "hap_redaction_character": "*",
            "hap_threshold": 0.8,
        }
    )

    # 2. Create an in-memory py-arrow table as input
    content = pa.array(
        [
            f"Your email is support@ibm.com! 5340904586541378 Only the next instance of email will be processed. test@ibm.com. Your SSN is {_TEST_SSN}. Contact me at 123-456-7890",
            "Subject: Assistance 127.0.0.1 adityars@ibm.com with credit card update [213254000]",
            "People like you shouldn't even be allowed to speak. Honestly, anyone who believes in [religion] or follows [ethnicity] is a fool.",
        ]
    )
    ids = [1, 2, 3]
    names = ["file1", "file2", "file3"]
    col_names = ["id", "content", "name"]
    input_table = pa.Table.from_arrays([ids, content, names], names=col_names)

    # 3. Run the operator
    table_list, metadata = operator.transform(input_table)

    # 4. Verify metadata
    expected_metadata = {
        "BankAccountNumber": 0,
        "CreditCardNumber": 1,
        "EmailAddress": 3,
        "HAP": 1,
        "IPAddress": 1,
        "PhoneNumber": 1,
        "SocialSecurityNumber": 1,
        "total_docs_count": 3,
        "processed_docs": 3,
        "failed_docs_count": 0,
        "failed_docs": [],
        "skipped_docs_count": 0,
        "skipped_docs": [],
        "node_status": "Completed",
        "processed_rows": 3,
    }
    assert metadata == expected_metadata, f"Expected {expected_metadata}, but got {metadata}"

    # 5. Verify output table structure
    assert len(table_list) > 0, "Output table list should not be empty"
    table = table_list[0]

    # 6. Verify PII and HAP counts per document
    errors = []
    expected_pii_bank_account = [0, 0, 0]
    expected_pii_credit_card = [1, 0, 0]
    expected_pii_email_address = [2, 1, 0]
    expected_pii_ip_address = [0, 1, 0]
    expected_pii_phone_number = [1, 0, 0]
    expected_pii_ssn_details = [1, 0, 0]
    expected_hap = [0, 0, 1]

    if expected_pii_bank_account != table["pii_bank_account"].to_pandas().to_list():
        errors.append("Bank Account PII error:" + str(table["pii_bank_account"].to_pandas().to_list()))
    if expected_pii_credit_card != table["pii_credit_card"].to_pandas().to_list():
        errors.append("Credit Card PII error:" + str(table["pii_credit_card"].to_pandas().to_list()))
    if expected_pii_email_address != table["pii_email_address"].to_pandas().to_list():
        errors.append("Email Id PII error:" + str(table["pii_email_address"].to_pandas().to_list()))
    if expected_pii_ip_address != table["pii_ip_address"].to_pandas().to_list():
        errors.append("Ip Address PII error:" + str(table["pii_ip_address"].to_pandas().to_list()))
    if expected_pii_phone_number != table["pii_phone_number"].to_pandas().to_list():
        errors.append("Phone Number PII Error:" + str(table["pii_phone_number"].to_pandas().to_list()))
    if expected_pii_ssn_details != table["pii_ssn_details"].to_pandas().to_list():
        errors.append("SSN PII Error:" + str(table["pii_ssn_details"].to_pandas().to_list()))
    if expected_hap != table["hap"].to_pandas().to_list():
        errors.append("HAP Error:" + str(table["hap"].to_pandas().to_list()))

    assert not errors, f"Errors: {', '.join(errors)}"


def test_pii_extraction_without_redaction_and_displaying_pii(mock_pii_hap_service):
    """Test PII extraction without redaction and with display_pii enabled."""
    # 1. Construct the operator
    operator = PIIAndHAPAnnotator(
        {
            "doc_column": "content",
            "provider": "litellm",
            "provider_config": {
                "model_id": "openai/granite4",
                "api_key": "<ollama>",  # pragma: allowlist secret
                "api_base": "http://localhost:11434/v1",
            },
            "redaction": False,
            "redaction_character": "",
            "hap_redaction": True,
            "hap_redaction_character": "*",
            "display_pii": True,
        }
    )

    # 2. Create input table
    content = pa.array(
        [
            f"Your email is support@ibm.com! Only the next instance of email will be processed. test@ibm.com. Your SSN is {_TEST_SSN}. Contact me at 123-456-7890",
            "Subject: Assistance  adityars@ibm.com with credit card update [213254000]",
        ]
    )
    names = ["file1", "file2"]
    ids = [1, 2]
    col_names = ["id", "content", "name"]
    input_table = pa.Table.from_arrays([ids, content, names], names=col_names)

    # 3. Run the operator
    table_list, metadata = operator.transform(input_table)

    # 4. Verify metadata
    expected_metadata = {
        "BankAccountNumber": 0,
        "CreditCardNumber": 0,
        "EmailAddress": 3,
        "HAP": 0,
        "IPAddress": 0,
        "PhoneNumber": 1,
        "SocialSecurityNumber": 1,
        "total_docs_count": 2,
        "processed_docs": 2,
        "failed_docs_count": 0,
        "failed_docs": [],
        "skipped_docs_count": 0,
        "skipped_docs": [],
        "node_status": "Completed",
        "processed_rows": 2,
    }
    assert metadata == expected_metadata, f"Expected {expected_metadata}, but got {metadata}"

    # 5. Verify output table
    table = table_list[0]

    # Expected counts per document
    expected_pii_bank_account = [0, 0]
    expected_pii_credit_card = [0, 0]
    expected_pii_email_address = [2, 1]
    expected_pii_ip_address = [0, 0]
    expected_pii_phone_number = [1, 0]
    expected_pii_ssn_details = [1, 0]
    expected_hap = [0, 0]

    errors = []
    if expected_pii_bank_account != table["pii_bank_account"].to_pandas().to_list():
        errors.append("Bank Account PII error:" + str(table["pii_bank_account"].to_pandas().to_list()))
    if expected_pii_credit_card != table["pii_credit_card"].to_pandas().to_list():
        errors.append("Credit Card PII error:" + str(table["pii_credit_card"].to_pandas().to_list()))
    if expected_pii_email_address != table["pii_email_address"].to_pandas().to_list():
        errors.append("Email Id PII error:" + str(table["pii_email_address"].to_pandas().to_list()))
    if expected_pii_ip_address != table["pii_ip_address"].to_pandas().to_list():
        errors.append("Ip Address PII error:" + str(table["pii_ip_address"].to_pandas().to_list()))
    if expected_pii_phone_number != table["pii_phone_number"].to_pandas().to_list():
        errors.append("Phone Number PII Error:" + str(table["pii_phone_number"].to_pandas().to_list()))
    if expected_pii_ssn_details != table["pii_ssn_details"].to_pandas().to_list():
        errors.append("SSN PII Error:" + str(table["pii_ssn_details"].to_pandas().to_list()))
    if expected_hap != table["hap"].to_pandas().to_list():
        errors.append("HAP Error:" + str(table["hap"].to_pandas().to_list()))

    # 6. Verify detailed PII information (when display_pii is True)
    expected_email_id_doc1 = [
        {
            "start": 14,
            "end": 29,
            "detection": "EmailAddress",
            "score": 0.8,
            "text": "support@ibm.com",
        },
        {
            "start": 82,
            "end": 94,
            "detection": "EmailAddress",
            "score": 0.8,
            "text": "test@ibm.com",
        },
    ]
    expected_ssn_doc1 = [
        {
            "start": 108,
            "end": 119,
            "detection": "NationalNumber.SocialSecurityNumber.US",
            "score": 0.8,
            "text": _TEST_SSN,
        }
    ]
    expected_phone_number_doc1 = [
        {
            "start": 135,
            "end": 147,
            "detection": "PhoneNumber",
            "score": 0.8,
            "text": "123-456-7890",
        }
    ]
    expected_email_id_doc2 = [
        {
            "start": 21,
            "end": 37,
            "detection": "EmailAddress",
            "score": 0.8,
            "text": "adityars@ibm.com",
        }
    ]

    if expected_email_id_doc1 != table["pii_email_address_info"][0].as_py():
        errors.append("Doc1: Email Id PII Error")
    if expected_phone_number_doc1 != table["pii_phone_number_info"][0].as_py():
        errors.append("Doc1:Phone Number PII Error")
    if expected_ssn_doc1 != table["pii_ssn_details_info"][0].as_py():
        errors.append("Doc1:SSN PII Error")
    if expected_email_id_doc2 != table["pii_email_address_info"][1].as_py():
        errors.append("Doc2: Email Id PII Error")

    assert not errors, f"Errors: {', '.join(errors)}"


def test_pii_extraction_with_redaction(mock_pii_hap_service):
    """Test PII extraction with redaction enabled."""
    # 1. Construct the operator
    operator = PIIAndHAPAnnotator(
        {
            "doc_column": "content",
            "provider": "litellm",
            "provider_config": {
                "model_id": "openai/granite4",
                "api_key": "<ollama>",  # pragma: allowlist secret
                "api_base": "http://localhost:11434/v1",
            },
            "redaction": True,
            "redaction_character": "*",
            "display_pii": False,
        }
    )

    # 2. Create input table
    content = pa.array(
        [
            f"Your email is support@ibm.com! Only the next instance of email will be processed. test@ibm.com. Your SSN is {_TEST_SSN}.",
            "Subject: Assistance adityars@ibm.com with credit card update",
        ]
    )
    names = ["file1", "file2"]
    ids = [1, 2]
    col_names = ["id", "content", "name"]
    input_table = pa.Table.from_arrays([ids, content, names], names=col_names)

    # 3. Run the operator
    table_list, _ = operator.transform(input_table)

    # 4. Verify the content has been redacted
    table = table_list[0]
    redacted_content = table["content"][0].as_py()

    # Verify that PII has been replaced with redaction character
    assert "support@ibm.com" not in redacted_content, "Email should be redacted"
    assert "test@ibm.com" not in redacted_content, "Email should be redacted"
    assert _TEST_SSN not in redacted_content, "SSN should be redacted"
    assert "*" in redacted_content, "Redaction character should be present"


def test_hap_extraction_with_redaction(mock_pii_hap_service):
    """Test HAP extraction with redaction enabled."""
    # 1. Construct the operator
    operator = PIIAndHAPAnnotator(
        {
            "doc_column": "content",
            "provider": "litellm",
            "provider_config": {
                "model_id": "openai/granite4",
                "api_key": "api-key",  # pragma: allowlist secret
                "api_base": "http://localhost:11434/v1",
            },
            "hap_redaction": True,
            "hap_redaction_character": "*",
            "hap_threshold": 0.8,
        }
    )

    # 2. Create input table
    content = pa.array(
        [
            "Your email is support@ibm.com!",
            "People like you shouldn't even be allowed to speak. Honestly, anyone who believes in [religion] or follows [ethnicity] is a fool.",
        ]
    )
    names = ["file1", "file2"]
    ids = [1, 2]
    col_names = ["id", "content", "name"]
    input_table = pa.Table.from_arrays([ids, content, names], names=col_names)

    # 3. Run the operator
    table_list, _ = operator.transform(input_table)

    # 4. Verify HAP detection
    table = table_list[0]
    expected_hap = [0, 1]

    assert expected_hap == table["hap"].to_pandas().to_list(), (
        f"Expected HAP counts {expected_hap}, but got {table['hap'].to_pandas().to_list()}"
    )

    # 5. Verify HAP content has been redacted
    redacted_content = table["content"][1].as_py()
    assert "*" in redacted_content, "HAP content should be redacted"


def test_hap_extraction_without_redaction(mock_pii_hap_service):
    """Test HAP extraction without redaction."""
    # 1. Construct the operator
    operator = PIIAndHAPAnnotator(
        {
            "doc_column": "content",
            "provider": "litellm",
            "provider_config": {
                "model_id": "openai/granite4",
                "api_key": "api-key",  # pragma: allowlist secret
                "api_base": "http://localhost:11434/v1",
            },
            "hap_redaction": False,
            "hap_redaction_character": "",
        }
    )

    # 2. Create input table
    content = pa.array(
        [
            f"Your email is support@ibm.com! Only the next instance of email will be processed. test@ibm.com. Your SSN is {_TEST_SSN}. Contact me at 123-456-7890",
            "People like you shouldn't even be allowed to speak. Honestly, anyone who believes in [religion] or follows [ethnicity] is a fool.",
        ]
    )
    names = ["file1", "file2"]
    ids = [1, 2]
    col_names = ["id", "content", "name"]
    input_table = pa.Table.from_arrays([ids, content, names], names=col_names)

    # 3. Run the operator
    table_list, _ = operator.transform(input_table)

    # 4. Verify HAP detection
    table = table_list[0]
    expected_hap = [0, 1]

    assert expected_hap == table["hap"].to_pandas().to_list(), (
        f"Expected HAP counts {expected_hap}, but got {table['hap'].to_pandas().to_list()}"
    )

    # 5. Verify content is NOT redacted
    original_content = table["content"][1].as_py()
    assert "shouldn't even be allowed to speak" in original_content, (
        "HAP content should NOT be redacted when hap_redaction is False"
    )


def test_empty_input_table(mock_pii_hap_service):
    """Test operator with empty input table."""
    # 1. Construct the operator
    operator = PIIAndHAPAnnotator(
        {
            "doc_column": "content",
            "provider": "litellm",
            "provider_config": {
                "model_id": "openai/granite4",
                "api_key": "api-key",  # pragma: allowlist secret
                "api_base": "http://localhost:11434/v1",
            },
        }
    )

    # 2. Create empty input table
    content = pa.array([])
    ids = []
    names = []
    col_names = ["id", "content", "name"]
    input_table = pa.Table.from_arrays([ids, content, names], names=col_names)

    # 3. Run the operator
    _, metadata = operator.transform(input_table)

    # 4. Verify metadata for empty input
    assert metadata["total_docs_count"] == 0
    assert metadata["processed_docs"] == 0
    assert metadata["node_status"] == "Completed"


def test_configuration_validation():
    """Test operator configuration validation."""
    # Test with missing doc_column (should use default)
    try:
        operator = PIIAndHAPAnnotator(
            {
                "provider": "litellm",
                "provider_config": {
                    "model_id": "openai/granite4",
                    "api_key": "api-key",  # pragma: allowlist secret
                    "api_base": "http://localhost:11434/v1",
                },
            }
        )
        assert operator.doc_column_name == OperatorConstants.Columns.DOC_COLUMN_DEFAULT
    except Exception as e:
        pytest.fail(f"Unexpected exception with default doc_column: {e!s}")

    # Test with custom configuration
    try:
        operator = PIIAndHAPAnnotator(
            {
                "doc_column": "text",
                "provider": "litellm",
                "provider_config": {
                    "model_id": "gpt-3.5-turbo",
                    "base_url": "http://localhost:8000/v1",
                    "api_key": "test-key",  # pragma: allowlist secret
                },
            }
        )
        assert operator.doc_column_name == "text"
        assert operator.provider == "litellm"
    except Exception as e:
        pytest.fail(f"Unexpected exception with custom configuration: {e!s}")


def test_config_validation_invalid_pii_threshold():
    """Test that invalid pii_threshold raises ValueError."""
    # Test pii_threshold > 1
    with pytest.raises(ValueError, match="pii_threshold must be between 0 and 1"):
        PIIAndHAPAnnotator(
            {
                "doc_column": "content",
                "pii_threshold": 1.5,
            }
        )

    # Test pii_threshold < 0
    with pytest.raises(ValueError, match="pii_threshold must be between 0 and 1"):
        PIIAndHAPAnnotator(
            {
                "doc_column": "content",
                "pii_threshold": -0.1,
            }
        )


def test_config_validation_invalid_hap_threshold():
    """Test that invalid hap_threshold raises ValueError."""
    # Test hap_threshold > 1
    with pytest.raises(ValueError, match="hap_threshold must be between 0 and 1"):
        PIIAndHAPAnnotator(
            {
                "doc_column": "content",
                "hap_threshold": 2.0,
            }
        )

    # Test hap_threshold < 0
    with pytest.raises(ValueError, match="hap_threshold must be between 0 and 1"):
        PIIAndHAPAnnotator(
            {
                "doc_column": "content",
                "hap_threshold": -0.5,
            }
        )


def test_config_validation_invalid_batch_size():
    """Test that invalid batch_size raises ValueError."""
    # Test batch_size = 0
    with pytest.raises(ValueError, match="batch_size must be positive"):
        PIIAndHAPAnnotator(
            {
                "doc_column": "content",
                "batch_size": 0,
            }
        )

    # Test batch_size < 0
    with pytest.raises(ValueError, match="batch_size must be positive"):
        PIIAndHAPAnnotator(
            {
                "doc_column": "content",
                "batch_size": -5,
            }
        )


def test_config_validation_invalid_chunk_sizes():
    """Test that invalid chunk size configuration raises ValueError."""
    # Test min_chunk_size > max_chunk_size
    with pytest.raises(ValueError, match=r"min_chunk_size .* cannot exceed max_chunk_size"):
        PIIAndHAPAnnotator(
            {
                "doc_column": "content",
                "min_chunk_size_kb": 200 * 1024,
                "max_chunk_size_kb": 100 * 1024,
            }
        )


@pytest.mark.parametrize(
    "config_override,expected_attr,expected_value",
    [
        # PII threshold edge cases
        ({"pii_threshold": 0.0}, "pii_threshold", 0.0),
        ({"pii_threshold": 1.0}, "pii_threshold", 1.0),
        # HAP threshold edge cases
        ({"hap_threshold": 0.0}, "hap_threshold", 0.0),
        ({"hap_threshold": 1.0}, "hap_threshold", 1.0),
        # Chunk size edge case - special handling needed
        (
            {"min_chunk_size_kb": 100 * 1024, "max_chunk_size_kb": 100 * 1024},
            "min_chunk_size",
            None,  # None signals to compare min_chunk_size == max_chunk_size
        ),
    ],
    ids=[
        "pii_threshold_min",
        "pii_threshold_max",
        "hap_threshold_min",
        "hap_threshold_max",
        "chunk_sizes_equal",
    ],
)
def test_config_validation_valid_edge_cases(config_override, expected_attr, expected_value):
    """Test that valid edge case configurations are accepted."""
    base_config = {
        "doc_column": "content",
        "provider": "litellm",
        "provider_config": {
            "model_id": "openai/granite4",
            "api_key": "api-key",  # pragma: allowlist secret
            "api_base": "http://localhost:11434/v1",
        },
    }
    config = {**base_config, **config_override}

    operator = PIIAndHAPAnnotator(config)

    if expected_value is None:
        # Special case: chunk sizes should be equal
        assert operator.min_chunk_size == operator.max_chunk_size
    else:
        assert getattr(operator, expected_attr) == expected_value


def test_expected_redactions_as_set(mock_pii_hap_service):
    """Test that expected_redactions is stored as a set with lowercase values."""
    # Test with mixed case input
    operator = PIIAndHAPAnnotator(
        {
            "doc_column": "content",
            "expected_redactions": [
                "PII",
                "HAP",
                "pii",
            ],  # Duplicate "pii" in different case
        }
    )

    # Verify it's a set
    assert isinstance(operator.expected_redactions, set), "expected_redactions should be a set"

    # Verify all values are lowercase
    assert operator.expected_redactions == {
        "pii",
        "hap",
    }, f"expected_redactions should be lowercase set, got {operator.expected_redactions}"

    # Verify set deduplication worked (only 2 unique values)
    assert len(operator.expected_redactions) == 2, (
        f"expected_redactions should have 2 unique values, got {len(operator.expected_redactions)}"
    )


def test_expected_redactions_default_value(mock_pii_hap_service):
    """Test that expected_redactions uses default value when not provided."""
    operator = PIIAndHAPAnnotator(
        {
            "doc_column": "content",
        }
    )

    # Verify default value is used and converted to set
    assert isinstance(operator.expected_redactions, set), "expected_redactions should be a set"
    assert "pii" in operator.expected_redactions, "Default should include 'pii'"
    assert "hap" in operator.expected_redactions, "Default should include 'hap'"


def test_expected_redactions_membership_check(mock_pii_hap_service):
    """Test that set membership checks work correctly for expected_redactions."""
    operator = PIIAndHAPAnnotator(
        {
            "doc_column": "content",
            "expected_redactions": ["PII", "HAP"],
        }
    )

    # Test O(1) membership checks
    assert "pii" in operator.expected_redactions, "'pii' should be in expected_redactions"
    assert "hap" in operator.expected_redactions, "'hap' should be in expected_redactions"
    assert "other" not in operator.expected_redactions, "'other' should not be in expected_redactions"

    # Verify case-insensitive (all stored as lowercase)
    assert "PII" not in operator.expected_redactions, "Uppercase 'PII' should not match (stored as lowercase)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
