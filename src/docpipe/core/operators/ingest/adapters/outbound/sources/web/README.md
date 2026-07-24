# Web Page Source Adapter

A LangChain-based adapter for ingesting public web pages and documentation sites using recursive crawling.

## Features

- **Recursive crawling**: Uses LangChain `RecursiveUrlLoader` to follow links from one or more seed URLs
- **Multi-URL ingest**: Accepts multiple starting URLs in a single configuration
- **Domain boundary controls**: Restrict crawling to the starting domain with `prevent_outside`
- **Exclude patterns**: Skip unwanted URL paths such as login, admin, or API endpoints
- **HTML preservation**: Stores fetched page content as UTF-8 encoded raw HTML
- **Normalized metadata**: Emits `content_type`, `file_size`, `depth`, and `url` metadata for each crawled page

## Quick Start

### Prerequisites

1. Python 3.8+ with `uv`
2. Public HTTP or HTTPS URLs to crawl
3. LangChain community loader dependency installed

### Install Dependencies

```bash
# From project root
uv pip install langchain-community requests
```

## Configuration Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `urls` | list[str] | Yes | - | One or more HTTP/HTTPS starting URLs |
| `max_depth` | int | No | `2` | Maximum recursive crawl depth. `0` crawls only the seed URL |
| `prevent_outside` | bool | No | `true` | Restrict crawling to pages within the starting domain |
| `exclude_patterns` | list[str] | No | `[]` | URL path patterns excluded from crawling; passed to `RecursiveUrlLoader` as `exclude_dirs` |
| `timeout` | int | No | `30` | Request timeout in seconds |

## Behavior

The adapter creates one LangChain `RecursiveUrlLoader` per configured seed URL with these runtime characteristics:

- `url=<seed URL>`
- `max_depth=<configured max_depth>`
- `prevent_outside=<configured prevent_outside>`
- `exclude_dirs=<exclude_patterns or None>`
- `timeout=<configured timeout>`

Each crawled LangChain document is converted into a Docling Pipelines ingest document with:

- SHA-256 document ID generated from the resolved page URL
- document name from page title metadata, or URL path fallback
- UTF-8 encoded HTML bytes as document content
- `content_type: text/html`
- `file_size`: calculated from the encoded HTML byte length
- `depth`: crawl depth from loader metadata
- `url`: resolved source URL

## Timestamp Behavior

Web pages do not expose reliable filesystem-style timestamps in this adapter.

- `file_size` is populated
- `created_time` is not populated
- `modified_time` is not populated in the output document/table

If downstream logic expects file timestamps, treat web-ingested records as timestamp-less documents.

## Usage Patterns

### Single documentation site

Use one seed URL with domain restriction enabled.

```json
{
        "provider": "web",
        "connection_params": {
          "urls": [
            "https://example.com"
          ],
          "max_depth": 2,
          "prevent_outside": true,
          "exclude_patterns": [
            "/admin",
            "/login",
            "/api"
          ],
          "timeout": 30
        }
}
```

### Multiple seed URLs

Use multiple URLs when bootstrapping content from more than one site.

```json
{
        "provider": "web",
        "connection_params": {
          "urls": [
            "https://example.com",
            "https://www.iana.org/domains/reserved"
          ],
          "max_depth": 2,
          "prevent_outside": true,
          "exclude_patterns": [
            "/admin",
            "/login",
            "/api"
          ],
          "timeout": 30
        }
}
```

### Landing page only

Use `max_depth: 0` to ingest only the seed page without following links.

```json
{
        "provider": "web",
        "connection_params": {
          "urls": [
            "https://example.com"
          ],
          "max_depth": 0,
          "prevent_outside": true,
          "exclude_patterns": [],
          "timeout": 30
        }
}
```

## Example Flow Configuration

```json
{
  "flow_name": "Web Page Ingestion",
  "flow": [
    {
      "name": "ingest_web",
      "type": "ingest_source",
      "config": {
        "provider": "web",
        "connection_params": {
          "urls": [
            "https://example.com",
            "https://www.iana.org/domains/reserved"
          ],
          "max_depth": 1,
          "prevent_outside": true,
          "exclude_patterns": [
            "/admin",
            "/login",
            "/api"
          ],
          "timeout": 30
        }
      }
    }
  ]
}
```

## Output Notes

Web-ingested records are appropriate for downstream extract and chunking flows, with a few source-specific differences:

- content is HTML, not binary office/PDF content
- `file_size` reflects HTML byte length
- no reliable created/modified timestamps are available
- page title may be absent, in which case the adapter falls back to the URL path

## Testing

Unit tests for this adapter are located at:

- `tests/unit/operators/ingest/test_web_source_adapter.py`

Example connector test script:

- `examples/connectors/test_web_adapter.py`

## Troubleshooting

### No pages returned

- Verify each URL is public and reachable
- Start with `max_depth: 0` or `1`
- Remove `exclude_patterns` temporarily to confirm filtering is not too aggressive

### Crawling leaves the expected site

- Set `prevent_outside: true`
- Review the seed URL and ensure it starts on the intended domain

### Pages are skipped unexpectedly

- Check `exclude_patterns`; they are mapped to `RecursiveUrlLoader.exclude_dirs`
- Confirm the URLs use `http://` or `https://`

### Timeout errors

- Increase `timeout`
- Reduce `max_depth`
- Test the seed URLs directly in a browser or with `curl`

## References

- [LangChain RecursiveUrlLoader](https://python.langchain.com/docs/integrations/document_loaders/recursive_url_loader/)