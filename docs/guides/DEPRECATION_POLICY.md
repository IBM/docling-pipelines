# Deprecation Policy

This document defines how `docling-pipelines` handles the deprecation and eventual removal of public APIs, operators, configuration parameters, and behaviours.

---

## Table of Contents

- [Scope](#scope)
- [Deprecation Lifecycle](#deprecation-lifecycle)
- [Deprecation Window](#deprecation-window)
- [How Deprecations Are Communicated](#how-deprecations-are-communicated)
- [Emergency Removals](#emergency-removals)
- [Operator Deprecation](#operator-deprecation)
- [Configuration Parameter Deprecation](#configuration-parameter-deprecation)
- [Python API Deprecation](#python-api-deprecation)
- [Flow JSON Schema Deprecation](#flow-json-schema-deprecation)
- [Experimental Features](#experimental-features)

---

## Scope

This policy applies to:

- Operator classes and their parameters
- `DocpipeFlowManager` public Python API
- Flow JSON configuration schema (node types, parameter names)
- REST API endpoints and response schemas
- CLI flags and environment variables
- Configuration file keys

Internal implementation details (private methods, internal modules prefixed with `_`) are not covered and may change without notice.

---

## Deprecation Lifecycle

```
Introduced → Deprecated → Removal warning → Removed
               (same or   (1 release before  (next MAJOR
               next MINOR)  removal)           version)
```

| Phase | Description |
|---|---|
| **Introduced** | Feature is added and fully supported. |
| **Deprecated** | Feature is marked as deprecated. A replacement is available (if applicable). Deprecation warning is emitted at runtime. |
| **Removal warning** | One release before removal, the CHANGELOG and documentation clearly state the final removal date. |
| **Removed** | Feature is deleted. Migration guide documents the upgrade path. |

---

## Deprecation Window

| Change type | Minimum deprecation window |
|---|---|
| Operator parameter renamed or removed | 2 MINOR releases |
| Operator removed | 2 MINOR releases |
| Python API method signature changed incompatibly | 2 MINOR releases |
| Flow JSON schema field renamed or removed | 2 MINOR releases |
| REST API endpoint removed or response schema changed | 1 MAJOR version cycle |
| CLI flag removed or renamed | 2 MINOR releases |
| Environment variable removed or renamed | 2 MINOR releases |

For MAJOR version bumps, deprecated items that have passed their window are removed.

No feature may be removed without first completing a full deprecation window, with the sole exception of [Emergency Removals](#emergency-removals).

---

## How Deprecations Are Communicated

### Runtime warnings

Deprecated Python APIs and operator parameters emit a `DeprecationWarning` at the point of use:

```python
import warnings

warnings.warn(
    "The 'old_param' parameter is deprecated as of v1.2.0 and will be removed in v2.0.0. "
    "Use 'new_param' instead.",
    DeprecationWarning,
    stacklevel=2,
)
```

### CHANGELOG

Each deprecated item has an entry under `### Deprecated` in the release's CHANGELOG section, specifying:

- What is deprecated
- The replacement (if any)
- The planned removal version

### Documentation

Documentation pages for deprecated items include a prominent notice:

```
> **Deprecated since v1.2.0.**
> This feature will be removed in v2.0.0.
> Use [replacement] instead.
```

### GitHub Issues

A tracking issue labelled `deprecation` is opened for each deprecated item. The issue is closed when the item is removed.

---

## Emergency Removals

A feature may be removed before the standard deprecation window expires only when:

- A security vulnerability (CVE) in the feature cannot be mitigated without removal, **or**
- A critical licensing issue requires immediate removal.

In such cases:

1. A GitHub Security Advisory is published.
2. The CHANGELOG entry under `### Security` documents the removal.
3. A migration guide is published on the same day as the release.
4. Maintainers announce the emergency removal through all communication channels listed in the [Release Process](../../RELEASE_PROCESS.md#release-announcement-plan).

---

## Operator Deprecation

When an operator is deprecated:

1. The operator's docstring gains a deprecation notice:

   ```python
   class OldOperator(BaseOperator):
       """
       .. deprecated:: 1.2.0
           Use :class:`NewOperator` instead. Will be removed in v2.0.0.
       """
   ```

2. The operator emits a `DeprecationWarning` in its `__init__` or `execute` method.
3. The operator remains functional for the full deprecation window.
4. The operator reference documentation is updated.

---

## Configuration Parameter Deprecation

When a flow JSON parameter is deprecated:

1. The operator validates the old parameter name and emits a deprecation log message (`logging.warning`).
2. If the old parameter is present, the operator maps it to the new parameter for the duration of the deprecation window.
3. After removal, the operator raises a `ValueError` with a clear message pointing to the migration guide.

Example:

```python
if "old_param" in config:
    import warnings
    warnings.warn(
        "'old_param' is deprecated as of v1.2.0. Use 'new_param' instead. "
        "See docs/guides/MIGRATION_GUIDE_v1_2.md",
        DeprecationWarning,
        stacklevel=2,
    )
    config["new_param"] = config.pop("old_param")
```

---

## Python API Deprecation

When a public method signature changes incompatibly:

1. The old signature is kept and marked deprecated via `warnings.warn`.
2. The old method delegates to the new one internally.
3. After the deprecation window, the old signature is removed.

---

## Flow JSON Schema Deprecation

When a flow JSON schema field is renamed:

1. Both old and new field names are accepted during the deprecation window.
2. The operator logs a warning when the old name is detected.
3. Documentation and examples are updated to use the new name immediately.
4. The migration guide includes a `sed` / `jq` one-liner to update existing flow files.

---

## Experimental Features

Features marked `experimental` in documentation are **excluded** from this deprecation policy. They may change or be removed in any MINOR or PATCH release without a deprecation period. Users of experimental features must monitor the CHANGELOG closely.

Experimental features are identified by:

- A `[EXPERIMENTAL]` tag in the documentation
- A `DeprecationWarning` or `UserWarning` emitted at runtime noting the experimental status
