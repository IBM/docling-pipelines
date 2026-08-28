# LanguageDetectionOperator

Detects the language of document text and appends ISO 639-1 language code and confidence score columns.

- **Short Name:** `lang_detect`
- **Category:** Quality

---

## Overview

`LanguageDetectionOperator` runs each document's text through a pluggable language detection
adapter and adds two columns — `lang_name` (ISO 639-1 code) and `lang_score` (confidence
0.0–1.0) — to the output table. Documents that fail detection are either removed (when
`filter_unknown_language: true`) or marked as `UNKNOWN` with a score of `0.0`.

Two adapters are bundled: `fasttext` (default, 176+ languages) and `langdetect` (55 languages,
no setup required). The adapter system is extensible — add a custom adapter by implementing
`LanguageServicePort`.

---

## Key Features

- Two built-in providers: `fasttext` (176+ languages) and `langdetect` (55 languages)
- FastText model loaded as a singleton (thread-safe, memory-efficient)
- Configurable handling of unknown/failed detections
- Extensible via `LanguageServicePort` adapter interface

---

## Operator Configuration

```json
{
  "name": "detect_language",
  "type": "lang_detect",
  "config": {
    "doc_column": "content",
    "filter_unknown_language": false
  },
  "depends_on": ["extract"]
}
```

With `langdetect` provider:
```json
{
  "name": "detect_language",
  "type": "lang_detect",
  "config": {
    "doc_column": "content",
    "language_provider": "langdetect",
    "filter_unknown_language": false
  },
  "depends_on": ["extract"]
}
```

### Complete Pipeline Example

```json
{
  "flow_name": "Language Detection Pipeline",
  "description": "Example flow with language detection",
  "global_config": {
    "doc_column": "content",
    "storage": "in-memory",
    "execute_type": "local"
  },
  "flow": [
    {
      "name": "ingest",
      "type": "ingest_source",
      "config": {
        "provider": "filesystem",
        "connection_params": {"paths": ["data/documents"]}
      }
    },
    {
      "name": "extract",
      "type": "extract_operator",
      "depends_on": ["ingest"],
      "config": {
        "text_extraction": {
          "provider": "docling_library"
        },
        "entity_extraction": {
          "provider": "none"
        }
      }
    },
    {
      "name": "detect_language",
      "type": "lang_detect",
      "depends_on": ["extract"],
      "config": {
        "language_provider": "fasttext",
        "filter_unknown_language": false
      }
    },
    {
      "name": "chunk",
      "type": "chunker",
      "depends_on": ["detect_language"],
      "config": {
        "chunk_size": 512
      }
    }
  ]
}
```

---

## Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `doc_column` | string | No | `"content"` | Column containing text to detect |
| `language_provider` | string | No | `"fasttext"` | Provider: `fasttext` or `langdetect` |
| `filter_unknown_language` | boolean | No | `false` | When `true`, rows with detection errors are removed; when `false` they are marked `UNKNOWN` |

---

## Output Columns

All input columns are preserved. The operator appends:

| Column | PyArrow Type | Description |
|---|---|---|
| `lang_name` | `string` | ISO 639-1 language code (e.g. `"en"`, `"fr"`) or `"UNKNOWN"` on detection failure |
| `lang_score` | `float32` | Confidence score (0.0–1.0); set to `0.0` for `UNKNOWN` |

---

## Examples

### Example 1 — fasttext (default)

```json
{
  "name": "detect_language",
  "type": "lang_detect",
  "config": {
    "language_provider": "fasttext",
    "filter_unknown_language": false
  },
  "depends_on": ["extract"]
}
```

### Example 2 — langdetect, filter unknowns

```json
{
  "name": "detect_language",
  "type": "lang_detect",
  "config": {
    "language_provider": "langdetect",
    "filter_unknown_language": true
  },
  "depends_on": ["extract"]
}
```

### Example 3 — Complete pipeline

```json
{
  "flow_name": "Language Detection Pipeline",
  "flow": [
    { "name": "ingest", "type": "ingest_source", "config": { "provider": "filesystem", "connection_params": {"paths": ["data/documents"]} } },
    { "name": "extract", "type": "extract_operator", "depends_on": ["ingest"],
      "config": { "text_extraction": { "provider": "docling_library" }, "entity_extraction": { "provider": "none" } } },
    { "name": "detect_language", "type": "lang_detect", "depends_on": ["extract"],
      "config": { "language_provider": "fasttext", "filter_unknown_language": false } },
    { "name": "chunk", "type": "chunker", "depends_on": ["detect_language"],
      "config": { "chunk_size": 512 } }
  ]
}
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ValueError: Text cannot be empty` | Document content column is empty | Ensure `ExtractOperator` runs before this step |
| `ValueError: No features in text` | Text contains only numbers or special characters | Accept the `UNKNOWN` label or pre-filter non-text rows |
| FastText model download slow | First-run model download (~131 MB) | Pre-download or cache the model file |
| Many documents marked `UNKNOWN` | Short texts (<20 chars) are hard to detect reliably | Use longer text or set `filter_unknown_language: false` and handle downstream |

---

## Architecture

### Supported providers

## Supported Providers

### fasttext (Default)

**Supported Languages**: 176+ languages including all langdetect languages plus:
- Uzbek (uz), Kazakh (kk), Azerbaijani (az)
- Bengali (bn), Tamil (ta), Telugu (te)
- Swahili (sw), Amharic (am), Yoruba (yo)
- And 120+ more languages

**Pros**:
- ✅ 176+ language support (3x more than langdetect)
- ✅ High accuracy for both long and short texts
- ✅ Better handling of mixed-language content
- ✅ Memory-efficient singleton model with reference counting
- ✅ Thread-safe model management

**Cons**:
- ❌ Requires model download (~131MB) on first use
- ❌ Slightly slower than langdetect for very short texts
- ❌ Requires fasttext library installation

### langdetect

**Supported Languages**: 55+ languages including:
- English (en), Spanish (es), French (fr), German (de)
- Chinese (zh-cn, zh-tw), Japanese (ja), Korean (ko)
- Arabic (ar), Russian (ru), Portuguese (pt)
- Italian (it), Dutch (nl), Polish (pl)

**Pros**:
- ✅ No setup required
- ✅ Fast detection
- ✅ Good accuracy for common languages
- ✅ No external dependencies
- ✅ Probabilistic approach

**Cons**:
- ❌ Limited to 55 languages
- ❌ Less accurate for very short texts (<20 characters)
- ❌ May struggle with mixed-language content

## Architecture

### Hexagonal Architecture

The language detection operator follows hexagonal architecture (ports and adapters pattern):

```
┌─────────────────────────────────────────┐
│    LanguageDetect (Core Logic)          │
│                                         │
│  - Document processing                  │
│  - Error handling                       │
│  - PyArrow table management             │
│  - Filtering logic                      │
└──────────────┬──────────────────────────┘
               │
               │ Uses
               ▼
┌─────────────────────────────────────────┐
│   LanguageServicePort (Interface)       │
│   (ports/outbound/language_service.py)  │
│                                         │
│  - detect_language()                    │
│  - Returns: LanguageDetectionResult     │
└──────────────┬──────────────────────────┘
               │
               │ Implemented by
               ▼
┌─────────────────────────────────────────┐
│           Adapters                      │
│   (adapters/outbound/)                  │
│                                         │
│  - LangdetectAdapter                    │
│  - Custom adapters (extensible)         │
└──────────────┬──────────────────────────┘
               │
               │ Uses
               ▼
┌─────────────────────────────────────────┐
│      Language Detection Libraries       │
│                                         │
│  - langdetect                           │
│  - Future: spaCy, polyglot, etc.        │
└─────────────────────────────────────────┘
               ▲
               │
               │ Uses
┌──────────────┴──────────────────────────┐
│      Domain Models                      │
│      (domain/models.py)                 │
│                                         │
│  - LanguageDetectionResult (dataclass)  │
│    * language_code: str                 │
│    * confidence: float                  │
└─────────────────────────────────────────┘
```

### Directory Structure

```
language_detection/
├── domain/
│   ├── __init__.py
│   └── models.py                    # Domain models (LanguageDetectionResult)
├── ports/
│   └── outbound/
│       ├── __init__.py
│       └── language_service.py      # Port interface (LanguageServicePort)
├── adapters/
│   └── outbound/
│       ├── __init__.py
│       ├── langdetect_adapter.py    # Langdetect implementation
│       └── factories/
│           ├── __init__.py
│           └── language_adapter_factory.py  # Factory for creating adapters
└── README.md
```

### Current Adapters

#### LangdetectAdapter
- **Location**: `adapters/outbound/langdetect_adapter.py`
- **Provider**: langdetect library
- **Languages**: 55+
- **Use Case**: Fast detection for common languages, no setup required

#### FastTextAdapter
- **Location**: `adapters/outbound/fasttext_adapter.py`
- **Provider**: Facebook's FastText model
- **Languages**: 176+
- **Use Case**: High accuracy, support for rare languages, production workloads
- **Infrastructure**: Uses `FastTextModelManager` for singleton pattern and reference counting

### Adding a New Provider

The architecture allows easy addition of new language detection providers:

1. **Create Adapter** (in `adapters/outbound/`):

```python
from core.operators.quality.language_detection.domain.models import LanguageDetectionResult
from core.operators.quality.language_detection.ports.outbound.language_service import LanguageServicePort
from core.operators.quality.language_detection.adapters.outbound.factories.language_adapter_factory import (
    register_language_adapter,
)

@register_language_adapter
class MyLanguageAdapter(LanguageServicePort):
    ADAPTER_NAME = "mylang"
    ADAPTER_DISPLAY_NAME = "My Language Detector"

    def detect_language(self, text: str) -> LanguageDetectionResult:
        # Your implementation here
        language_code = "en"  # ISO 639-1 code
        confidence = 0.95     # 0.0 to 1.0
        return LanguageDetectionResult(language_code=language_code, confidence=confidence)
```

**Note**: `LanguageDetectionResult` is a dataclass defined in `domain/models.py` with two fields:
- `language_code`: ISO 639-1 language code (str)
- `confidence`: Confidence score between 0.0 and 1.0 (float)

2. **Register Adapter** (add to `adapters/outbound/__init__.py`):

```python
from .mylang_adapter import MyLanguageAdapter

__all__ = [
    "FastTextAdapter",
    "LangdetectAdapter",
    "MyLanguageAdapter",  # Add your adapter
]
```

3. **Use in Configuration**:

The adapter will be automatically available through the factory pattern:

```json
{
  "name": "detect_language",
  "type": "lang_detect",
  "config": {
    "language_provider": "mylang"
  }
}
```

### Adding a new provider

Implement `LanguageServicePort` and register the adapter:

```python
@register_language_adapter
class MyLanguageAdapter(LanguageServicePort):
    ADAPTER_NAME = "mylang"

    def detect_language(self, text: str) -> LanguageDetectionResult:
        return LanguageDetectionResult(language_code="en", confidence=0.95)
```

Then use `"language_provider": "mylang"` in the flow config.

### Typical pipeline position

```
Ingest → Extract → LanguageDetectionOperator → [SQLFilter / Chunker → Embeddings]
```

## Sample Flow

See [`sample_flows/advanced/quality_branching_merge_pipeline.json`](../../../sample_flows/advanced/quality_branching_merge_pipeline.json) for a complete example using language detection for quality-based routing.
