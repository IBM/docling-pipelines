# PR Policy — Common Rules

Rules that apply to **all pull requests** regardless of repository, language, or project type.
These rules run first, before any repository-specific checks.

**Enforcement modes:**
- **PROMPT** — Ask the developer. Proceed based on their Yes/No response.
- **ADVISORY** — Informational only. Note findings in the PR body; never block.

---

## Rule 1: PR Size — More Than 20 Changed Python Files

**Mode: PROMPT**

If the diff touches more than 20 `.py` files, ask the developer whether the PR can be split into smaller, more focused units. Non-Python files (config, YAML, JSON, markdown, requirements, etc.) are excluded from the count entirely.

### Workflow
1. Count changed `.py` files only: `git diff --name-only <base_branch> | grep '\.py$' | wc -l`
2. If the count exceeds 20:
   - Ask: *"This PR changes N Python files. Would you like suggestions on how it could be broken down into smaller PRs? (Yes — suggest a breakdown / No — continue with this PR)"*
   - **Yes** — Analyse the changed files and suggest a possible breakdown by module, layer, or concern. Present the suggested split clearly — **do not create branches, commits, or make any changes at this stage**. Then ask: *"Would you like Bob to create these smaller PRs, or will you handle it yourself? (Bob creates them / I'll do it myself)"*
     - **Bob creates them** — Share the full implementation plan first (branch names, files per PR, order of merging). Wait for explicit developer confirmation before making any changes. On confirmation, proceed with implementation.
     - **I'll do it myself** — Stop. Do not proceed with the original PR. Developer will create the smaller PRs themselves.
   - **No** — If the bulk of the `.py` files are `__init__.py` re-exports with no logic changes, note this in the PR body and continue. Otherwise append: *"This PR contains N changed Python files. The developer confirmed it cannot be split further."* and continue.
3. If the count is 20 or fewer, proceed without prompting.

---

## Rule 2: Initial PR Review

**Mode: ADVISORY (with inline fix prompt)**

A lightweight automated first-pass review that catches surface-level issues a human reviewer would immediately flag. Not a deep code review — the goal is to eliminate obvious problems before the PR reaches a human reviewer, saving a review round-trip.

### What is checked

**1. Dead code**
Commented-out code blocks in new or modified lines (e.g. `# old logic`, `# TODO remove`, large commented blocks).

**2. Debug artifacts**
`print()`, `breakpoint()`, or `pdb.set_trace()` calls in new or modified lines.

**3. Overly large functions**
Any new or modified function exceeding 60 lines is flagged for the developer's consideration.

**4. Missing docstrings**
New public functions or methods (not prefixed with `_`) that have no docstring.

**5. Exception handling hygiene**
Bare `except:` or `except Exception: pass` blocks, or catch blocks that neither log nor re-raise the exception.

**6. Logging hygiene**
f-strings used directly inside `logger.*()` calls instead of `%s`-style formatting.
```python
# Non-compliant
logger.info(f"Processing {doc_id}")

# Compliant
logger.info("Processing %s", doc_id)
```

**7. Import hygiene**
`import *` usage in any changed file. Unused imports are already caught by ruff — Bob surfaces them early with the exact line number.

### What is NOT checked
- Logic correctness — that is for the human reviewer
- Architecture or design decisions
- Performance optimisations
- Test quality or coverage depth

### Workflow
1. Run after all other rules have been checked.
2. If **no findings**: state *"Initial review passed. No surface-level issues found."* and proceed.
3. If **findings exist**:
   - Present a structured **Initial Review Report**:
     ```
     [DEAD CODE]   operator_utils.py:45      — commented-out block detected
     [DEBUG]       chunker.py:112            — print() statement found
     [DOCSTRING]   embeddings_operator.py:88 — public method missing docstring
     [EXCEPTION]   redaction.py:67           — bare except with no log or re-raise
     [LOGGING]     lang_id.py:34             — f-string used in logger.info()
     [LARGE FN]    extract_operator.py:55    — function _process_batch is 74 lines
     [IMPORT]      vectordb_operator.py:3    — import * detected
     ```
   - Ask: *"The initial review found N issue(s) listed above. Would you like to fix any of these before requesting human review? (Yes / No)"*
   - **Yes** — Developer fixes the items. Bob re-runs the scan to confirm findings are resolved before proceeding.
   - **No** — Append the full Initial Review Report to the PR body under the heading **"Initial Review Report"** so the human reviewer sees the acknowledged gaps upfront. Proceed with PR creation.

---

## Enforcement Summary

| # | Rule | Mode | Auto-fix | Scope |
|---|---|---|---|---|
| 1 | PR > 20 changed Python files | PROMPT | No | All PRs |
| 2 | Initial PR review (dead code, debug, docstrings, exceptions, logging, imports) | ADVISORY | No | All PRs |
