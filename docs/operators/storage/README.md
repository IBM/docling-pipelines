# Storage Operators

Storage operators persist or export pipeline data to durable destinations. They are placed at
checkpoints or at the end of a pipeline and do not disrupt the data flowing to downstream
operators (pass-through or append-only output schema).

## Operators

| Operator | Short name | Purpose |
| --- | --- | --- |
| [DocumentSetOperator](document_set_readme.md) | `document_set` | Persist a PyArrow table into a named DuckDB document set |
| [StorageOutputOperator](storage_output_readme.md) | `storage_output` | Write documents to a pluggable file destination (filesystem, etc.) |
