# Proposal

## Why

Pipelines have no built-in way to count how often configured words or phrases appear in each document. A dedicated,
bounded, deterministic keyword counter gives lexical enrichment without regex risk or runtime downloads.

## What Changes

- Add a built-in Functional operator `KeywordCountOperator` (short name `keyword_count`, owner `docpipe`).
- Emit exactly one fixed, non-configurable output column `keyword_counts` of Arrow type `map<string, int64>`; when the
  column already exists, merge new counts into it (append new keys, add counts for repeated exact keys with checked
  `int64` addition).
- Support three matching modes: `literal` (default, existing `google-re2` in literal mode with Unicode-aware whole-word
  boundaries), `stem` (existing NLTK `SnowballStemmer`, no corpora), and `lemma` (an administrator-installed spaCy
  pipeline package, never downloaded at runtime).
- Enforce fixed limits: at most 20 keywords per instance, 50 code points per keyword, 1,000 combined code points, and
  1,000,000 characters per document in linguistic modes; reject (never truncate) violations.
- Fail closed: no fallback between modes, no fallback from RE2 to Python `re`, no model or corpus downloads.
- Emit aggregate execution metadata (`documents_with_matches`, `total_matches`, `match_mode`) without per-keyword
  disclosure; never log keywords or document text.
- Emit a flow-validation warning when all `keyword_count` nodes together exceed 100 keyword entries.
- Register the operator in `DOCPIPE_OPERATORS` and document it (operator README, operator reference, README table, and
  a sample flow).

## Capabilities

### New Capabilities
- `keyword-count-operator`: Per-document counting of configured keywords and phrases into the fixed `keyword_counts`
  map, including configuration validation, literal/stem/lemma matching semantics, row-level behavior, map merge rules,
  discovery metadata, execution metadata, and security/privacy controls.

### Modified Capabilities
<!-- None: no existing capabilities are recorded under openspec/specs/. -->

## Impact

- New code: `src/docpipe/core/operators/functional/keyword_count.py`,
  `src/docpipe/core/operators/functional/keyword_normalization.py`.
- Modified code: `src/docpipe/core/operators/operator_registry.py` (import + `DOCPIPE_OPERATORS`),
  `src/docpipe/core/operators/functional/__init__.py` (export),
  `src/docpipe/core/constants/operator_constants.py` and `src/docpipe/core/constants/constants.py` (operator/config
  name constants and execution-metric names), the flow-level aggregate keyword warning in
  `src/docpipe/core/orchestration/flow_validator.py` with its message in `src/docpipe/exceptions/error_messages.py`,
  and `SUM` aggregation entries for the new match counters in
  `src/docpipe/core/job_management/application/aggregation/strategies.py`.
- Dependencies: none added. Uses existing `google-re2==1.1.20251105`, `nltk==3.10.3`, and `spacy>=3.7.4`. Lemma mode
  requires a separately installed spaCy pipeline; no pipeline is installed in the base environment.
- Tests: new `tests/unit/operators/keyword_count/`.
- Docs: new `docs/operators/functional/keyword_count_readme.md`; updates to `docs/reference/OPERATORS.md` and
  `README.md`; new sample flow under `sample_flows/operators/`.
- Schema: downstream consumers see one new `map<string, int64>` column, advertised as a `json` feature that is not
  filterable or vector-database eligible.
