# PII and HAP Annotator

## Overview

The PII and HAP Annotator is an operator that detects Personally Identifiable Information (PII) and Hate, Abuse, and Profanity (HAP) content in documents using local LLM models via Ollama or OpenAI-compatible APIs (like vLLM).

## Features

- **PII Detection**: Identifies various types of personally identifiable information including:
  - Email addresses
  - Phone numbers
  - Social Security Numbers (SSN)
  - Credit card numbers
  - Bank account numbers
  - IP addresses
  - Person names
  - Physical addresses
  - Dates of birth

- **HAP Detection**: Identifies harmful content including:
  - Hate speech
  - Abusive language
  - Profanity
  - Harassment

- **Flexible Backend Support**:
  - **Ollama**: Use local models running via Ollama
  - **OpenAI**: Use OpenAI-compatible APIs (e.g., vLLM, local OpenAI servers)

- **Configurable Thresholds**: Set confidence thresholds for both PII and HAP detection
- **Parallel Processing**: Process multiple documents concurrently for better performance
- **Detailed Results**: Get both counts and detailed JSON results for each detection

## Configuration

### Basic Configuration

```python
{
    "detection_type": "ollama",  # or "openai"
    "model_name": "llama2",
    "redaction": True,
    "redaction_character": "*",
    "hap_redaction": True,
    "hap_redaction_character": "*",
    "pii_threshold": 0.5,
    "hap_threshold": 0.75,
    "doc_column": "content",
    "batch_size": 4,
    "expected_redactions": ["PII", "HAP"],
    "pii_list": ["email_address", "phone_number", "ssn_details"]
}
```

### Ollama Configuration

```python
{
    "detection_type": "ollama",
    "model_name": "llama2",  # or any Ollama model
    "redaction": True,
    "hap_redaction": True,
    "pii_threshold": 0.5,
    "hap_threshold": 0.75,
    "expected_redactions": ["PII", "HAP"]
}
```

### OpenAI-Compatible API Configuration

```python
{
    "detection_type": "openai",
    "model_name": "llama-3-8b",  # Model loaded in vLLM
    "openai_base_url": "http://localhost:8000/v1",
    "openai_api_key": "not-needed",  # Often ignored by local servers
    "redaction": True,
    "hap_redaction": True,
    "pii_threshold": 0.5,
    "hap_threshold": 0.75
}
```

## Parameters

| Parameter                 | Type    | Required | Default                          | Description                              |
| ------------------------- | ------- | -------- | -------------------------------- | ---------------------------------------- |
| `detection_type`          | string  | No       | "ollama"                         | Backend to use: "ollama" or "openai"     |
| `model_name`              | string  | No       | "llama2"                         | Model name to use                        |
| `redaction`               | boolean | No       | False                            | Enable PII redaction/masking             |
| `redaction_character`     | string  | No       | "X"                              | Character to use for PII masking         |
| `hap_redaction`           | boolean | No       | False                            | Enable HAP redaction/masking             |
| `hap_redaction_character` | string  | No       | "X"                              | Character to use for HAP masking         |
| `pii_threshold`           | float   | No       | 0.5                              | Confidence threshold for PII (0.0-1.0)   |
| `hap_threshold`           | float   | No       | 0.75                             | Confidence threshold for HAP (0.0-1.0)   |
| `expected_redactions`     | list    | No       | ["PII", "HAP"]                   | List of redaction types to perform       |
| `pii_list`                | list    | No       | See DEFAULT_PII_TYPES_OF_CONCERN | List of PII types to detect              |
| `display_pii`             | boolean | No       | False                            | Include detailed PII values in output    |
| `batch_size`              | integer | No       | 4                                | Number of parallel processing threads    |
| `min_chunk_size_kb`       | integer | No       | 51200 (50KB)                     | Minimum chunk size for processing        |
| `max_chunk_size_kb`       | integer | No       | 102400 (100KB)                   | Maximum chunk size for processing        |
| `openai_base_url`         | string  | No\*     | None                             | Base URL for OpenAI-compatible API       |
| `openai_api_key`          | string  | No       | "not-needed"                     | API key for OpenAI-compatible API        |
| `doc_column`              | string  | No       | "content"                        | Column containing document text          |
| `partial_ingest`          | boolean | No       | False                            | Continue processing on document failures |

\* Required when `detection_type` is "openai"

## Output Columns

The operator adds the following columns to the output table for each PII type:

### PII Columns (per type)

- `pii_email_address` (integer): Count of email addresses detected
- `pii_phone_number` (integer): Count of phone numbers detected
- `pii_ssn_details` (integer): Count of SSNs detected
- `pii_credit_card` (integer): Count of credit card numbers detected
- `pii_bank_account` (integer): Count of bank account numbers detected
- `pii_ip_address` (integer): Count of IP addresses detected

### HAP Columns

- `hap` (integer): Total number of HAP instances detected

### Optional Display Columns (when `display_pii=True`)

- `pii_email_address_display` (string): Detailed email address detections
- `pii_phone_number_display` (string): Detailed phone number detections
- And similar display columns for other PII types

## Usage Example

### Using Ollama

```python
from core.operators.universal.pii_and_hap import PIIAndHAPAnnotator

config = {
    "detection_type": "ollama",
    "model_name": "llama2",
    "redaction": True,
    "redaction_character": "*",
    "hap_redaction": True,
    "hap_redaction_character": "*",
    "pii_threshold": 0.5,
    "hap_threshold": 0.75,
    "doc_column": "content",
    "batch_size": 4,
    "expected_redactions": ["PII", "HAP"],
    "pii_list": ["email_address", "phone_number", "ssn_details"]
}

operator = PIIAndHAPAnnotator(config)
output_tables, metadata = operator.transform(input_table)
```

### Using OpenAI-Compatible API (vLLM)

```python
from core.operators.universal.pii_and_hap import PIIAndHAPAnnotator

config = {
    "detection_type": "openai",
    "model_name": "llama-3-8b",
    "openai_base_url": "http://localhost:8000/v1",
    "openai_api_key": "not-needed",
    "redaction": True,
    "hap_redaction": True,
    "pii_threshold": 0.5,
    "hap_threshold": 0.75,
    "doc_column": "content",
    "expected_redactions": ["PII", "HAP"]
}

operator = PIIAndHAPAnnotator(config)
output_tables, metadata = operator.transform(input_table)
```

## Dependencies

### For Ollama Backend

```bash
pip install ollama
```

### For OpenAI Backend

```bash
pip install openai
```

## Performance Considerations

1. **Model Selection**: Larger models provide better accuracy but are slower
2. **Parallel Processing**: Adjust `batch_size` based on your system resources and available CPU/GPU
3. **Chunking Configuration**:
   - Use `min_chunk_size_kb` and `max_chunk_size_kb` to control memory usage
   - Smaller chunks process faster but may lose context
   - Larger chunks provide better context but use more memory
4. **Thresholds**: Higher thresholds reduce false positives but may miss some detections
5. **Redaction**: Enabling redaction adds processing overhead but provides data protection

## Future Enhancements

- Support for additional PII types (passport numbers, driver's license, etc.)
- Batch processing optimizations for very large document sets
- Custom detection rules and patterns
- Integration with more LLM providers (Anthropic, Cohere, etc.)
- Enhanced redaction strategies (partial masking, tokenization)

## License

Copyright IBM Corp. 2025
SPDX-License-Identifier: Apache-2.0
