## ADDED Requirements

### Requirement: Index discovers all documentation files at startup
The docs indexer SHALL walk the `docs/` directory tree and a fixed list of top-level markdown files (`README.md`, `ARCHITECTURE.md`, `QUICKSTART.md`, `USER_GUIDE_PIPELINE_SETUP.md`, `TROUBLESHOOTING.md`) and build an in-memory index of their content at server startup.

#### Scenario: Full docs tree indexed
- **WHEN** the server starts in the repo root
- **THEN** all `.md` files under `docs/` SHALL be discovered and indexed
- **THEN** the total file count SHALL be logged at INFO level

#### Scenario: New doc file appears without restart
- **WHEN** a new markdown file is added to `docs/` after server startup
- **THEN** the file is NOT required to appear in search results until the server is restarted (index is built once at startup)

### Requirement: search_docs returns ranked excerpts matching a query
The `search_docs` tool SHALL accept a plain-text query string and return up to `max_results` (default 5, max 20) matching excerpts from the indexed documentation, each with a source file path, a relevance score, and a surrounding text excerpt.

#### Scenario: Query matches multiple files
- **WHEN** a client calls `search_docs` with `query="chunker overlap"`
- **THEN** results SHALL include excerpts from operator docs containing those terms
- **THEN** each result SHALL include `source`, `excerpt`, and `score` fields
- **THEN** results SHALL be ordered by descending relevance score

#### Scenario: Query matches nothing
- **WHEN** a client calls `search_docs` with a query that matches no indexed content
- **THEN** the tool SHALL return an empty results array and a message indicating no matches were found

#### Scenario: max_results is respected
- **WHEN** a client calls `search_docs` with `max_results=3`
- **THEN** at most 3 results SHALL be returned regardless of total match count

### Requirement: Index supports keyword-based matching
The indexer SHALL implement TF-IDF-style keyword matching or equivalent — it SHALL NOT require an embedding model or external ML service.

#### Scenario: Exact term match
- **WHEN** a query contains a word that appears verbatim in an indexed doc
- **THEN** that doc SHALL appear in search results

#### Scenario: Case-insensitive matching
- **WHEN** a query contains `"Chunker"` and the doc contains `"chunker"`
- **THEN** the match SHALL be found
