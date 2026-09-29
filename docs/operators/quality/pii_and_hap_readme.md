# PIIAndHAPAnnotator

Detects and optionally redacts Personally Identifiable Information (PII) and Hate, Abuse &
Profanity (HAP) content from document text using LLM-based detection.

- **Short Name:** `pii_and_hap`
- **Category:** Quality

---

## Overview

`PIIAndHAPAnnotator` scans each document's text content for PII (emails, phone numbers, credit
card numbers, etc.) and HAP language using a configurable LLM provider (LiteLLM or WatsonX).
Detected instances are counted in dedicated output columns; when redaction is enabled the
matched spans are replaced with a masking character in the original content column.

---

## Key Features

- LLM-based detection via LiteLLM (100+ providers including Ollama) or WatsonX native API
- Separate detection and redaction toggles for PII and HAP
- Configurable confidence thresholds for both PII and HAP
- Selectable PII types to detect (13 built-in categories)
- Debug mode (`display_pii`) to surface detected values in output columns
- Graceful per-document error handling — failed documents are logged and skipped

---

## Operator Configuration

```json
{
  "type": "pii_and_hap",
  "name": "detect_pii_hap",
  "config": {
    "provider": "litellm",
    "provider_config": {
      "model_id": "openai/granite4",
      "api_base": "http://localhost:11434/v1",
      "api_key": "<ollama>"
    },
    "expected_redactions": ["pii", "hap"],
    "redaction": true,
    "hap_redaction": true,
    "pii_threshold": 0.5,
    "hap_threshold": 0.8
  },
  "depends_on": ["extract_documents"]
}
```

---

## Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `provider` | string | No | `"litellm"` | Detection provider: `litellm` or `watsonx` |
| `provider_config` | object | No | `{}` | Provider-specific config (see below) |
| `redaction` | boolean | No | `false` | Replace detected PII spans with `redaction_character` |
| `hap_redaction` | boolean | No | `false` | Replace detected HAP spans with `hap_redaction_character` |
| `expected_redactions` | list | No | `["pii","hap"]` | Detection types to run: any subset of `["pii","hap"]` |
| `pii_list` | list | No | all 13 types | PII types to detect (see supported types below) |
| `redaction_character` | string | No | `"*"` | Masking character for PII redaction |
| `hap_redaction_character` | string | No | `"*"` | Masking character for HAP redaction |
| `pii_threshold` | float | No | `0.5` | Confidence threshold for PII detection (0.0–1.0) |
| `hap_threshold` | float | No | `0.8` | Confidence threshold for HAP detection (0.0–1.0) |
| `display_pii` | boolean | No | `false` | Add extra columns with actual PII values (**testing only**) |

### LiteLLM `provider_config`

| Field | Type | Required | Description |
|---|---|---|---|
| `model_id` | string | Yes | Model ID with provider prefix (e.g. `openai/granite4` for Ollama) |
| `api_base` | string | No | API endpoint URL (e.g. `http://localhost:11434/v1` for Ollama) |
| `api_key` | string | No | Authentication key |

### WatsonX `provider_config`

| Field | Type | Required | Description |
|---|---|---|---|
| `model_id` | string | Yes | WatsonX model identifier |
| `api_key` | string | Yes | IBM Cloud API key |
| `api_base` | string | Yes | WatsonX endpoint URL |
| `container_kind` | string | Yes | `"project"` or `"space"` |
| `container_id` | string | Yes | Project or space UUID |
| `timeout` | integer | No | Request timeout in seconds (default: `300`) |

### Supported PII types (`pii_list`)

| Type | Description |
|---|---|
| `BankAccountNumber` | Bank account numbers |
| `CreditCardNumber` | Credit/debit card numbers |
| `EmailAddress` | Email addresses |
| `IPAddress` | IPv4 and IPv6 addresses |
| `PhoneNumber` | Phone and fax numbers |
| `SocialSecurityNumber` | US Social Security Numbers |
| `PersonName` | Full or partial person names |
| `DateOfBirth` | Dates of birth |
| `Address` | Physical addresses |
| `PassportNumber` | Passport numbers |
| `DriverLicenseNumber` | Driver's license numbers |
| `NationalID` | National identity numbers |
| `MedicalRecordNumber` | Medical record numbers |

When `pii_list` is omitted, all 13 types are detected by default.

---

## Output Columns

All original columns are preserved. The operator appends:

| Column | PyArrow Type | Description |
|---|---|---|
| `pii_bank_account` | `int64` | Count of bank account numbers detected |
| `pii_credit_card` | `int64` | Count of credit card numbers detected |
| `pii_email_address` | `int64` | Count of email addresses detected |
| `pii_ip_address` | `int64` | Count of IP addresses detected |
| `pii_phone_number` | `int64` | Count of phone numbers detected |
| `pii_ssn_details` | `int64` | Count of Social Security Numbers detected |
| `pii_person_name` | `int64` | Count of person names detected |
| `pii_date_of_birth` | `int64` | Count of dates of birth detected |
| `pii_address` | `int64` | Count of physical addresses detected |
| `pii_passport_number` | `int64` | Count of passport numbers detected |
| `pii_driver_license` | `int64` | Count of driver's license numbers detected |
| `pii_national_id` | `int64` | Count of national identity numbers detected |
| `pii_medical_record` | `int64` | Count of medical record numbers detected |
| `hap` | `int64` | Count of HAP instances detected |

When `display_pii: true`, additional `*_info` columns are added for each PII type containing the actual detected values. **Never enable in production.**

---

## Examples

### Example 1 — PII detection only (Ollama via LiteLLM)

```json
{
  "type": "pii_and_hap",
  "name": "detect_pii",
  "config": {
    "provider": "litellm",
    "provider_config": {
      "model_id": "openai/granite4",
      "api_base": "http://localhost:11434/v1",
      "api_key": "<ollama>"
    },
    "expected_redactions": ["pii"],
    "pii_list": ["EmailAddress", "PhoneNumber", "SocialSecurityNumber"],
    "redaction": true,
    "pii_threshold": 0.7
  },
  "depends_on": ["extract"]
}
```

### Example 2 — PII and HAP with WatsonX

```json
{
  "type": "pii_and_hap",
  "name": "detect_pii_hap",
  "config": {
    "provider": "watsonx",
    "provider_config": {
      "model_id": "ibm/granite-13b-chat-v2",
      "api_key": "${WATSONX_API_KEY}",
      "api_base": "https://us-south.ml.cloud.ibm.com",
      "container_kind": "project",
      "container_id": "${WATSONX_PROJECT_ID}"
    },
    "expected_redactions": ["pii", "hap"],
    "redaction": true,
    "hap_redaction": true,
    "pii_threshold": 0.8,
    "hap_threshold": 0.7
  },
  "depends_on": ["extract"]
}
```

### Example 3 — Debug: surface detected PII values (testing only)

```json
{
  "type": "pii_and_hap",
  "name": "debug_pii",
  "config": {
    "provider": "litellm",
    "provider_config": {
      "model_id": "openai/llama3.2:3b",
      "api_base": "http://localhost:11434/v1",
      "api_key": "<ollama>"
    },
    "expected_redactions": ["pii"],
    "pii_list": ["EmailAddress", "PhoneNumber"],
    "redaction": false,
    "display_pii": true
  },
  "depends_on": ["extract"]
}
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Connection errors to provider | LLM service not running or wrong `api_base` | Verify Ollama is running (`ollama serve`); check `api_base` and credentials |
| Low detection accuracy / many false positives | Model or threshold mismatch | Adjust `pii_threshold` / `hap_threshold`; try a larger or more capable model |
| `ValidationError` for WatsonX | Missing required `provider_config` fields | Ensure `api_key`, `api_base`, `container_kind`, `container_id` are all set |
| Old flows using `provider: "ollama"` fail | Direct Ollama provider was removed | Migrate to `provider: "litellm"` with `openai/` model prefix (see Architecture section) |

---

## Architecture

### Detection paths

The operator uses a decorator-based adapter registry. Each provider adapter self-registers with `PIIAndHAPDetectionFactory` via `@register_pii_and_hap_detection_adapter` and fully encapsulates its own detection path behind the unified `PIIAndHAPDetectionPort.detect()` interface:

1. **WatsonX** (`WatsonxPIIAndHAPAdapter`): Uses the native `/ml/v1/text/detection` API — optimised for PII/HAP, no prompt engineering required.
2. **LiteLLM** (`LiteLLMPIIAndHAPAdapter`): Prompt-based detection via chat completion — supports 100+ providers including Ollama.

Adding a new provider is a single-file change: create the adapter module, decorate it with `@register_pii_and_hap_detection_adapter`, and it is automatically discoverable.

### Migration from legacy Ollama provider

Direct `"provider": "ollama"` support was removed. Migrate as follows:

```json
// Before (no longer supported)
{ "provider": "ollama", "model_name": "granite4" }

// After (required)
{
  "provider": "litellm",
  "model_name": "openai/granite4",
  "provider_config": {
    "api_key": "ollama", // pragma: allowlist secret
    "api_base": "http://localhost:11434/v1"
  }
}
```

### Typical pipeline position

```
Ingest → Extract → PIIAndHAPAnnotator → [Chunker → Embeddings → VectorDB]
```

## Sample Flow

See [`sample_flows/operators/pii_hap_detection.json`](../../../sample_flows/operators/pii_hap_detection.json) for a complete example using PII and HAP detection.
