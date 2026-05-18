# Redaction Operator Configuration Reference

## Overview
The Redaction operator masks or redacts text that matches a given word or regex pattern. It replaces matched content with a masking character and provides statistics on the number of redactions performed.

- **Short Name**: `redaction`
- **Category**: Quality
- **Operator Name:** `redaction`

## Configuration Parameters

### 1. redaction_regex
- **Type**: String
- **Required**: Yes
- **Default**: null
- **Description**: The pattern or word to be masked/redacted

**Pattern Types:**
- **Literal Word**: Simple word to redact (e.g., `"confidential"`)
- **Regex Pattern**: Regular expression for complex matching (e.g., `"\d{3}-\d{2}-\d{4}"` for SSN)

**Examples:**
```json
// Literal word
"redaction_regex": "confidential"

// Email pattern (basic, commonly used)
"redaction_regex": "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}"

// Phone number pattern (US format: 123-456-7890)
"redaction_regex": "\\b\\d{3}-\\d{3}-\\d{4}\\b"

// SSN pattern (XXX-XX-XXXX)
"redaction_regex": "\\b\\d{3}-\\d{2}-\\d{4}\\b"

// Credit card pattern (basic 16-digit with optional spaces/dashes)
"redaction_regex": "\\b\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}\\b"
```

### 2. redaction_masking_character
- **Type**: String
- **Required**: No
- **Default**: `"*"`
- **Description**: Single character used for masking matched text

**Examples:**
```json
"redaction_masking_character": "*"  // Default
"redaction_masking_character": "#"
"redaction_masking_character": "X"
"redaction_masking_character": "█"
```

## Output Features

### 1. redaction_stats
- **Column**: Value of `stats_column` parameter (default: `"redaction_stats"`)
- **Type**: Integer
- **Description**: Number of matches found and redacted in the document
- **Filterable**: Yes

## Configuration Examples

### Example 1: Simple Word Redaction
```json
{
  "id": "c2d4e6f8-9a1b-4c3d-8e7f-5a6b2c1d9e0f",
  "operator": "redaction",
  "config": {
    "redaction_regex": "confidential",
    "redaction_masking_character": "*"
  }
}
```

**Input:**
```
This is a confidential document containing confidential information.
```

**Output:**
```
This is a ************ document containing ************ information.
```

### Example 2: Email Redaction
```json
{
  "id": "c2d4e6f8-9a1b-4c3d-8e7f-5a6b2c1d9e0f",
  "operator": "redaction",
  "config": {
    "redaction_regex": "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}",
    "redaction_masking_character": "#"
  }
}
```

**Input:**
```
Contact us at support@example.com or sales@company.org
```

**Output:**
```
Contact us at ##################### or ##################
```

## Complete Flow Example

```json
{
  "flow_name": "PII Redaction Pipeline",
  "description": "Ingest, extract, and redact sensitive information",
  "flow": [
    {
      "name": "ingest_documents",
      "type": "ingest_local_folder",
      "config": {
        "input_folder": "./sample_documents",
      }
    },
    {
      "name": "extract_documents",
      "type": "extract_operator",
      "depends_on": ["ingest_documents"],
      "config": {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "none"
      }
    },
    {
      "name": "redact_emails",
      "type": "redaction",
      "depends_on": ["extract_documents"],
      "config": {
        "redaction_regex": "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}",
        "redaction_masking_character": "*",
        "stats_column": "email_redactions"
      }
    },
    {
      "name": "redact_phone_numbers",
      "type": "redaction",
      "depends_on": ["redact_emails"],
      "config": {
        "redaction_regex": "\\b\\d{3}-\\d{3}-\\d{4}\\b",
        "redaction_masking_character": "#",
        "stats_column": "phone_redactions"
      }
    }
  ]
}
```

## Common Redaction Patterns

### Personal Information

#### Email Addresses
```json
"redaction_regex": "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}"
```

#### Phone Numbers (US Format)
```json
// With dashes: 555-123-4567
"redaction_regex": "\\d{3}-\\d{3}-\\d{4}"

// With parentheses: (555) 123-4567
"redaction_regex": "\\(\\d{3}\\)\\s*\\d{3}-\\d{4}"

// Any format
"redaction_regex": "\\(?\\d{3}\\)?[\\s.-]?\\d{3}[\\s.-]?\\d{4}"
```

#### Social Security Numbers
```json
"redaction_regex": "\\d{3}-\\d{2}-\\d{4}"
```

#### Credit Card Numbers
```json
"redaction_regex": "\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}"
```

### Financial Information

#### Bank Account Numbers
```json
"redaction_regex": "\\b\\d{8,17}\\b"
```

#### Routing Numbers
```json
"redaction_regex": "\\b\\d{9}\\b"
```

### Identification

#### Passport Numbers (US)
```json
"redaction_regex": "[A-Z]{1,2}\\d{6,9}"
```

#### Driver's License (varies by state)
```json
"redaction_regex": "[A-Z]{1,2}\\d{5,8}"
```

### Network Information

#### IP Addresses (IPv4)
```json
"redaction_regex": "\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b"
```

#### MAC Addresses
```json
"redaction_regex": "([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})"
```

### Custom Patterns

#### Specific Words or Phrases
```json
"redaction_regex": "\\b(confidential|secret|private)\\b"
```

#### Case-Insensitive Matching
Use `(?i)` flag in regex:
```json
"redaction_regex": "(?i)\\b(confidential|secret|private)\\b"
```

## Best Practices

1. **Test Patterns**: Verify regex patterns on sample data before production
2. **Escape Properly**: Remember to double-escape backslashes in JSON
3. **Use Word Boundaries**: Add `\b` to avoid partial word matches
4. **Chain Operators**: Use multiple redaction operators for different patterns
5. **Monitor Stats**: Check `redaction_stats` column to verify redactions
6. **Case Sensitivity**: Use `(?i)` flag for case-insensitive matching
7. **Validate Results**: Spot-check redacted documents to ensure accuracy
