# PR Policy — Docling-Pipelines Standards

Rules that apply specifically to the **docling-pipelines** repository. These enforce Python coding conventions,
operator architecture patterns, and project-specific standards unique to this codebase.

Run these checks after the common rules in `common.md` have been completed.

**Enforcement modes:**
- **PROMPT** — Ask the developer. Proceed based on their Yes/No response.
- **AUTO-FIX** — Bob applies the fix automatically when the developer agrees.
- **ADVISORY** — Informational only. Note findings in the PR body; never block.

**Applies to:** All `.py` files under `src/datasift/`

---

## Rule 1: Keyword-Only Function Arguments

**Mode: PROMPT + AUTO-FIX**

All function and method definitions with 2 or more parameters (excluding `self` and `cls`) must use
the `*` separator to enforce keyword-only arguments. This is a project-wide convention applied
throughout `src/datasift/`.

### What to check
Scan the diff for `def` signatures that have positional parameters without a `*` separator.
Single-parameter functions (excluding `self`/`cls`) are exempt.

```python
# Non-compliant
def __init__(self, config: dict, mode: str) -> None:

# Compliant
def __init__(self, *, config: dict, mode: str) -> None:
```

### Workflow
1. Scan all new or modified `def` signatures in the diff.
2. Identify signatures with 2+ parameters (excluding `self`/`cls`) that lack `*`.
3. If any are found:
   - Show the offending signatures to the developer.
   - Ask: *"These functions use positional arguments. Make them keyword-only by adding `*`? (Yes / No)"*
   - **Yes** — Bob adds the `*` separator to each flagged signature and updates call sites within the diff scope.
   - **No** — Continue PR. Note the deviation in the PR body under "Code Standards Deviations".
4. If none are found, proceed without prompting.

---

## Rule 2: New Operator — `get_metadata()` Must Be `@staticmethod`

**Mode: PROMPT**

Any new class that subclasses `AbstractOperator` must implement `get_metadata()` as a `@staticmethod`.
Metadata must not depend on instance state — it is used for operator discovery and UI rendering
before the operator is instantiated.

### What to check
Detect new classes inheriting from `AbstractOperator` in the diff. Check whether their `get_metadata`
method has the `@staticmethod` decorator.

```python
# Non-compliant
def get_metadata(self) -> dict[str, Any]:

# Compliant
@staticmethod
def get_metadata() -> dict[str, Any]:
```

### Workflow
1. Detect new `AbstractOperator` subclasses in the diff.
2. For each, check if `get_metadata` has `@staticmethod`.
3. If the decorator is missing:
   - Ask: *"`get_metadata()` is missing the `@staticmethod` decorator. Please add it and remove `self` from the signature, then confirm when done. (Yes, I will fix it / No, proceed as-is)"*
   - **Yes** — Stop. Wait for the developer to apply the fix before proceeding.
   - **No** — Continue PR without blocking.
4. If the decorator is present, proceed without prompting.

---

## Rule 3: Built-In Operator — Must Be Registered in `DATASIFT_OPERATORS`

**Mode: PROMPT + AUTO-FIX**

Built-in operators (those with `owner = DatasiftConstants.OWNER_DATASIFT`) must be added to the
`DATASIFT_OPERATORS` frozenset in `operator_registry.py`. Unregistered operators are invisible to
the CLI (`--list-operators`) and the pipeline executor.

### Workflow
1. Detect new operator classes with `owner = DatasiftConstants.OWNER_DATASIFT` in the diff.
2. Check whether the class appears in the `DATASIFT_OPERATORS` frozenset in `operator_registry.py`.
3. If it is missing:
   - Ask: *"This operator is not registered in `DATASIFT_OPERATORS`. Add it now? (Yes / No)"*
   - **Yes** — Bob adds the import and the class to the frozenset.
   - **No** — Note the gap in the PR body.
4. If already registered, proceed.

---

## Rule 4: `get_required_features()` Instance + Static Pair

**Mode: ADVISORY**

If a new or modified operator implements `get_required_features()` as an instance method (using `self`),
a companion `get_static_required_features()` static method should also be implemented. This dual-method
pattern is required for operator discovery and metadata resolution without instantiation.

```python
# When get_required_features uses self, also implement:
@staticmethod
def get_static_required_features() -> list[str]:
    return [OperatorConstants.Columns.DOC_COLUMN_DEFAULT]
```

### Workflow
1. Detect `def get_required_features(self` in the diff.
2. Check whether `get_static_required_features` is also defined as a `@staticmethod` in the same class.
3. If missing, note in the PR body: *"Instance `get_required_features()` found. Consider adding `get_static_required_features()` for operator discovery without instantiation."*
4. Do not block or prompt.

---

## Rules Delegated to Existing Policies

The following checks are enforced by existing workspace rules. This file references them — they are not redefined here.

| Check | Enforced by |
|---|---|
| No unicode/emoji in logging statements | `use-unicode-chars.md` |
| No "Made with Bob" in Python code | `python.md` |
| PR template must be used and complete | `git-policy.md` — Pull Request Template Policy |
| Secrets detection (`detect-secrets`) must pass | `git-policy.md` — Pre-Commit Hook Verification Policy |
| `--no-verify` and `--force` flags are blocked | `git-policy.md` — Command Restrictions |

---

## Enforcement Summary

| # | Rule | Mode | Auto-fix | Scope |
|---|---|---|---|---|
| 1 | Keyword-only function arguments | PROMPT | Yes | All Python files in diff |
| 2 | `get_metadata()` must be `@staticmethod` | PROMPT | No | New operators |
| 3 | Built-in operator must be registered | PROMPT | Yes | New built-in operators |
| 4 | `get_required_features()` instance + static pair | ADVISORY | No | Modified operators |
