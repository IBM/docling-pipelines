# Readability Operator Configuration Reference

## Overview

The Readability operator analyzes text and produces a set of readability and text complexity metrics. These metrics help estimate how easy or difficult a document is to read and understand.

The operator supports **on-demand metric calculation** through the `readability_score_list` configuration parameter, meaning only the requested metrics are computed.

- **Operator Name**: `readability`
- **Category**: Quality
- **Short Name**: `readability`

## Implementation

This operator provides a custom implementation of standard readability formulas. The metrics and scoring logic are consistent with those defined in the [textstat](https://github.com/textstat/textstat/tree/main/textstat/backend/metrics) package, which is a widely used Python library for text readability analysis. This implementation makes use of [Pyphen](https://pyphen.org/) — a Python hyphenation library built on LibreOffice's hyphenation dictionaries — which provides more accurate and language-aware syllable detection.

This approach offers:
- Accurate syllable counting via Pyphen's language-specific hyphenation rules
- Reduced external dependencies
- Consistent, cacheable text statistics for efficient multi-metric computation

## Configuration Parameters

### 1. doc_column
- **Type**: String
- **Required**: No
- **Default**: `content`
- **Description**: The name of the column containing the document text to analyze

### 2. readability_score_list
- **Type**: List of strings
- **Required**: Yes
- **Default**: All 13 scores
- **Valid Values**: See Supported Metrics section
- **Description**: List of metric names to calculate. Only the requested metrics are computed

**Example:**
```json
"readability_score_list": [
  "flesch_reading_ease",
  "flesch_kincaid_grade",
  "gunning_fog"
]
```

## Supported Metrics

### 1. Flesch Reading Ease (`flesch_reading_ease`)

Measures how easy a text is to read.

**Formula:**
```
206.835 - 1.015(words/sentences) - 84.6(syllables/words)
```

**Interpretation:**

| Score | Difficulty |
|-------|------------|
| 90–100 | Very easy |
| 80–89 | Easy |
| 70–79 | Fairly easy |
| 60–69 | Standard |
| 50–59 | Fairly difficult |
| 30–49 | Difficult |
| 0–29 | Very difficult |

**Example:**
- Children's books: 90+
- News articles: 60–70
- Academic papers: 30–50

---

### 2. Flesch-Kincaid Grade (`flesch_kincaid_grade`)

Estimates U.S. school grade level required to understand the text.

**Formula:**
```
0.39(words/sentences) + 11.8(syllables/words) - 15.59
```

**Interpretation:**

| Score | Reading Level |
|-------|---------------|
| 5 | 5th grade |
| 8 | Middle school |
| 12 | High school |
| 16+ | College level |

---

### 3. Gunning Fog Index (`gunning_fog`)

Estimates years of formal education needed to understand the text.

**Formula:**
```
0.4((words/sentences) + 100(complex_words/words))
```

Where: `complex_words` = words with 3+ syllables

**Interpretation:**

| Score | Complexity |
|-------|------------|
| 6–8 | Easy |
| 9–12 | Standard |
| 13–16 | Difficult |
| 17+ | Very complex |

---

### 4. SMOG Index (`smog_index`)

Estimates education level needed to comprehend the text.

**Formula:**
```
1.0430 × √(complex_words × (30/sentences)) + 3.1291
```

**Interpretation:**

| Score | Reading Level |
|-------|---------------|
| 7–9 | Simple |
| 10–12 | Moderate |
| 13+ | Advanced |

Often used for healthcare and public communication readability analysis.

---

### 5. Coleman-Liau Index (`coleman_liau_index`)

Uses character counts instead of syllables.

**Formula:**
```
0.0588L - 0.296S - 15.8
```

Where:
- `L` = average letters per 100 words
- `S` = average sentences per 100 words

**Interpretation:**

Returns approximate U.S. grade level.
- Lower values → easier text
- Higher values → more complex text

---

### 6. Automated Readability Index (`automated_readability_index`)

Uses word and character lengths to estimate readability.

**Formula:**
```
4.71(characters/words) + 0.5(words/sentences) - 21.43
```

**Interpretation:**

| Score | Reader Level |
|-------|--------------|
| 1–6 | Elementary |
| 7–9 | Middle school |
| 10–12 | High school |
| 13+ | College |

---

### 7. Dale-Chall Readability Score (`dale_chall_readability_score`)

Measures readability using a predefined list of easy/familiar words.

**Interpretation:**

| Score | Difficulty |
|-------|------------|
| 4.9 or below | Easy |
| 5–6 | Average |
| 7–8 | Difficult |
| 9+ | Very difficult |

Useful for evaluating whether text uses overly complex vocabulary.

---

### 8. Difficult Words (`difficult_words`)

Counts words not present in the easy words list.

**Interpretation:**
- Lower count → simpler vocabulary
- Higher count → more advanced vocabulary

**Useful for:**
- Educational content
- Accessibility checks
- Simplification pipelines

---

### 9. Linsear Write Formula (`linsear_write_formula`)

Originally designed for technical manuals.

**Interpretation:**

| Score | Complexity |
|-------|------------|
| < 8 | Easy |
| 8–12 | Moderate |
| > 12 | Difficult |

Works well for technical or engineering-oriented text.

---

### 10. Text Standard (`text_standard`)

Provides an aggregated readability estimate by combining multiple readability metrics (Flesch-Kincaid, Gunning Fog, SMOG, Coleman-Liau, and ARI).

**Interpretation:**

Returns a numeric grade-level estimate. Useful as a high-level summary metric.

---

### 11. Spache Readability (`spache_readability`)

Designed specifically for children's or primary-school-level text. Uses the easy words list to identify unfamiliar vocabulary.

**Interpretation:**

Lower scores indicate easier text for younger readers.

**Typically used for:**
- Educational content
- Child-focused material
- Beginner reading analysis

---

### 12. McAlpine EFLAW (`mcalpine_eflaw`)

Designed for evaluating readability for non-native English readers.

**Interpretation:**
- Lower values → easier for ESL/EFL readers
- Higher values → harder for second-language readers

**Useful for:**
- International documentation
- Beginner English material
- Simplified communication checks

---

### 13. Reading Time (`reading_time`)

Estimates the time (in minutes) required to read the document, based on an average reading speed of ~200 words per minute.

**Example:**
- 2.5 → approximately 2.5 minutes

**Useful for:**
- UX/content design
- Article previews
- Chunking and pacing

---

## Output Features

All selected readability scores are added as new columns to the output table. Each score is filterable and can be used in downstream operators such as `branching` or `sql_filter`.

**Column names match the metric keys exactly:**
- `flesch_reading_ease`
- `flesch_kincaid_grade`
- `gunning_fog`
- `smog_index`
- `coleman_liau_index`
- `automated_readability_index`
- `dale_chall_readability_score`
- `difficult_words`
- `linsear_write_formula`
- `text_standard`
- `spache_readability`
- `mcalpine_eflaw`
- `reading_time`

## General Guidance

### Easier Text Typically Has:
- Shorter sentences
- Fewer syllables per word
- Fewer complex words
- Lower grade-level scores

### Harder Text Typically Has:
- Long sentences
- Technical vocabulary
- Multi-syllable words
- Higher grade-level scores

### Score Selection Guidelines

| Use Case | Recommended Metrics |
|----------|---------------------|
| General audience | `flesch_reading_ease`, `flesch_kincaid_grade`, `text_standard` |
| Technical content | `gunning_fog`, `linsear_write_formula`, `difficult_words` |
| Educational content | `flesch_kincaid_grade`, `spache_readability`, `dale_chall_readability_score` |
| ESL/EFL content | `mcalpine_eflaw`, `flesch_reading_ease`, `difficult_words` |
| Quick assessment | `flesch_reading_ease`, `text_standard`, `reading_time` |

## Configuration Examples

### Example 1: Basic Readability Analysis
```json
{
  "name": "document_readability",
  "type": "readability",
  "config": {
    "doc_column": "content",
    "readability_score_list": [
      "flesch_reading_ease",
      "flesch_kincaid_grade",
      "gunning_fog"
    ]
  }
}
```

### Example 2: Comprehensive Analysis (All Scores)
```json
{
  "name": "document_readability",
  "type": "readability",
  "config": {
    "doc_column": "content",
    "readability_score_list": [
      "flesch_reading_ease",
      "flesch_kincaid_grade",
      "gunning_fog",
      "smog_index",
      "coleman_liau_index",
      "automated_readability_index",
      "dale_chall_readability_score",
      "difficult_words",
      "linsear_write_formula",
      "text_standard",
      "spache_readability",
      "mcalpine_eflaw",
      "reading_time"
    ]
  }
}
```

### Example 3: Grade Level Focus
```json
{
  "name": "document_readability",
  "type": "readability",
  "config": {
    "doc_column": "content",
    "readability_score_list": [
      "flesch_kincaid_grade",
      "gunning_fog",
      "text_standard"
    ]
  }
}
```

## Complete Flow Example

```json
{
  "flow_name": "Readability Analysis Pipeline",
  "description": "Ingest, extract, analyze readability, and filter documents",
  "flow": [
    {
      "name": "ingest_documents",
      "type": "ingest_local",
      "config": {
        "paths": "sample_documents"
      }
    },
    {
      "name": "extract_documents",
      "type": "extract_operator",
      "depends_on": ["ingest_documents"],
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
      "name": "compute_readability",
      "type": "readability",
      "depends_on": ["extract_documents"],
      "config": {
        "doc_column": "content",
        "readability_score_list": [
          "flesch_reading_ease",
          "flesch_kincaid_grade",
          "gunning_fog",
          "difficult_words",
          "reading_time"
        ]
      }
    },
    {
      "name": "filter_readable_documents",
      "type": "sql_filter",
      "depends_on": ["compute_readability"],
      "config": {
        "criteria_list": [
          "flesch_reading_ease >= 60",
          "flesch_kincaid_grade <= 10"
        ]
      }
    }
  ]
}
```

## Technical Details

### Word List

The operator uses a single consolidated easy words list (`easy_words.txt`) containing 2,940 familiar English words. This list combines vocabulary from both Dale-Chall and Spache readability research, providing comprehensive coverage for:

- **Dale-Chall Readability Score**: Identifies difficult words for general audiences
- **Difficult Words metric**: Counts unfamiliar vocabulary
- **Spache Readability**: Assesses text complexity for children (grades 1-4)

The consolidated list ensures consistent word familiarity assessment across all metrics.

### Syllable Counting with Pyphen

**What is a Syllable?**

A syllable is a unit of pronunciation containing a single vowel sound:
- "cat" = 1 syllable
- "water" = 2 syllables (wa-ter)
- "beautiful" = 3 syllables (beau-ti-ful)

**Why Syllable Counting Matters for Readability:**

Syllable count is a key indicator of word complexity:
- **Shorter words** (fewer syllables) are generally easier to read
- **Longer words** (more syllables) require more cognitive effort
- Many readability formulas use syllable-to-word ratios to estimate text complexity

**Implementation:**

Syllable counting is performed using [Pyphen](https://pyphen.org/), a Python library for hyphenation based on LibreOffice's hyphenation dictionaries.

```python
from pyphen import Pyphen
self.dic = Pyphen(lang="en_US")

def count_syllables(self, word: str) -> int:
    hyphenated = self.dic.inserted(word)
    syllable_count = hyphenated.count("-") + 1
    return max(1, syllable_count)
```

**Examples:**
- "computer" → "com-put-er" → 3 syllables
- "documentation" → "doc-u-men-ta-tion" → 5 syllables
- "text" → "text" → 1 syllable

**Used by:** Flesch Reading Ease, Flesch-Kincaid Grade, Gunning Fog Index, SMOG Index, Linsear Write Formula

**Accuracy Notes:**

While Pyphen provides accurate syllable counting for most English words, some edge cases may differ from phonetic reality. However, the statistical nature of readability formulas means minor variations do not significantly impact overall readability trends and scores.

## References

### Readability Overview
- [Readability (Wikipedia)](https://en.wikipedia.org/wiki/Readability) — General overview of readability formulas and their interpretation
- [Flesch-Kincaid Readability Tests](https://en.wikipedia.org/wiki/Flesch%E2%80%93Kincaid_readability_tests) — Explains commonly used readability formulas and score interpretation

### Specific Formulas
- [Dale-Chall Readability Formula](https://en.wikipedia.org/wiki/Dale%E2%80%93Chall_readability_formula) — Details on difficult-word based readability scoring
- [SMOG Index](https://en.wikipedia.org/wiki/SMOG) — Information about SMOG readability grading and healthcare usage
- [Spache Readability Formula](https://en.wikipedia.org/wiki/Spache_readability_formula) — Readability metric designed for children's text
