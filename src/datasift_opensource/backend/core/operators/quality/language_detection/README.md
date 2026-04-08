# Language Detection Operator

## Overview

The Language Detection Operator identifies the language of document content and provides confidence scores. It supports multiple language detection providers through a pluggable adapter system and follows hexagonal architecture principles for extensibility.

## Quick Start

### Basic Configuration

```json
{
  "operator_type": "datasift_opensource.backend.core.operators.quality.lang_id.LanguageDetect",
  "operator_params": {
    "doc_column": "content",
    "filter_unknown_language": false
  }
}
```

### Complete Pipeline Example

```json
{
  "nodes": [
    {
      "id": "ingest",
      "operator_type": "datasift_opensource.backend.core.operators.ingest.ingest_local_folder.IngestLocalFolder",
      "operator_params": {
        "folder_path": "data/documents"
      }
    },
    {
      "id": "extract",
      "operator_type": "datasift_opensource.backend.core.operators.extract.extract_docling.ExtractDocling",
      "operator_params": {}
    },
    {
      "id": "language",
      "operator_type": "datasift_opensource.backend.core.operators.quality.lang_id.LanguageDetect",
      "operator_params": {
        "doc_column": "content",
        "filter_unknown_language": false
      }
    },
    {
      "id": "chunk",
      "operator_type": "datasift_opensource.backend.core.operators.functional.chunker.DoclingChunker",
      "operator_params": {
        "chunk_size": 512
      }
    }
  ],
  "edges": [
    { "from": "ingest", "to": "extract" },
    { "from": "extract", "to": "language" },
    { "from": "language", "to": "chunk" }
  ]
}
```

## Features

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

2. **Register Adapter** (import in operator):

```python
# In lang_id.py
import core.operators.quality.language_detection.adapters.outbound.mylang_adapter  # noqa: F401
```

3. **Use in Factory**:

The adapter will be automatically available through the factory pattern.

## Configuration Reference

### Parameters

| Parameter                 | Type    | Required | Description                                       |
| ------------------------- | ------- | -------- | ------------------------------------------------- |
| `doc_column`              | string  | No       | Column containing text (default: `content`)       |
| `filter_unknown_language` | boolean | No       | Filter out unknown languages (default: false)     |
| `language_provider`       | string  | No       | Language detection provider (default: `langdetect`) |

### Output Columns

| Column       | Type   | Description                                |
| ------------ | ------ | ------------------------------------------ |
| `lang_name`  | string | ISO 639-1 language code (e.g., 'en', 'fr')|
| `lang_score` | float  | Confidence score (0.0 to 1.0)              |

## Performance

### Benchmark Results

Based on 5 sample documents:

| Metric     | Value      |
| ---------- | ---------- |
| Time       | 0.05s      |
| Throughput | 100 docs/s |
| Accuracy   | Good       |

### Performance Tips

1. **Text Length**: Longer texts (>50 characters) produce more accurate results
2. **Batch Processing**: Process documents in batches for better throughput
3. **Filtering**: Use `filter_unknown_language: true` to remove low-confidence detections
4. **Pre-filtering**: Filter out non-text content before language detection

## Error Handling

### Common Errors

#### Empty Text

```
ValueError: Text cannot be empty
```

**Solution**: Ensure documents have content before language detection

#### No Features in Text

```
ValueError: Language detection failed: No features in text.
```

**Solution**: Text contains only numbers or special characters. Consider filtering or marking as UNKNOWN.

### Filtering Behavior

When `filter_unknown_language: true`:
- Documents with detection errors are removed from the flow
- Failed documents are recorded in metadata
- Status set to `CompletedWithErrors`

When `filter_unknown_language: false` (default):
- Documents with detection errors are marked as `UNKNOWN`
- Confidence score set to `0.0`
- Status set to `CompletedWithWarnings`
- All documents remain in the flow

## Testing

### Unit Tests

```bash
cd src/datasift_opensource/backend
source .venv/bin/activate
export PYTHONPATH="$(pwd):${PYTHONPATH}"

# Run language detection tests
uv run pytest ../../../tests/unit/operators/language/ -v
```

### Example Script

```bash
# Run the language detection example
python examples/language_detection_example.py
```

### Flow Testing

```bash
datasift-orchestrator --flow-file tests/flow_local.json
```

## Troubleshooting

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Verify Detection

```python
from core.operators.quality.lang_id import LanguageDetect
import pyarrow as pa

# Create operator
operator = LanguageDetect({"doc_column": "content"})

# Test with sample data
content = pa.array(["Hello, world!", "Bonjour, monde!", "¡Hola, mundo!"])
doc_id = pa.array(["1", "2", "3"])
name = pa.array(["doc1", "doc2", "doc3"])

table = pa.Table.from_arrays(
    [doc_id, content, name],
    names=["id", "content", "name"]
)

# Run detection
result_tables, metadata = operator.transform(table)
print(result_tables[0])
```

Expected output:
```
lang_name: ["en", "fr", "es"]
lang_score: [0.9999, 0.9999, 0.9999]
```

## Language Code Reference

### Common ISO 639-1 Codes

| Code | Language   | Code | Language   |
| ---- | ---------- | ---- | ---------- |
| en   | English    | es   | Spanish    |
| fr   | French     | de   | German     |
| it   | Italian    | pt   | Portuguese |
| ru   | Russian    | zh   | Chinese    |
| ja   | Japanese   | ko   | Korean     |
| ar   | Arabic     | hi   | Hindi      |
| nl   | Dutch      | pl   | Polish     |
| tr   | Turkish    | sv   | Swedish    |

For complete list, see: https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes

## Additional Resources

- [langdetect Documentation](https://github.com/Mimino666/langdetect)
- [ISO 639-1 Language Codes](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes)
- [Hexagonal Architecture Pattern](https://alistair.cockburn.us/hexagonal-architecture/)

## Support

For issues or questions:

1. Check this documentation
2. Review the langdetect library documentation
3. Open an issue in the datasift-opensource repository
