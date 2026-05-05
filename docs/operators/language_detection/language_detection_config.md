# Language Detection Operator - Configuration Reference

## Overview

The Language Detection operator automatically detects the language of document content and provides confidence scores. It supports multiple detection providers through a pluggable adapter system.

- **Operator Name:** `lang_detect`
- **Category**: Quality
- **Short Name**: `lang_detect`

## Configuration Parameters

#### 1. `language_provider` (String)
**Type:** String  
**Required:** No  
**Default:** `"fasttext"`  
**Description:** Language detection provider to use.

**Valid Values:**
- `"fasttext"` - Facebook's FastText model (176+ languages, high accuracy)
- `"langdetect"` - Langdetect library (55+ languages, fast detection)

**Examples:**
```json
"language_provider": "fasttext"
"language_provider": "langdetect"
```

#### 2. `filter_unknown_language` (Boolean)
**Type:** Boolean  
**Required:** No  
**Default:** `false`  
**Description:** Whether to filter out documents where language detection fails or returns unknown language.

**Behavior:**
- `true`: Documents with detection failures are removed from the pipeline
- `false`: Documents with detection failures are marked as "UNKNOWN" with confidence 0.0

**Examples:**
```json
"filter_unknown_language": true
"filter_unknown_language": false
```

**The operator adds two columns to the PyArrow table:**

### 1. `lang_name` (String)
**Description:** ISO 639-1 language code of the detected language  
**Available for Filter:** Yes  
**Available for Vector DB:** Yes  
**Type:** String

**Example Values:**
- `"en"` - English
- `"es"` - Spanish
- `"fr"` - French
- `"de"` - German
- `"zh"` - Chinese
- `"UNKNOWN"` - Detection failed (when `filter_unknown_language: false`)

### 2. `lang_score` (Float)
**Description:** Confidence score of the language detection (0.0 to 1.0)  
**Available for Filter:** Yes  
**Type:** Float

**Example Values:**
- `0.95` - High confidence
- `0.75` - Medium confidence
- `0.50` - Low confidence
- `0.0` - Unknown language (detection failed)

## Configuration Examples

### Example 1: Basic FastText Configuration
```json
{
  "operator": "lang_detect",
  "config": {
    "language_provider": "fasttext",
  }
}
```

### Example 2: Langdetect with Filtering
```json
{
  "operator": "lang_detect",
  "config": {
    "language_provider": "langdetect",
    "filter_unknown_language": true,
  }
}
```

### Example 3: FastText with Unknown Language Handling
```json
{
  "operator": "lang_detect",
  "config": {
    "language_provider": "fasttext",
    "filter_unknown_language": false,
  }
}
```

## Complete Flow Example

```json
{
  "flow": {
    "name": "Language Detection Pipeline",
    "flow_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "description": "Pipeline: ingest → extract → language detection",
    "storage": "in-memory",
    "execute_type": "local",
    "global_config": {
      "doc_column": "content",
      "disable_validation": "true",
      "force_ingest": true
    },
    "dag": [
      {
        "id": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd",
        "name": "ingest",
        "operator": "ingest_local",
        "config": {
          "input_folder": "data/documents/",
          "include_filter": "txt,pdf",
          "max_workers": 2
        },
        "input_edges": [],
        "output_edges": [
          {
            "node_id_ref": "7cfd7577-b061-4fc9-92d5-120ae0fbde89"
          }
        ]
      },
      {
        "id": "7cfd7577-b061-4fc9-92d5-120ae0fbde89",
        "name": "extract",
        "operator": "extract_operator",
        "config": {
          "text_extraction_mode": "docling_library",
          "entity_extraction_mode": "none"
        },
        "input_edges": [
          {
            "node_id_ref": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd"
          }
        ],
        "output_edges": [
          {
            "node_id_ref": "8def9abc-c1d2-4e3f-9a0b-1c2d3e4f5a6b"
          }
        ]
      },
      {
        "id": "8def9abc-c1d2-4e3f-9a0b-1c2d3e4f5a6b",
        "name": "detect_language",
        "operator": "lang_detect",
        "config": {
          "language_provider": "fasttext",
          "filter_unknown_language": false
        },
        "input_edges": [
          {
            "node_id_ref": "7cfd7577-b061-4fc9-92d5-120ae0fbde89"
          }
        ],
        "output_edges": []
      }
    ]
  }
}
```

## Related Documentation

- [Language Detection Overview](src/datasift_opensource/backend/core/operators/quality/language_detection/README.md) - Detailed operator documentation
- [FastText Adapter](../../src/datasift_opensource/backend/core/operators/quality/language_detection/adapters/outbound/fasttext_adapter.py) - FastText implementation
- [Langdetect Adapter](../../src/datasift_opensource/backend/core/operators/quality/language_detection/adapters/outbound/langdetect_adapter.py) - Langdetect implementation
