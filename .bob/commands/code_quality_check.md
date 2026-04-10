# Code Quality Check Command

## Command Name
`code_quality_check`

## Description
Run a comprehensive code quality analysis on the folder 'src/datasift_opensource/backend' and generate a detailed report with the following structure:

## Analysis Requirements

### 1. Type Checking (MyPy)
- Run: `cd src/datasift_opensource/backend && uv run mypy . --config-file=pyproject.toml 2>&1 | tee mypy_output.txt`
- Count total errors
- Categorize errors by type:
  - Missing library stubs
  - Type incompatibilities
  - Override violations
  - Missing annotations
  - Import errors
  - Other errors
- Identify top 5 critical type errors with file paths and line numbers

### 2. Linting (Ruff)
- Run: `cd src/datasift_opensource/backend && uv run ruff check . --output-format=json 2>&1 | tee ruff_output.txt`
- Count total issues
- Categorize by severity (High/Medium/Low)
- Group by rule category (UP, B, E402, RUF, C4, etc.)
- List all issues with file paths and line numbers

### 3. Formatting Check (Ruff Format)
- Run: `cd src/datasift_opensource/backend && uv run ruff format --check . 2>&1 | tee format_output.txt`
- Count files needing formatting
- Calculate percentage of formatted files

### 4. Syntax Errors (Flake8)
- Run: `cd src/datasift_opensource/backend && uv run flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics 2>&1`
- Report critical syntax error count

### 5. File Count
- Run: `cd src/datasift_opensource/backend && find . -name "*.py" -not -path "./.venv/*" -not -path "./.ruff_cache/*" -not -path "./__pycache__/*" | wc -l`

## Report Structure

Generate a report with these sections:

### 📊 Executive Summary
- Analysis date and time
- Total Python files
- Overall quality rating (0-10 scale)

### 🎯 CRITICAL FINDINGS
Identify and detail the TOP 3 most critical issues:
1. **Critical Issue #1**: [Name]
   - Location: file path and line numbers
   - Severity: CRITICAL/HIGH/MEDIUM
   - Code snippet showing the error
   - Impact description
   - Recommended fix

2. **Critical Issue #2**: [Name]
   - [Same structure as above]

3. **Critical Issue #3**: [Name]
   - [Same structure as above]

### 📈 DETAILED METRICS

#### Type Checking (MyPy)
```
Total Lines Analyzed: [number]
Total Errors: [number]
Error Rate: [percentage]

Breakdown:
├─ Missing library stubs: [count] ([percentage])
├─ Type incompatibilities: [count] ([percentage])
├─ Override violations: [count] ([percentage])
├─ Missing annotations: [count] ([percentage])
├─ Import errors: [count] ([percentage])
└─ Other errors: [count] ([percentage])
```

#### Linting (Ruff)
```
Total Issues: [number]
Severity Distribution:
├─ High: [count] ([percentage])
├─ Medium: [count] ([percentage])
└─ Low: [count] ([percentage])

Categories:
├─ Code modernization (UP): [count]
├─ Bugbear (B): [count]
├─ Import order (E402): [count]
└─ Other (RUF, C4): [count]
```

#### Formatting (Ruff Format)
```
Files Analyzed: [number]
├─ Need Formatting: [count] ([percentage])
└─ Already Formatted: [count] ([percentage])
```

#### Syntax Errors (Flake8)
```
Critical Syntax Errors: [count] ✅/⚠️
```

### 🚨 TOP 10 CRITICAL ISSUES
Create a table with:
| # | File | Line | Issue | Severity |
|---|------|------|-------|----------|
| 1 | [file] | [line] | [description] | [severity] |
[... continue for 10 rows]

### 📋 ISSUE CATEGORIES

#### Missing Library Stubs ([count] errors)
List libraries with missing stubs and occurrence counts

#### Type Annotation Issues ([count] errors)
Summarize missing annotation patterns

#### Override Violations ([count] errors)
List files with LSP violations

### 🎨 CODE STYLE ISSUES (Ruff)

#### High Priority ([count] issues)
List with rule codes and descriptions

#### Medium Priority ([count] issues)
List with rule codes and descriptions

#### Low Priority ([count] issues)
List with rule codes and descriptions

### ✅ POSITIVE FINDINGS
List 5 positive aspects of the codebase

### 📊 QUALITY RATING BREAKDOWN

Calculate weighted score:

| Category | Score | Weight | Notes |
|----------|-------|--------|-------|
| **Type Safety** | [0-10] | 30% | [notes] |
| **Code Style** | [0-10] | 20% | [notes] |
| **Formatting** | [0-10] | 15% | [notes] |
| **Syntax** | [0-10] | 15% | [notes] |
| **Maintainability** | [0-10] | 20% | [notes] |

**Weighted Score:** [calculation] = **[X.X]/10**

### 🔧 RECOMMENDED ACTION PLAN

#### 🚀 Immediate (This Week)
List 3-5 actionable items with bash commands

#### 📅 Short-term (Next 2 Weeks)
List 4-6 actionable items

#### 🎯 Long-term (Next Quarter)
List 4-5 strategic improvements

### 💡 KEY INSIGHTS
List 5 key observations about code quality

### 🎓 COMPARISON TO STANDARDS

| Standard | Expected | Actual | Gap |
|----------|----------|--------|-----|
| Enterprise Grade | 8-9/10 | [X.X]/10 | [status] |
| Production Ready | 7-8/10 | [X.X]/10 | [status] |
| Mid-stage Startup | 6-7/10 | [X.X]/10 | [status] |
| Prototype | 4-5/10 | [X.X]/10 | [status] |

**Verdict:** [assessment]

### 📝 CONCLUSION
Provide 2-3 paragraph summary with:
- Current state assessment
- Most critical issues
- Timeline for improvement
- Next steps

## Scoring Guidelines

### Type Safety (0-10)
- 10: Zero type errors, 100% coverage
- 8-9: <10 errors, >90% coverage
- 6-7: 10-50 errors, >70% coverage
- 4-5: 50-150 errors, >50% coverage
- 2-3: 150-300 errors, >30% coverage
- 0-1: >300 errors or <30% coverage

### Code Style (0-10)
- 10: Zero linting issues
- 8-9: <10 issues, all low severity
- 6-7: 10-30 issues, mostly low/medium
- 4-5: 30-100 issues, some high severity
- 2-3: 100-200 issues
- 0-1: >200 issues

### Formatting (0-10)
- 10: 100% formatted
- 8-9: >95% formatted
- 6-7: 80-95% formatted
- 4-5: 60-80% formatted
- 2-3: 40-60% formatted
- 0-1: <40% formatted

### Syntax (0-10)
- 10: Zero critical syntax errors
- 8-9: 1-2 minor syntax warnings
- 6-7: 3-5 syntax issues
- 4-5: 6-10 syntax issues
- 2-3: 11-20 syntax issues
- 0-1: >20 syntax issues

### Maintainability (0-10)
- 10: Excellent documentation, clear structure
- 8-9: Good documentation, minor issues
- 6-7: Adequate documentation, some complexity
- 4-5: Limited documentation, high complexity
- 2-3: Poor documentation, very complex
- 0-1: No documentation, unmaintainable

## Output Format
- Use markdown formatting
- Include emojis for visual clarity
- Use code blocks for commands and examples
- Create tables for structured data
- Use tree diagrams for hierarchical data
- Bold critical information
- Use color indicators: 🔴 (critical), 🟡 (medium), 🟢 (low)

## Quality Rating Formula
```
Overall Score = (Type Safety × 0.30) + 
                (Code Style × 0.20) + 
                (Formatting × 0.15) + 
                (Syntax × 0.15) + 
                (Maintainability × 0.20)
```

## Critical Issue Priority Order
1. Forward reference errors (breaks type system)
2. Method override violations (breaks polymorphism)
3. Type incompatibilities (runtime errors)
4. Import errors (breaks execution)
5. Missing annotations (reduces type safety)

## Prerequisites
- Must be in project root directory
- Virtual environment activated or use `uv run` prefix
- All dev dependencies installed: `uv sync --extra dev`

## Example Usage
Simply say: "code_quality_check" or "Run code quality check"

## Version
1.0.0 (2026-04-09)