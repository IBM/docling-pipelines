---
name: code-quality-check
description: Use when the user wants to run a code quality check or analysis on the docpipe source. Runs MyPy and Ruff on src/docpipe and generates a structured report with metrics, critical issues, and a weighted quality score.
metadata:
  user-invocable: true
  disable-model-invocation: false
---

# Code Quality Check

Run a comprehensive code quality analysis on `src/docpipe` and generate a structured report.

## Prerequisites

- Must be in project root directory
- `uv run` handles the venv — no manual activation needed
- Dev dependencies installed: `uv pip install -e .[dev]`

## Analysis Steps

### 1. Quick check (canonical)

Run all hooks together first to see the overall picture:

```bash
pre-commit run ruff-format ruff mypy --all-files 2>&1
```

### 2. Type Checking (MyPy)

```bash
uv run mypy src/docpipe --config-file=pyproject.toml 2>&1
```

Capture and categorize:

- Missing library stubs
- Type incompatibilities
- Override violations
- Missing annotations
- Import errors
- Other

Identify top 5 critical errors with file path + line number.

### 3. Linting (Ruff)

```bash
uv run ruff check src/docpipe --output-format=json 2>&1
```

Categorize by rule group (UP, B, E, RUF, C4) and count. Map to High/Medium/Low severity:

- High: B (bugbear), F (pyflakes errors), E9 (syntax)
- Medium: E (style), W (warnings), RUF
- Low: UP (pyupgrade), C4 (comprehensions), I (imports)

### 4. Formatting (Ruff Format)

```bash
uv run ruff format --check src/docpipe 2>&1
```

Count files needing formatting. Note: ruff-format is authoritative — flake8 is not used in this project.

### 5. File Count

```bash
find src/docpipe -name "*.py" ! -path "*/__pycache__/*" | wc -l
```

> Do NOT write output to temp files (mypy_output.txt etc.) — they pollute `git status`.

## Report Structure

### Executive Summary

| Metric                       | Value |
| ---------------------------- | ----- |
| Python files                 |       |
| Overall quality score (0–10) |       |
| MyPy errors                  |       |
| Ruff issues                  |       |
| Files needing formatting     |       |

### Critical Findings

Top 3 issues — each with:

- Location: `file:line`
- Severity: CRITICAL / HIGH / MEDIUM
- Code snippet (3–5 lines)
- Impact
- Recommended fix

### Detailed Metrics

**Type Checking (MyPy)**

| Category               | Count | %   |
| ---------------------- | ----- | --- |
| Missing library stubs  |       |     |
| Type incompatibilities |       |     |
| Override violations    |       |     |
| Missing annotations    |       |     |
| Import errors          |       |     |
| Other                  |       |     |

**Linting (Ruff)**

| Severity | Count | %   |
| -------- | ----- | --- |
| High     |       |     |
| Medium   |       |     |
| Low      |       |     |

**Formatting**

| Status            | Count | %   |
| ----------------- | ----- | --- |
| Needs formatting  |       |     |
| Already formatted |       |     |

### Top 10 Issues

| #   | File | Line | Rule | Severity |
| --- | ---- | ---- | ---- | -------- |

### Quality Rating Breakdown

| Category        | Score (0–10) | Weight |
| --------------- | ------------ | ------ |
| Type Safety     |              | 30%    |
| Code Style      |              | 20%    |
| Formatting      |              | 15%    |
| Syntax          |              | 15%    |
| Maintainability |              | 20%    |

Overall Score = (Type Safety × 0.30) + (Code Style × 0.20) + (Formatting × 0.15) + (Syntax × 0.15) + (Maintainability × 0.20)

### Scoring Guidelines

| Category        | 10        | 8–9  | 6–7      | 4–5     | 2–3     | 0–1  |
| --------------- | --------- | ---- | -------- | ------- | ------- | ---- |
| Type Safety     | 0 errors  | <10  | 10–50    | 50–150  | 150–300 | >300 |
| Code Style      | 0 issues  | <10  | 10–30    | 30–100  | 100–200 | >200 |
| Formatting      | 100%      | >95% | 80–95%   | 60–80%  | 40–60%  | <40% |
| Syntax          | 0 errors  | 1–2  | 3–5      | 6–10    | 11–20   | >20  |
| Maintainability | Excellent | Good | Adequate | Limited | Poor    | None |

### Positive Findings

List 5 positive aspects of the codebase.

### Recommended Action Plan

- **Immediate (this week):** 3–5 items with exact commands
- **Short-term (next 2 weeks):** 4–6 items
- **Long-term (next quarter):** 3–5 strategic improvements

### Conclusion

2–3 sentences: current state, most critical issue, single next step.
