# PII and HAP Operator - Configuration Parameters Documentation

## Overview
The PII and HAP (Personally Identifiable Information and Hate, Abuse, and Profanity) Annotator operator detects and optionally redacts sensitive information and harmful content from documents using LLM-based detection.

**Operator Name:** `pii_and_hap`  
**Category:** Quality  
**Short Name:** `pii_and_hap`

---

## Configuration Parameters

#### 1. `provider_config` (JSON/Dictionary)
**Type:** JSON Object  
**Required:** No
**Default:** `{}`  
**Description:** Provider-specific configuration dictionary containing authentication and connection details.

**Provider-Specific Requirements:**

##### For WatsonX Provider:
```json
{
  "api_key": "your-watsonx-api-key", # pragma: allowlist secret
  "url": "https://your-watsonx-instance.com",
  "container_kind": "project",
  "container_id": "your-project-id",
  "timeout": 300
}
```
- `api_key`: WatsonX API authentication key (required)
- `url`: WatsonX API endpoint URL (required)
- `container_kind`: Type of container ("project/space/catalog") (required)
- `container_id`: Project or space ID (required)
- `timeout`: Request timeout in seconds (optional, default: 300)

##### For Ollama Provider:
```json
{
  "model_name": "granite4"
}
```
- `model_name`: Name of the Ollama model to use (optional, uses operator-level model_name if not specified)

##### For LiteLLM Provider:
```json
{
  "api_base": "http://localhost:8000",
  "api_key": "your-api-key" # pragma: allowlist secret
}
```
- `api_base`: OpenAI-compatible API endpoint (optional, provider-specific)
- `api_key`: API key for authentication (optional, provider-specific)

**Note:** For LiteLLM, `model_name` is specified at the operator level (not in `provider_config`). LiteLLM supports 100+ providers including OpenAI, Anthropic, Azure OpenAI, Cohere, AWS Bedrock, Google Vertex AI, and more. The `api_key` and `api_base` requirements depend on the specific provider being used.

**Examples:**
- OpenAI: Requires `api_key` (uses default OpenAI endpoint)
- Azure OpenAI: Requires `api_key` and `api_base`
- Anthropic: Requires `api_key` (uses default Anthropic endpoint)
- Local providers: May not require `api_key`

#### 2. `redaction` (Boolean)
**Type:** Boolean  
**Required:** Yes  
**Default:** `false`  
**Description:** Enable or disable PII redaction in document content.

**Valid Values:** `true`, `false`

#### 3. `hap_redaction` (Boolean)
**Type:** Boolean  
**Required:** Yes  
**Default:** `false`  
**Description:** Enable or disable HAP (Hate, Abuse, Profanity) redaction in document content.

**Valid Values:** `true`, `false`

#### 4. `provider` (String)
**Type:** String
**Required:** No
**Default:** `"litellm"`
**Description:** Detection provider to use for PII/HAP analysis.

**Valid Values:** `"watsonx"`, `"litellm"`

**Examples:**
```json
"provider": "watsonx"
"provider": "litellm"
```

#### 5. `model_name` (String)
**Type:** String
**Required:** No
**Default:** `"granite4"`
**Description:** Name of the model to use for detection. Required for [`"litellm"`](docs/operators/pii_and_hap/pii_and_hap_config.md) flows and ignored by native WatsonX text detection.

**Examples:**
```json
"model_name": "granite4"
"model_name": "llama3.2"
"model_name": "mistral"
```

#### 6. `expected_redactions` (List)
**Type:** List of Strings  
**Required:** No  
**Default:** `["pii", "hap"]`
**Description:** List of detection types to perform and potentially redact.

**Valid Values:** `["PII", "HAP"]` or any subset  
**Examples:**
```json
"expected_redactions": ["pii", "hap"]
"expected_redactions": ["pii"]
"expected_redactions": ["hap"]
```

#### 7. `pii_list` (List)
**Type:** List of Strings
**Required:** No
**Default:** `["BankAccountNumber", "CreditCardNumber", "EmailAddress", "IPAddress", "PhoneNumber", "SocialSecurityNumber"]`
**Description:** Specific PII types to detect and redact.

**Valid Values:**
- `"BankAccountNumber"` - Bank account numbers
- `"CreditCardNumber"` - Credit card numbers
- `"EmailAddress"` - Email addresses
- `"IPAddress"` - IP addresses
- `"PhoneNumber"` - Phone numbers
- `"SocialSecurityNumber"` - Social Security Numbers

**Examples:**
```json
"pii_list": ["EmailAddress", "PhoneNumber", "SocialSecurityNumber"]
"pii_list": ["CreditCardNumber", "BankAccountNumber"]
```

#### 8. `redaction_character` (String)
**Type:** String  
**Required:** No  
**Default:** `"*"`  
**Description:** Character used to mask/redact PII content.

**Examples:**
```json
"redaction_character": "*"
"redaction_character": "#"
"redaction_character": "X"
```

#### 9. `hap_redaction_character` (String)
**Type:** String  
**Required:** No  
**Default:** `"*"`  
**Description:** Character used to mask/redact HAP content.

**Examples:**
```json
"hap_redaction_character": "*"
"hap_redaction_character": "#"
```

#### 10. `pii_threshold` (Float)
**Type:** Float  
**Required:** No  
**Default:** `0.5`  
**Range:** `0.0` to `1.0`  
**Description:** Confidence threshold for PII detection. Detections below this threshold are ignored.

**Examples:**
```json
"pii_threshold": 0.5
"pii_threshold": 0.7
"pii_threshold": 0.9
```

#### 11. `hap_threshold` (Float)
**Type:** Float  
**Required:** No  
**Default:** `0.8`
**Range:** `0.0` to `1.0`  
**Description:** Confidence threshold for HAP detection. Detections below this threshold are ignored.

**Examples:**
```json
"hap_threshold": 0.5
"hap_threshold": 0.8
```

#### 12. `display_pii` (Boolean)
**Type:** Boolean
**Required:** No
**Default:** `false`
**Description:** Include actual PII values in output columns for debugging/analysis purposes.

**Valid Values:** `true`, `false`

**Warning:** Setting this to `true` will expose sensitive PII data in output columns. Use only for debugging in secure environments.

---

## Features

The operator adds the following feature columns to the output table:

### PII Detection Columns

#### 1. `pii_bank_account` (Integer)
**Description:** Count of bank account numbers detected in the document  
**Available for Filter:** Yes  
**Type:** Integer

#### 2. `pii_credit_card` (Integer)
**Description:** Count of credit card numbers detected in the document  
**Available for Filter:** Yes  
**Type:** Integer

#### 3. `pii_email_address` (Integer)
**Description:** Count of email addresses detected in the document  
**Available for Filter:** Yes  
**Type:** Integer

#### 4. `pii_ip_address` (Integer)
**Description:** Count of IP addresses detected in the document  
**Available for Filter:** Yes  
**Type:** Integer

#### 5. `pii_phone_number` (Integer)
**Description:** Count of phone numbers detected in the document  
**Available for Filter:** Yes  
**Type:** Integer

#### 6. `pii_ssn_details` (Integer)
**Description:** Count of Social Security Numbers detected in the document  
**Available for Filter:** Yes  
**Type:** Integer

### HAP Detection Columns

#### 7. `hap` (Integer)
**Description:** Count of HAP (Hate, Abuse, Profanity) instances detected in the document  
**Available for Filter:** Yes  
**Type:** Integer

### Optional Display Columns (when `display_pii: true`)

When `display_pii` is enabled, additional columns are added with the actual detected PII values:
- `pii_bank_account_info_column`
- `pii_credit_card_info_column`
- `pii_email_address_info_column`
- `pii_ip_address_info_column`
- `pii_phone_number_info_column`
- `pii_ssn_details_info_column`

**Warning:** These columns contain actual sensitive data and should only be used in secure testing environments.

---

## Complete Configuration Examples

### Example 1: Basic Ollama Configuration with PII Detection Only
```json
{
  "operator": "pii_and_hap",
  "config": {
    "provider": "ollama",
    "model_name": "granite4",
    "provider_config": {},
    "expected_redactions": ["pii"],
    "pii_list": ["EmailAddress", "PhoneNumber", "SocialSecurityNumber"],
    "redaction": true,
    "redaction_character": "*",
    "pii_threshold": 0.7
  }
}
```

### Example 2: WatsonX Configuration with Both PII and HAP
```json
{
  "operator": "pii_and_hap",
  "config": {
    "provider": "watsonx",
    "provider_config": {
      "api_key": "your-watsonx-api-key", # pragma: allowlist secret
      "url": "https://us-south.ml.cloud.ibm.com",
      "container_kind": "project",
      "container_id": "your-project-id"
    },
    "expected_redactions": ["pii", "hap"],
    "pii_list": ["BankAccountNumber", "CreditCardNumber", "EmailAddress", "PhoneNumber", "SocialSecurityNumber"],
    "redaction": true,
    "hap_redaction": true,
    "redaction_character": "#",
    "hap_redaction_character": "*",
    "pii_threshold": 0.8,
    "hap_threshold": 0.7
  }
}
```

### Example 3: LiteLLM Configuration with Selective PII Detection
```json
{
  "operator": "pii_and_hap",
  "config": {
    "provider": "litellm",
    "model_name": "gpt-4",
    "provider_config": {
      "api_key": "your-openai-api-key" # pragma: allowlist secret
    },
    "expected_redactions": ["pii"],
    "pii_list": ["CreditCardNumber", "BankAccountNumber"],
    "redaction": true,
    "pii_threshold": 0.9
  }
}
```

### Example 4: Debug Configuration with PII Display
```json
{
  "operator": "pii_and_hap",
  "config": {
    "provider": "ollama",
    "model_name": "llama3.2:3b",
    "provider_config": {},
    "expected_redactions": ["pii"],
    "pii_list": ["EmailAddress", "PhoneNumber"],
    "redaction": false,
    "display_pii": true,
    "pii_threshold": 0.5
  }
}
```
---

## Validation Rules

### Configuration Validation

1. **Provider Config Validation:**
   - WatsonX requires: `api_key`, `url`, `container_kind`, `container_id`
   - Missing required keys will cause validation error

2. **Threshold Validation:**
   - `pii_threshold` must be between 0.0 and 1.0
   - `hap_threshold` must be between 0.0 and 1.0

3. **Redaction List Validation:**
   - `expected_redactions` must be subset of `["pii", "hap"]`
   - `pii_list` must be subset of valid PII types

---

## Common Issues and Troubleshooting

### Issue 1: Provider Connection Failures
**Symptoms:** Operator fails with connection errors

**Solutions:**
- Verify provider service is running (Ollama: `http://localhost:11434`)
- Check `provider_config` credentials for WatsonX/LiteLLM
- Verify network connectivity

### Issue 2: Low Detection Accuracy
**Symptoms:** Missing obvious PII/HAP or too many false positives

**Solutions:**
- Adjust `pii_threshold` and `hap_threshold`
- Try different models
- Verify document content quality

### Issue 3: Performance Issues
**Symptoms:** Slow processing

**Solutions:**
- Use faster provider/model
- Optimize document preprocessing
- Consider provider-specific performance tuning

---

## Dependencies

### Required Services
- **Ollama** (if using ollama provider): Local LLM service
- **WatsonX** (if using watsonx provider): IBM WatsonX API access
- **LiteLLM** (if using litellm provider): OpenAI-compatible API endpoint

---

## Security Considerations

1. **PII Exposure:**
   - Never use `display_pii: true` in production
   - Ensure redacted content is properly masked
   - Audit output columns for sensitive data

2. **API Credentials:**
   - Store `provider_config` credentials securely
   - Never commit credentials to version control

---
