# Document Quality Operator Configuration

## Overview

The Document Quality operator analyzes text documents and computes various quality metrics including word statistics, formatting patterns, and content quality indicators. It uses the Data Prep Kit (DPK) document quality transform to assess document characteristics.

**Operator Name:** `doc_quality`  
**Category:** Quality  
**SDK-Based:** Yes (uses `dpk_doc_quality`)

## Configuration Parameters

The operator adds 11 document quality metrics to the PyArrow table:

### 1. `docq_total_words` (Integer)
**Description:** Total number of words in the document  
**Available for Filter:** Yes  
**Type:** Integer

**Example Values:**
- `150` - Short document
- `1500` - Medium document
- `5000` - Long document

### 2. `docq_mean_word_len` (Float)
**Description:** Mean length of words in characters  
**Available for Filter:** Yes  
**Type:** Float

**Example Values:**
- `4.2` - Simple vocabulary
- `5.8` - Average complexity
- `7.5` - Complex vocabulary

### 3. `docq_symbol_to_word_ratio` (Float)
**Description:** Ratio of symbols (emojis, special characters) to words  
**Available for Filter:** Yes  
**Type:** Float  
**Range:** 0.0 to 1.0+

**Example Values:**
- `0.01` - Minimal symbols
- `0.05` - Normal usage
- `0.20` - Heavy symbol usage

### 4. `docq_sentence_count` (Integer)
**Description:** Number of sentences in the document  
**Available for Filter:** Yes  
**Type:** Integer

**Example Values:**
- `5` - Few sentences
- `50` - Moderate length
- `200` - Long document

### 5. `docq_lorem_ipsum_ratio` (Float)
**Description:** Ratio of lorem ipsum placeholder text occurrences  
**Available for Filter:** Yes  
**Type:** Float  
**Range:** 0.0 to 1.0

**Example Values:**
- `0.0` - No placeholder text
- `0.5` - Half placeholder content
- `1.0` - All placeholder text

### 6. `docq_contain_bad_word` (Boolean)
**Description:** Whether text contains profanity or inappropriate words  
**Available for Filter:** Yes  
**Type:** Boolean

**Example Values:**
- `false` - Clean content
- `true` - Contains profanity

### 7. `docq_bullet_point_ratio` (Float)
**Description:** Ratio of lines starting with bullet points  
**Available for Filter:** Yes  
**Type:** Float  
**Range:** 0.0 to 1.0

**Example Values:**
- `0.0` - No bullet points
- `0.3` - Some lists
- `0.8` - Heavily list-based

### 8. `docq_curly_bracket_ratio` (Float)
**Description:** Ratio of curly brackets `{` or `}` to text length  
**Available for Filter:** Yes  
**Type:** Float  
**Range:** 0.0 to 1.0

**Example Values:**
- `0.0` - No code/JSON
- `0.05` - Some structured content
- `0.20` - Heavy code/JSON content

### 9. `docq_ellipsis_line_ratio` (Float)
**Description:** Ratio of lines ending with ellipsis `...`  
**Available for Filter:** Yes  
**Type:** Float  
**Range:** 0.0 to 1.0

**Example Values:**
- `0.0` - No ellipsis
- `0.1` - Occasional use
- `0.5` - Frequent incomplete sentences

### 10. `docq_alphabet_word_ratio` (Float)
**Description:** Ratio of words containing at least one alphabetic character  
**Available for Filter:** Yes  
**Type:** Float  
**Range:** 0.0 to 1.0

**Example Values:**
- `0.95` - Mostly text
- `0.70` - Mixed text and numbers
- `0.30` - Mostly numeric/symbols

### 11. `docq_contain_common_en_words` (Float)
**Description:** Whether text contains common English words (the, and, to, that, of, with, be, have)  
**Available for Filter:** Yes  
**Type:** Float

**Example Values:**
- `1.0` - Contains common words
- `0.0` - No common words (possibly non-English or gibberish)

## Configuration Examples

### Example 1: Basic Document Quality Analysis
```json
{
  "id": "quality-node-1",
  "operator": "doc_quality",
  "config": {
    "text_lang": "en"
  }
}
```

### Example 3: Pipeline with Quality Filtering
```json
{
  "flow_name": "Document Quality Pipeline",
  "description": "Analyze document quality and filter based on metrics",
  "flow": [
    {
      "name": "quality_analysis",
      "type": "doc_quality",
      "config": {}
    },
    {
      "name": "quality_filter",
      "type": "sql_filter",
      "depends_on": ["quality_analysis"],
      "config": {
        "criteria_list": [
          "docq_total_words >= 50",
          "docq_contain_bad_word = false",
          "docq_lorem_ipsum_ratio < 0.1"
        ]
      }
    }
  ]
}
```

## Downstream Usage Examples

After computing quality metrics, use them in SQL filters:

### Filter High-Quality Documents
```json
{
  "operator": "sql_filter",
  "config": {
    "criteria_list": [
      "docq_total_words >= 100",
      "docq_mean_word_len >= 4.0",
      "docq_contain_bad_word = false",
      "docq_alphabet_word_ratio >= 0.90"
    ]
  }
}
```

### Filter Out Placeholder Content
```json
{
  "operator": "sql_filter",
  "config": {
    "criteria_list": [
      "docq_lorem_ipsum_ratio < 0.05",
      "docq_contain_common_en_words > 0.5"
    ]
  }
}
```

### Filter Code/Technical Documents
```json
{
  "operator": "sql_filter",
  "config": {
    "criteria_list": [
      "docq_curly_bracket_ratio >= 0.10",
      "docq_bullet_point_ratio >= 0.20"
    ]
  }
}
```

## Best Practices

1. **Language Setting**: Set `text_lang` correctly for accurate language-specific checks
2. **Quality Thresholds**: Adjust filtering thresholds based on your document corpus characteristics
3. **Profanity Detection**: The bad word check is language-specific; default is English
4. **Placeholder Detection**: Use `docq_lorem_ipsum_ratio` to filter out template/draft documents
