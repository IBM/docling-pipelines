# Ingest Local Folder Operator - Configuration Reference

## Overview

The Ingest Local Operator discovers and loads file metadata from a local filesystem file or directory. This operator performs metadata-only ingestion - it does NOT extract text content. Text extraction is handled by downstream operators like ExtractOperator.

- **Operator Name:** `ingest_local`
- **Category**: Ingest
- **Short Name**: `ingest_local`

## Configuration Parameters

### 1. `paths` (String)
**Type:** String  
**Required:** Yes  
**Description:** Path to the file or folder containing documents to ingest.  

**Examples:**
```json
"paths": "/path/to/documents"
```

```json
"paths": "./data/test1.txt"
```

### 2. `max_files` (Integer)
**Type:** Integer  
**Required:** No  
**Default:** `100`  
**Description:** Maximum number of files to ingest. Processing stops after reaching this limit.  

**Examples:**
```json
"max_files": 100
```

### 3. `max_file_size` (Integer)
**Type:** Integer  
**Required:** No  
**Default:** `100` (MB)  
**Description:** Maximum file size in megabytes. Files larger than this will be skipped.  

**Examples:**
```json
"max_file_size": 50
```

### 4. `include_filter` (List)
**Type:** List (comma-separated string)  
**Required:** No  
**Default:** `"pdf,docx,pptx,txt,md"`  
**Description:** File extensions to include. Only files with these extensions will be processed.  

**Examples:**
```json
"include_filter": "pdf,docx,txt"
```

```json
"include_filter": "md,rst,adoc"
```

### 5. `exclude_filter` (List)
**Type:** List (comma-separated string)  
**Required:** No  
**Description:** File extensions to exclude. Files with these extensions will be skipped even if they match include_filter.  

**Examples:**
```json
"exclude_filter": "tmp,bak,log"
```

### 6. `force_ingest` (Boolean)
**Type:** Boolean  
**Required:** No  
**Default:** `false`  
**Description:** Force re-ingestion of previously processed documents. When false, documents are skipped if they haven't been modified since last ingestion.  

**Examples:**
```json
"force_ingest": true
```

### 7. `retain_deleted_docs` (Boolean)
**Type:** Boolean  
**Required:** No  
**Default:** `false`  
**Description:** Whether to retain documents in the system that have been deleted from the source folder.  

**Examples:**
```json
"retain_deleted_docs": true
```

## Output Features

### `id` (String)
**Type:** String  
**Description:** Document identifier  
**Available for Filter:** Yes  
**Available for Vector DB:** Yes  

### `name` (String)
**Type:** String  
**Description:** The absolute path to the document file  
**Available for Filter:** Yes  
**Available for Vector DB:** No  

### `path` (String)
**Type:** String  
**Description:** The absolute path to the document file (same as name)  
**Available for Filter:** Yes  
**Available for Vector DB:** No  

### `document_format` (String)
**Type:** String  
**Description:** File format/extension of the document (e.g., `.pdf`, `.xlsx`)  
**Available for Filter:** Yes  
**Available for Vector DB:** No  

### `size` (Integer)
**Type:** Integer  
**Description:** File size in bytes  
**Available for Filter:** Yes  
**Available for Vector DB:** No  

### `created_time` (Integer)
**Type:** Integer  
**Description:** File creation timestamp (Unix epoch time)  
**Available for Filter:** Yes  
**Available for Vector DB:** No  

### `modified_time` (Integer)
**Type:** Integer  
**Description:** File modification timestamp (Unix epoch time)  
**Available for Filter:** Yes  
**Available for Vector DB:** No  

## Configuration Examples

### Example 1: Basic Local Ingestion
```json
{
  "operator": "ingest_local",
  "config": {
    "paths": "/data/documents",
    "max_files": 500,
    "include_filter": "pdf,docx"
  }
}
```

### Example 2: Filtered Ingestion with Size Limit
```json
{
  "operator": "ingest_local",
  "config": {
    "paths": "./documents",
    "max_files": 1000,
    "max_file_size": 50,
    "include_filter": "pdf,txt,md",
    "exclude_filter": "tmp,bak"
  }
}
```

### Example 3: Force Re-ingestion
```json
{
  "operator": "ingest_local",
  "config": {
    "paths": "/data/updated_docs",
    "force_ingest": true,
    "retain_deleted_docs": true
  }

```

## Best Practices

1. **Start Small**: Begin with a small `max_files` value to test your pipeline
2. **Use Filters**: Leverage `include_filter` and `exclude_filter` to process only relevant files
3. **Size Limits**: Set appropriate `max_file_size` to avoid memory issues with large files
4. **Incremental Updates**: Leave `force_ingest` as false for efficient incremental processing
5. **Path Validation**: Ensure `paths` exists and is accessible before running

## Validation Rules

- `paths` must exist (can be a file or directory)
- `max_files` must be greater than 0
- `max_file_size` must be greater than 0
- File extensions in filters should not include the dot (use "pdf" not ".pdf")

## Complete Flow Example

- [Sample Flow](../../../sample_flows/complete_pipeline_flow.json)
