# Readability Operator Configuration Reference

## Overview
The Readability operator computes text readability scores for document content using multiple established readability formulas. It analyzes text complexity, sentence structure, and vocabulary to provide 13 different readability metrics.

- **Operator Name**: `readability`
- **Category**: Quality
- **Short Name**: `readability`

## Configuration Parameters

### 1. readability_score_list
- **Type**: List of strings
- **Required**: Yes
- **Default**: All 13 scores (see below)
- **Valid Values**: See Available Readability Scores section
- **Description**: Select which readability scores to compute for your documents

**Example:**
```json
"readability_score_list": [
  "flesch_ease",
  "flesch_kincaid",
  "gunning_fog"
]
```

## Available Readability Scores

### 1. flesch_ease
- **Name**: Flesch Reading Ease
- **Type**: Float
- **Range**: 0-100 (higher = easier to read)
- **Description**: Rates text on a 0 to 100 scale where higher scores mean easier reading
- **Interpretation**:
  - 90-100: Very Easy (5th grade)
  - 80-89: Easy (6th grade)
  - 70-79: Fairly Easy (7th grade)
  - 60-69: Standard (8th-9th grade)
  - 50-59: Fairly Difficult (10th-12th grade)
  - 30-49: Difficult (College)
  - 0-29: Very Difficult (College graduate)

### 2. flesch_kincaid
- **Name**: Flesch Kincaid Grade
- **Type**: Float
- **Description**: Estimates the U.S. school grade level needed to understand the text
- **Interpretation**: Score of 8.0 means 8th grade reading level

### 3. gunning_fog
- **Name**: Gunning Fog
- **Type**: Float
- **Description**: Estimates the grade level needed based on long sentences and difficult words
- **Interpretation**: Score of 12.0 means 12th grade reading level

### 4. smog_index
- **Name**: SMOG Index
- **Type**: Float
- **Description**: Shows the grade level needed, based mainly on how many hard words the text has
- **Interpretation**: Particularly accurate for texts aimed at grades 4-12

### 5. coleman_liau_index
- **Name**: Coleman Liau Index
- **Type**: Float
- **Description**: Estimates reading grade level using letter counts instead of syllables
- **Interpretation**: Useful for texts where syllable counting is difficult

### 6. automated_readability_index
- **Name**: Automated Readability Index (ARI)
- **Type**: Float
- **Description**: Gives the school grade level needed using characters per word and words per sentence
- **Interpretation**: Designed for real-time monitoring of readability

### 7. dale_chall_readability_score
- **Name**: Dale Chall Readability Score
- **Type**: Float
- **Description**: Estimates the grade level by checking how many uncommon words are used
- **Interpretation**: Uses a list of 3,000 familiar words; higher scores indicate more difficult text

### 8. difficult_words
- **Name**: Difficult Words Count
- **Type**: Integer
- **Description**: Returns the count of words that are not commonly used, which make the text harder for readers
- **Interpretation**: Higher count = more difficult text

### 9. linsear_write_formula
- **Name**: Linsear Write Formula
- **Type**: Float
- **Description**: Computes grade level based on easy vs. hard words and sentence length
- **Interpretation**: Designed specifically for technical writing

### 10. text_standard
- **Name**: Text Standard
- **Type**: Float
- **Description**: Provides an overall grade-level estimate by combining multiple readability formulas
- **Interpretation**: Consensus grade level from multiple metrics

### 11. spache_readability
- **Name**: Spache Readability
- **Type**: Float
- **Description**: Estimates reading grade level for texts aimed at young children up to 4th grade
- **Interpretation**: Best for primary school texts (grades 1-4)

### 12. mcalpine_eflaw
- **Name**: McAlpine EFLAW
- **Type**: Float
- **Description**: Rates readability for learners of English, focusing on short 'miniwords' and sentence length
- **Interpretation**: Designed for ESL/EFL contexts

### 13. reading_time
- **Name**: Reading Time
- **Type**: Float
- **Description**: The reading time of the given text in seconds
- **Calculation**: Assumes 14.69ms per character (approximately 200 words per minute)

## Output Features

All selected readability scores are added as columns to the output table. Each score is filterable and can be used in downstream operators.

**Column Names**: Each score is added with suffix `_textstat`:
- `flesch_ease_textstat`
- `flesch_kincaid_textstat`
- `gunning_fog_textstat`
- etc.

## Configuration Examples

### Example 1: Basic Readability Analysis
```json
{
  "id": "readability-node-1",
  "operator": "readability",
  "config": {
    "readability_score_list": [
      "flesch_ease",
      "flesch_kincaid",
      "gunning_fog"
    ]
  }
}
```

### Example 2: Comprehensive Analysis (All Scores)
```json
{
  "id": "readability-node-2",
  "operator": "readability",
  "config": {
    "readability_score_list": [
      "flesch_ease",
      "flesch_kincaid",
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
  "id": "readability-node-3",
  "operator": "readability",
  "config": {
    "readability_score_list": [
      "flesch_kincaid",
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
      "type": "ingest_local_folder",
      "config": {
        "input_folder": "sample_documents"
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
      "name": "compute_readability",
      "type": "readability",
      "depends_on": ["extract_documents"],
      "config": {
        "readability_score_list": [
          "flesch_ease",
          "flesch_kincaid",
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
          "flesch_ease_textstat >= 60",
          "flesch_kincaid_textstat <= 10"
        ]
      }
    }
  ]
}
```

## Score Selection Guidelines

### For General Audience
- `flesch_ease` - Overall readability
- `flesch_kincaid` - Grade level
- `text_standard` - Consensus grade level

### For Technical Content
- `gunning_fog` - Complex sentence detection
- `linsear_write_formula` - Technical writing assessment
- `difficult_words` - Vocabulary complexity

### For Educational Content
- `flesch_kincaid` - Grade level alignment
- `spache_readability` - Primary grades (1-4)
- `dale_chall_readability_score` - Vocabulary difficulty

### For ESL/EFL Content
- `mcalpine_eflaw` - ESL-specific metric
- `flesch_ease` - General readability
- `difficult_words` - Vocabulary challenge

### For Quick Assessment
- `flesch_ease` - Single comprehensive score
- `text_standard` - Consensus grade level
- `reading_time` - Time estimate
