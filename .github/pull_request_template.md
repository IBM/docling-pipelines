<!--
Note -
1. PR title must follow Conventional Commits: https://www.conventionalcommits.org/en/v1.0.0/#summary
   Format: <type>[optional scope][optional !]: <description>
   Types: fix | feat | docs | style | refactor | perf | test | build | ci | chore | revert
   Example: feat(chunker): add sliding window chunking strategy
   Append ! before the colon for breaking changes: feat(api)!: remove deprecated endpoint
2. Tag the issue this PR resolves (or remove the Issue section if there is none)
3. Headings that are not applicable to the PR can be removed from the below template
-->

## Issue
<!-- Tag the issue this PR resolves, or remove this section if there is none -->
Resolves #

## Dev Tracking
<!-- Link to epic or parent task if this PR is part of a larger feature/epic -->
<!-- Example: Part of Epic #123 or Subtask of #456 -->

## Description
<!-- Concise Summary of the PR -->

## Basic Checklist
- [ ] Code follows project standards (keyword-only arguments, no unicode in logging)
- [ ] Tests added/updated for new functionality
- [ ] Documentation updated (see Documentation Update Checklist below)
- [ ] No breaking changes (or documented in Breaking Changes section)

## Breaking Changes
<!-- List any breaking changes introduced by this PR -->
<!-- If none, write "None" -->

## Dependencies
<!-- List any new dependencies added or version updates -->
<!-- Include package name, version, and reason for addition/update -->
<!-- If none, write "None" -->

## Testing Details
<!-- Details about how the changes were tested -->
<!-- Include test commands, test files, or manual testing steps -->

## Documentation Update Checklist
<!-- Check all documentation files that were updated or reviewed for this PR -->
- [ ] README.md (if adding features, changing structure, or modifying setup)
- [ ] ARCHITECTURE.md (if modifying operators, data flow, or system design)
- [ ] CONTRIBUTING.md (if changing development workflow or code standards)
- [ ] USER_GUIDE_PIPELINE_SETUP.md (if changing installation, setup, or execution)
- [ ] QUICKSTART.md (if changing quick start steps or examples)
- [ ] OPERATOR_REFERENCE.md (if adding/modifying operators)
- [ ] TROUBLESHOOTING.md (if discovering new issues or solutions)
- [ ] Operator documentation in docs/operators/ (if operator added/modified)
- [ ] N/A - No documentation updates needed

## Screenshots/Videos
<!-- For UI changes, include screenshots or videos demonstrating the changes -->
<!-- If not applicable, remove this section -->

### Pre-Commit Hook Results
<!-- Paste the output of pre-commit hooks execution to verify all checks passed -->


### Note
 1. **Keyword Arguments** - Ensure function arguments are keyword-based, not positional - [Link](https://docs.python.org/3/glossary.html#term-argument)
 2. **Metadata Independence:** When adding or modifying operator metadata, ensure the data does not depend on instance variables.
 3. **Method Requirements:** Ensure `get_metadata` is a static method. If `get_required_features` depends on instance variables, the operator must implement `get_static_required_features` using the default values referenced in `get_required_features`
 4. For every PR, ensure that the pre-commit hook output has been included.