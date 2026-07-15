---
name: repo-review
description: Use when the user wants an architectural review or deep code review of the repository. Produces a structured report identifying dead code, broken abstractions, operator contract violations, and architectural gaps. Compares against previous reviews if they exist.
metadata:
  user-invocable: true
  disable-model-invocation: false
---

# Repo Review

Run in Agent mode (not Orchestrator — Agent has the file read tools needed).

Before starting, confirm:

- Latest code is pulled: `git pull`
- No unintended local-only files that would skew the review

## Review Focus

Scan for the "dirt" — concrete problems, not generalities:

- Dead code (unreachable, commented-out, unused imports/classes/functions)
- Broken abstractions (adapters imported from domain/application, DB calls in operators)
- Operator contract violations: missing `@staticmethod` on `get_metadata()`, wrong `category`, not in `DOCPIPE_OPERATORS` frozenset, f-strings in logger calls, emoji in log messages
- Architecture pattern: hexagonal (ports/adapters/domain/application) — how faithfully is it followed?
- Test gaps: operators without transform() happy-path test, API routes without auth test

Include file path + line number for every finding. Do not make code changes.

## Output

1. Create folder: `reviews/<YYYY-MM-DD>/`
2. Write one `.md` per area reviewed (e.g. `operators.md`, `orchestration.md`, `api.md`, `tests.md`)
3. If a previous `reviews/` folder exists, diff against it — note improvements and regressions
4. Write `reviews/<YYYY-MM-DD>/summary.md` linking all per-area files
5. Record stubs/unimplemented code in `reviews/<YYYY-MM-DD>/unimplemented.md` — exclude from quality grade

## Scope

- Include: `src/docpipe/`, `tests/`
- Exclude: `sample_flows/`, `notebooks/`, `docs/`

## Per-Area File Structure

Each area file must cover:

- Dominant patterns and abstractions found
- Violations with file path + line number + code snippet
- Test coverage gaps
- Grade: A / B / C / D / F with one-sentence reasoning

## Summary File

- Overall repo grade
- Top 5 most critical findings across all areas (with file:line links)
- Links to each per-area file
- Comparison to previous review: improvements / regressions (if prior review exists)
