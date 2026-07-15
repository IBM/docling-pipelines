## Documentation Changes

When code changes affect the project, update all impacted docs in the same commit.

### File locations

| Type | Location |
|---|---|
| Operator user guide | `docs/operators/<category>/<operator_name>_readme.md` |
| Operator parameter reference | `docs/reference/OPERATORS.md` |
| How-to guides | `docs/guides/<GUIDE_NAME>.md` |
| Integration docs | `docs/integrations/<name>/` |
| Architecture notes (maintainers only) | `docs/internals/` |
| Style rules | `docs/guides/DOCUMENTATION_STYLE_GUIDE.md` |

### Change impact matrix

| Change type | Files to update |
|---|---|
| New operator | `docs/operators/<category>/<name>_readme.md` (create), `docs/reference/OPERATORS.md`, `README.md` (if user-facing) |
| Operator modified | `docs/operators/<category>/<name>_readme.md`, `docs/reference/OPERATORS.md` |
| Architecture change | `ARCHITECTURE.md`, `README.md` (if user-facing) |
| Installation/setup change | `USER_GUIDE_PIPELINE_SETUP.md`, `QUICKSTART.md`, `README.md` |
| New external integration | `README.md`, `USER_GUIDE_PIPELINE_SETUP.md`, `ARCHITECTURE.md`, `TROUBLESHOOTING.md`, `docs/integrations/<name>/` |
| Flow structure / global_config change | `docs/reference/GLOBAL_CONFIG.md`, `docs/guides/FLOW_CONFIGURATION_GUIDE.md`, `USER_GUIDE_PIPELINE_SETUP.md` |
| Development process change | `CONTRIBUTING.md` |
| New known issue/fix | `TROUBLESHOOTING.md` |

### Rules
- No timestamps or changelogs in documentation files — use `CHANGELOG.md` only
- Verify accuracy — do not document assumed behaviour
- Keep operator names, parameters, and paths consistent across all files
- Operator READMEs follow the 8-section template — see `docs/guides/DOCUMENTATION_STYLE_GUIDE.md`
- Do not create `<name>_config.md` alongside operator READMEs — all content in one file
- New docs must be linked from at least one parent file (`docs/README.md` or a parent `README.md`)
- File naming: `UPPER_SNAKE_CASE.md` everywhere; exception is operator readmes (`<name>_readme.md` lowercase under `docs/operators/<category>/`)
