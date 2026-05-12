# OpenSearch Schema Templates Guide

## Overview

Schema templates provide a flexible, reusable way to define OpenSearch index configurations for DataSift pipelines. Instead of manually configuring index schemas for each flow, you can use pre-built templates or create custom ones that automatically adapt to your pipeline's requirements.

## Table of Contents

1. [What are Schema Templates?](#what-are-schema-templates)
2. [Benefits](#benefits)
3. [Available Templates](#available-templates)
4. [Using Schema Templates](#using-schema-templates)
5. [Placeholder Reference](#placeholder-reference)
6. [Creating Custom Templates](#creating-custom-templates)
7. [Validation Rules](#validation-rules)
8. [Metadata Normalization](#metadata-normalization)
9. [Best Practices](#best-practices)
10. [Examples](#examples)
11. [Troubleshooting](#troubleshooting)

## What are Schema Templates?

Schema templates are JSON files that define OpenSearch index configurations with placeholder values that are replaced at runtime. They provide:

- **Reusable index structures** across different pipelines
- **Consistent field mappings** and analyzers
- **Dynamic configuration** through placeholder replacement
- **Validation** to catch errors before index creation

Templates are stored in `src/datasift/core/operators/vectordb/schemas/` and referenced by path in the VectorDBOperator configuration.

## Benefits

### Consistency

- Same index structure across development, testing, and production
- Standardized field types and analyzers
- Reduced configuration errors

### Maintainability

- Update schema in one place, apply to all flows
- Version control for schema changes
- Clear separation between schema definition and runtime configuration

### Flexibility

- Placeholders adapt to different vector dimensions, engines, and algorithms
- Custom analyzers for specific use cases
- Easy to create domain-specific templates

### Validation

- Schema structure validated before index creation
- Parameter ranges checked automatically
- Clear error messages for configuration issues

## Available Templates

### 1. default_schema.v1.json

**Purpose**: General-purpose schema for document storage with standard field types.

**Use Cases**:

- Basic document indexing
- General text search
- Standard vector similarity search

**Features**:

- Standard text fields with keyword sub-fields
- Numeric types (int64, float)
- Boolean fields
- Object and nested types
- KNN vector configuration

**Location**: `src/datasift/core/operators/vectordb/schemas/default_schema.v1.json`

### 2. document_chunks_schema.v1.json

**Purpose**: Optimized schema for document chunking workflows with custom text analysis.

**Use Cases**:

- Semantic search on document chunks
- RAG (Retrieval-Augmented Generation) pipelines
- Content-heavy document processing

**Features**:

- Custom content analyzer with stemming and stop words
- Optimized for text-heavy content
- Additional field types (date, keyword)
- Enhanced text analysis for better search relevance

**Location**: `src/datasift/core/operators/vectordb/schemas/document_chunks_schema.v1.json`

## Using Schema Templates

### Basic Usage

Add `schema_template_path` to your VectorDBOperator's `provider_config`:

```json
{
  "operator_type": "datasift.core.operators.vectordb.vectordb_operator.VectorDBOperator",
  "operator_params": {
    "provider": "opensearch",
    "index_name": "my_documents",
    "provider_config": {
      "schema_template_path": "schemas/default_schema.v1.json",
      "host": "localhost",
      "port": 9200,
      "engine": "faiss",
      "algorithm": "hnsw",
      "vector_dimension": 384
    }
  }
}
```

### With Document Chunks Template

```json
{
  "provider_config": {
    "schema_template_path": "schemas/document_chunks_schema.v1.json",
    "host": "localhost",
    "port": 9200,
    "engine": "faiss",
    "algorithm": "hnsw",
    "vector_dimension": 768
  }
}
```

### Fallback Behavior

If `schema_template_path` is not specified or the template cannot be loaded:

- System falls back to dynamic schema generation
- Warning logged but execution continues
- Schema generated from `available_features` configuration

## Placeholder Reference

Templates support the following placeholders that are replaced at runtime:

| Placeholder             | Description                | Example Values                         | Required |
| ----------------------- | -------------------------- | -------------------------------------- | -------- |
| `__VECTOR_DIMENSION__`  | Vector embedding dimension | `384`, `768`, `1536`                   | Yes      |
| `__ENGINE__`            | KNN engine name            | `faiss`, `lucene`, `nmslib`, `jvector` | Yes      |
| `__ALGORITHM__`         | KNN algorithm              | `hnsw`, `ivf`                          | Yes      |
| `__SPACE_TYPE__`        | Similarity metric          | `l2`, `cosine`, `inner_product`        | Yes      |
| `__ENGINE_PARAMETERS__` | Engine-specific parameters | `{"ef_construction": 128, "m": 24}`    | Yes      |

### Placeholder Usage in Templates

```json
{
  "field_types": {
    "vector": {
      "type": "knn_vector",
      "dimension": "__VECTOR_DIMENSION__",
      "method": {
        "name": "__ALGORITHM__",
        "space_type": "__SPACE_TYPE__",
        "engine": "__ENGINE__",
        "parameters": "__ENGINE_PARAMETERS__"
      }
    }
  }
}
```

### Runtime Replacement

When the template is loaded, placeholders are replaced with actual values from your configuration:

```json
{
  "field_types": {
    "vector": {
      "type": "knn_vector",
      "dimension": 768,
      "method": {
        "name": "hnsw",
        "space_type": "l2",
        "engine": "faiss",
        "parameters": {
          "ef_construction": 128,
          "m": 24
        }
      }
    }
  }
}
```

## Creating Custom Templates

### Template Structure

A schema template must include:

1. **schema_name**: Unique identifier for the template
2. **schema_version**: Version number (integer)
3. **settings**: OpenSearch index settings
4. **field_types**: Field type definitions

### Minimal Template Example

```json
{
  "schema_name": "my_custom_schema",
  "schema_version": 1,
  "settings": {
    "index": {
      "knn": true,
      "number_of_shards": 2,
      "number_of_replicas": 1
    }
  },
  "field_types": {
    "vector": {
      "type": "knn_vector",
      "dimension": "__VECTOR_DIMENSION__",
      "method": {
        "name": "__ALGORITHM__",
        "space_type": "__SPACE_TYPE__",
        "engine": "__ENGINE__",
        "parameters": "__ENGINE_PARAMETERS__"
      }
    },
    "string": {
      "type": "text",
      "fields": {
        "keyword": {
          "type": "keyword",
          "ignore_above": 256
        }
      }
    }
  }
}
```

### Custom Analyzer Example

```json
{
  "schema_name": "custom_analyzer_schema",
  "schema_version": 1,
  "settings": {
    "index": {
      "knn": true,
      "number_of_shards": 3,
      "number_of_replicas": 1
    },
    "analysis": {
      "analyzer": {
        "my_custom_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "stop", "snowball", "asciifolding"]
        }
      }
    }
  },
  "field_types": {
    "vector": {
      "type": "knn_vector",
      "dimension": "__VECTOR_DIMENSION__",
      "method": {
        "name": "__ALGORITHM__",
        "space_type": "__SPACE_TYPE__",
        "engine": "__ENGINE__",
        "parameters": "__ENGINE_PARAMETERS__"
      }
    },
    "analyzed_text": {
      "type": "text",
      "analyzer": "my_custom_analyzer",
      "fields": {
        "keyword": {
          "type": "keyword",
          "ignore_above": 256
        }
      }
    }
  }
}
```

### Saving Custom Templates

1. Create your template JSON file
2. Save to `src/datasift/core/operators/vectordb/schemas/`
3. Name with version: `my_schema.v1.json`
4. Reference in flow configuration: `"schema_template_path": "schemas/my_schema.v1.json"`

## Validation Rules

Templates are validated before use. The following rules apply:

### Required Fields

- `schema_name` (string)
- `schema_version` (integer)
- `settings` (object)
- `field_types` (object)

### Vector Field Validation

- Must have `type: "knn_vector"`
- `dimension` must be positive integer
- `method` must include `name`, `space_type`, `engine`
- Engine must be one of: `faiss`, `lucene`, `nmslib`, `jvector`
- Algorithm must be one of: `hnsw`, `ivf`
- Space type must be one of: `l2`, `cosine`, `inner_product`

### Parameter Range Validation

**HNSW Parameters**:

- `ef_construction`: 1-1000 (recommended: 100-512)
- `m`: 2-100 (recommended: 16-48)

**IVF Parameters**:

- `nlist`: 1-10000 (recommended: 100-1000)
- `nprobe`: 1-nlist (recommended: 8-128)

### Analyzer Validation

- Analyzer names must be unique
- Tokenizer must be valid OpenSearch tokenizer
- Filters must be valid OpenSearch token filters

## Metadata Normalization

The VectorDBOperator automatically normalizes and aggregates metadata columns.

### Column Name Aliases

Common column name variations are automatically mapped:

| Target Field | Source Aliases                          | Description          |
| ------------ | --------------------------------------- | -------------------- |
| `source`     | `source`, `path`                        | Document source path |
| `page_count` | `page_count`, `pages_processed`         | Number of pages      |
| `mimetype`   | `mimetype`, `mime_type`, `content_type` | MIME type            |

### Field Derivation

Missing metadata fields are automatically derived:

- **extension**: Extracted from `name` or `source` filename
- **mimetype**: Derived from `extension` using standard mappings

### Predefined Metadata Fields

These fields are automatically collected into a `metadata` object:

- `name`: Document filename
- `size`: File size in bytes
- `created_time`: Creation timestamp
- `modified_time`: Modification timestamp
- `source`: Document source path
- `mimetype`: MIME type
- `extension`: File extension
- `page_count`: Number of pages

### Example Transformation

**Input**:

```python
{
  "path": "/docs/report.pdf",
  "name": "report.pdf",
  "pages_processed": 10,
  "content": "Document content..."
}
```

**Output** (automatically normalized):

```python
{
  "content": "Document content...",
  "metadata": {
    "source": "/docs/report.pdf",
    "name": "report.pdf",
    "page_count": 10,
    "extension": "pdf",
    "mimetype": "application/pdf"
  }
}
```

## Best Practices

### Template Design

1. **Use Semantic Names**: Name templates based on use case (e.g., `document_chunks`, `product_catalog`)
2. **Version Templates**: Include version in filename (`my_schema.v1.json`)
3. **Document Purpose**: Add comments in template describing intended use
4. **Test Thoroughly**: Validate templates with sample data before production use

### Configuration

1. **Match Vector Dimensions**: Ensure `vector_dimension` matches your embedding model
2. **Choose Appropriate Engine**:
   - `faiss`: Best for large-scale similarity search
   - `lucene`: Good for smaller datasets, native to OpenSearch
   - `nmslib`: Fast approximate search
3. **Tune Parameters**: Adjust `ef_construction` and `m` based on accuracy/speed tradeoff
4. **Use Appropriate Space Type**:
   - `l2`: Euclidean distance
   - `cosine`: Cosine similarity (normalized vectors)
   - `inner_product`: Dot product similarity

### Performance

1. **Shard Count**: Use 2-5 shards for most use cases
2. **Replica Count**: Use 0 replica for development, 1+ for production
3. **Batch Size**: Adjust based on document size and available memory
4. **Analyzer Complexity**: Balance search quality with indexing performance

## Examples

### Example 1: Basic Document Storage

```json
{
  "operator_params": {
    "provider": "opensearch",
    "index_name": "documents",
    "provider_config": {
      "schema_template_path": "schemas/default_schema.v1.json",
      "host": "localhost",
      "port": 9200,
      "engine": "faiss",
      "algorithm": "hnsw",
      "vector_dimension": 384
    },
    "feature_mappings": {
      "doc_id_hash": "id",
      "content": "content",
      "embeddings": "embeddings"
    },
    "available_features": {
      "embeddings": {
        "type": "vector",
        "available_for_vector_db": true
      },
      "content": {
        "type": "string",
        "available_for_vector_db": true
      },
      "doc_id_hash": {
        "type": "string",
        "available_for_vector_db": true
      }
    }
  }
}
```

### Example 2: Document Chunks with Custom Analyzer

```json
{
  "operator_params": {
    "provider": "opensearch",
    "index_name": "document_chunks",
    "provider_config": {
      "schema_template_path": "schemas/document_chunks_schema.v1.json",
      "host": "localhost",
      "port": 9200,
      "engine": "faiss",
      "algorithm": "hnsw",
      "vector_dimension": 768,
      "engine_parameters": {
        "ef_construction": 256,
        "m": 32
      }
    },
    "feature_mappings": {
      "chunk_id": "id",
      "content": "content",
      "embeddings": "embeddings",
      "doc_name": "doc_name",
      "chunk_index": "chunk_index"
    },
    "available_features": {
      "embeddings": {
        "type": "vector",
        "available_for_vector_db": true
      },
      "content": {
        "type": "content_text",
        "available_for_vector_db": true
      },
      "chunk_id": {
        "type": "string",
        "available_for_vector_db": true
      },
      "doc_name": {
        "type": "string",
        "available_for_vector_db": true
      },
      "chunk_index": {
        "type": "integer",
        "available_for_vector_db": true
      }
    }
  }
}
```

### Example 3: High-Dimensional Embeddings

```json
{
  "operator_params": {
    "provider": "opensearch",
    "index_name": "high_dim_vectors",
    "provider_config": {
      "schema_template_path": "schemas/default_schema.v1.json",
      "host": "localhost",
      "port": 9200,
      "engine": "faiss",
      "algorithm": "hnsw",
      "vector_dimension": 1536,
      "space_type": "cosine",
      "engine_parameters": {
        "ef_construction": 512,
        "m": 48
      }
    }
  }
}
```

## Troubleshooting

### Template Not Found

**Error**: `Schema template not found: schemas/my_schema.v1.json`

**Solutions**:

1. Verify file exists in `src/datasift/core/operators/vectordb/schemas/`
2. Check path is relative to `src/datasift/core/operators/vectordb/`
3. Ensure filename matches exactly (case-sensitive)

### Invalid Template Structure

**Error**: `Schema validation failed: missing required field 'schema_name'`

**Solutions**:

1. Ensure all required fields are present
2. Check JSON syntax is valid
3. Verify field types match expected types

### Placeholder Not Replaced

**Error**: `Invalid vector dimension: __VECTOR_DIMENSION__`

**Solutions**:

1. Ensure placeholder syntax is exact: `__PLACEHOLDER__`
2. Verify configuration provides values for all placeholders
3. Check template uses supported placeholders only

### Vector Dimension Mismatch

**Error**: `Vector dimension mismatch: expected 768, got 384`

**Solutions**:

1. Match `vector_dimension` in config to embedding model output
2. Common dimensions:
   - `nomic-embed-text`: 768
   - `text-embedding-ada-002`: 1536
   - `all-MiniLM-L6-v2`: 384

### Engine Parameter Out of Range

**Error**: `Parameter 'ef_construction' out of valid range: 2000`

**Solutions**:

1. Check parameter ranges in validation rules
2. Use recommended values:
   - `ef_construction`: 100-512
   - `m`: 16-48
3. Adjust based on accuracy/performance tradeoff

### Analyzer Not Found

**Error**: `Unknown analyzer: my_custom_analyzer`

**Solutions**:

1. Define analyzer in template's `settings.analysis` section
2. Verify analyzer name matches exactly
3. Check analyzer configuration is valid OpenSearch syntax

## Additional Resources

- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture and design patterns
- [OPERATOR_REFERENCE.md](../OPERATOR_REFERENCE.md) - VectorDBOperator documentation
- [USER_GUIDE_PIPELINE_SETUP.md](../USER_GUIDE_PIPELINE_SETUP.md) - Complete pipeline setup guide
- [OpenSearch KNN Documentation](https://opensearch.org/docs/latest/search-plugins/knn/index/) - Official OpenSearch KNN guide
