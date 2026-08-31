# Built-in Operator References

Choose examples by behavior, not merely by category. Read the implementation, its unit tests, metadata, and one representative flow before starting.

## Behavior map

| Needed behavior | Implementation | Tests | Flow or documentation |
|---|---|---|---|
| Pass-through and basic metadata | `src/docpipe/core/operators/functional/noop.py` | `tests/unit/operators/noop/test_noop.py` | `sample_flows/advanced/branching_quality_routing.json` |
| Add a deterministic identifier column | `src/docpipe/core/operators/functional/doc_id_hash.py` | `tests/unit/operators/doc_id/test_doc_id_hash.py` | Search `sample_flows/` for `doc_id_hash` |
| Filter rows from JSON criteria | `src/docpipe/core/operators/quality/sql_filter.py` | `tests/unit/operators/filter/test_sql_filter.py` | `sample_flows/advanced/quality_branching_merge_pipeline.json` |
| Expand documents into chunks | `src/docpipe/core/operators/functional/chunker.py` | `tests/unit/operators/chunker/test_chunker.py` | `sample_flows/advanced/hybrid_chunking.json` |
| Produce named output branches | `src/docpipe/core/operators/functional/branching_operator.py` | `tests/unit/operators/branching/test_branching_operator.py` | `sample_flows/advanced/branching_quality_routing.json` |
| Consume and combine branches | `src/docpipe/core/operators/functional/merge.py` | `tests/unit/operators/merge/test_merge.py` | `sample_flows/advanced/quality_branching_merge_pipeline.json` |
| Use an embedding port/provider | `src/docpipe/core/operators/functional/embeddings/embeddings_operator.py` | `tests/unit/operators/embeddings/test_embeddings_operator.py` | `sample_flows/quickstart/complete_pipeline_ollama.json` |
| Use LLM-backed classification | `src/docpipe/core/operators/quality/classification/document_classifier.py` | `tests/unit/operators/classify/test_document_classifier.py` | `sample_flows/operators/classification_ollama.json` |
| Add several typed quality features | `src/docpipe/core/operators/quality/readability/readability_operator.py` | `tests/unit/operators/readability/test_readability.py` | `sample_flows/advanced/quality_branching_merge_pipeline.json` |
| Write through a destination port | `src/docpipe/core/operators/storage/storage_output_operator.py` | `tests/unit/operators/storage/test_storage_output_operator.py` | `sample_flows/storage_output/processed_content_s3.json` |

Some older implementations contain styles that newer repository rules prohibit. Reuse architecture and table semantics, but apply current keyword-only and lazy-logging requirements from `AGENTS.md` and the skill.

## Metadata and validation references

- Base contract: `src/docpipe/core/operators/abstract_operator.py`
- Metadata keys: `src/docpipe/core/constants/operator_constants.py`
- Flow feature propagation: `src/docpipe/core/orchestration/flow_validator.py`
- Public parameter reference: `docs/reference/OPERATORS.md`
- Operator documentation structure: `docs/guides/DOCUMENTATION_STYLE_GUIDE.md`

For conditional required columns, compare `get_required_features()`, `get_static_required_features()`, metadata features, and flow-validator behavior rather than changing only one surface.

## Registry references

- Built-in imports and `DOCPIPE_OPERATORS`: `src/docpipe/core/operators/operator_registry.py`
- Resolution and availability: `src/docpipe/core/orchestration/operator_factory.py`
- Registry/API visibility: `tests/unit/api/routes/test_operators_routes.py`
- Factory integration: `tests/integration/test_operator_factory_integration.py`

The class, registry import, frozenset entry, metadata, docs, and flow `type` must use the same `short_name`.

## Test-shape references

- Shared fixtures: `tests/conftest.py`
- Operator expectations: `docs/guides/TESTING_STANDARDS.md`
- Generic starting template: `tests/templates/test_operator_template.py`

Treat the template as a checklist, not finished code: replace placeholder `pass` statements with exact schema, value, and metadata assertions, and prefer the closest real operator test for mocking patterns.
