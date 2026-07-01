# Release Process

This document describes the end-to-end release process for `docling-pipelines`, covering versioning strategy, release notes, migration guides, deprecation policy, and the release announcement plan.

---

## Table of Contents

- [Versioning Strategy](#versioning-strategy)
- [Release Cadence](#release-cadence)
- [Release Checklist](#release-checklist)
- [Step-by-Step Release Process](#step-by-step-release-process)
- [Release Notes](#release-notes)
- [Migration Guides](#migration-guides)
- [Release Announcement Plan](#release-announcement-plan)
- [Deprecation Policy](#deprecation-policy)

---

## Versioning Strategy

`docling-pipelines` follows [Semantic Versioning 2.0.0](https://semver.org/) (`MAJOR.MINOR.PATCH`).

| Component | When to increment | Example |
|-----------|------------------|---------|
| **MAJOR** | Incompatible API changes that break existing flows or operator contracts | `0.x.x` → `1.0.0` |
| **MINOR** | New backwards-compatible functionality (new operators, new parameters with defaults) | `1.0.0` → `1.1.0` |
| **PATCH** | Backwards-compatible bug fixes, documentation corrections, dependency patches | `1.0.0` → `1.0.1` |

### Pre-release Identifiers

Pre-release versions use the format `MAJOR.MINOR.PATCH-{qualifier}.N`:

| Qualifier | Purpose | Example |
|-----------|---------|---------|
| `alpha` | Early feature preview, may be unstable | `1.0.0-alpha.1` |
| `beta` | Feature-complete, stabilisation in progress | `1.0.0-beta.1` |
| `rc` | Release candidate, no planned changes | `1.0.0-rc.1` |

### Version Source of Truth

The authoritative version is defined in [`pyproject.toml`](pyproject.toml) under `[project].version`. All tags and distribution artifacts derive their version from this value.

### Version Tagging

Git tags use the prefix `v`, e.g. `v1.2.3`. Tags are immutable: once a tag is pushed, it is never deleted or moved. If an artifact at a given version is found to be broken, a new patch version is released.

---

## Release Cadence

| Release type | Approximate frequency |
|---|---|
| PATCH | As needed for bug or security fixes |
| MINOR | Monthly, aligned with sprint boundaries |
| MAJOR | When breaking changes are unavoidable, announced at least 4 weeks in advance |

---

## Release Checklist

Before every release, confirm all of the following:

- [ ] All planned items in the milestone are merged or explicitly deferred
- [ ] `pyproject.toml` version updated
- [ ] `CHANGELOG.md` entry written for this version
- [ ] Migration guide created (MAJOR or breaking MINOR only)
- [ ] All CI checks pass on `main`
- [ ] Static analysis (ruff, mypy, sonarqube) clean
- [ ] Mend / Whitesource OSS scan report clean
- [ ] Unit test coverage >= 80 %
- [ ] Integration tests pass
- [ ] `detect-secrets` pre-commit hook passes
- [ ] Release notes drafted and reviewed by at least one maintainer
- [ ] Announcement text prepared (see [Release Announcement Plan](#release-announcement-plan))
- [ ] PyPI distribution artifact built and verified
- [ ] Git tag pushed

---

## Step-by-Step Release Process

### 1. Prepare the release branch

For MAJOR or MINOR releases, create a dedicated release branch from `main`:

```bash
git checkout main
git pull origin main
git checkout -b release/vX.Y.Z
```

For PATCH releases, cherry-pick fixes onto the existing release branch or work directly on `main`.

### 2. Update the version

Edit [`pyproject.toml`](pyproject.toml):

```toml
[project]
version = "X.Y.Z"
```

### 3. Update CHANGELOG.md

Add a section at the top of [`CHANGELOG.md`](CHANGELOG.md) following the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. See [Release Notes](#release-notes) for the required structure.

### 4. Write or update migration guides

If this release contains breaking changes, create `docs/guides/MIGRATION_GUIDE_vX_Y.md` following the [migration guide template](docs/guides/MIGRATION_GUIDE_TEMPLATE.md).

### 5. Open a Release PR

Open a pull request from `release/vX.Y.Z` → `main` with the title `chore(release): vX.Y.Z`. Include:

- Link to the CHANGELOG entry
- Link to any migration guides
- The release announcement draft

The PR must be reviewed and approved by at least one maintainer before merging.

### 6. Merge and tag

After the PR is approved and merged:

```bash
git checkout main
git pull origin main
git tag vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

### 7. Build and publish distribution artifacts

```bash
source .venv/bin/activate
uv build
# Verify the wheel and source distribution
twine check dist/*
# Publish to PyPI
twine upload dist/*
```

CI (GitHub Actions / Jenkins) automates steps 7 and 8 on tag push.

### 8. Create a GitHub Release

On GitHub, create a new Release from the tag `vX.Y.Z`. Paste in the CHANGELOG entry as the release body.

---

## Release Notes

Release notes are maintained in [`CHANGELOG.md`](CHANGELOG.md) at the repository root, following the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

### Entry structure

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- Short description of new feature (#issue-number)

### Changed
- Short description of changed behaviour (#issue-number)

### Deprecated
- Short description of what is deprecated and the planned removal version

### Removed
- Short description of removed features

### Fixed
- Short description of bug fix (#issue-number)

### Security
- Short description of security fix (CVE-YYYY-XXXXX if applicable)
```

### Guidelines

- Every user-visible change must appear in the CHANGELOG.
- Reference the GitHub issue or PR number.
- Use present tense ("Add support for …" not "Added support for …").
- Do not include internal refactors, test changes, or CI changes unless they affect end-users.

---

## Migration Guides

A migration guide is required for every release that introduces breaking changes (MAJOR version bumps and any MINOR change that removes or renames a public API).

Migration guides live at `docs/guides/MIGRATION_GUIDE_vX_Y.md` where `X_Y` corresponds to the target MAJOR.MINOR version.

A template is available at [`docs/guides/MIGRATION_GUIDE_TEMPLATE.md`](docs/guides/MIGRATION_GUIDE_TEMPLATE.md).

Each guide must include:

- Summary of breaking changes
- Before / after code examples for every breaking change
- Step-by-step upgrade instructions
- Automated migration script path (if one exists under `scripts/`)
- Known limitations or caveats

---

## Release Announcement Plan

### Channels and timing

| Channel | Audience | Timing |
|---------|---------|--------|
| GitHub Release notes | Public — GitHub users and watchers | At tag push |
| GitHub Discussions (Announcements category) | Public — community | Same day as release |
| PyPI release page | Public — pip users | Automated on publish |

### Announcement content

Each announcement must include:

- Version number and release date
- One-sentence summary of what changed
- Link to the GitHub Release (full CHANGELOG entry)
- Link to migration guide (if applicable)
- Link to the PyPI package page
- Call to action: "Try it with `pip install docling-pipelines==X.Y.Z`"

### Major release announcements

For MAJOR releases, a blog post or extended write-up should be prepared at least one week before release, covering:

- Motivation for the breaking changes
- New capabilities introduced
- Upgrade path summary
- Roadmap for the next cycle

---

## Deprecation Policy

See the full [Deprecation Policy](docs/guides/DEPRECATION_POLICY.md) for details.

### Summary

1. **Deprecation notice** — A feature is marked deprecated in the same release where the replacement is introduced. Deprecation is announced in the CHANGELOG under `### Deprecated`.
2. **Deprecation window** — Deprecated features remain functional for a minimum of **two MINOR releases** (or one MAJOR release cycle, whichever is longer).
3. **Removal** — The feature is removed in the next MAJOR version after the deprecation window has elapsed.
4. **Emergency removal** — Security vulnerabilities may force earlier removal; affected users are notified via a security advisory.
