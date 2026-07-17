# Git Policy

## Blocked Flags

Never use `--no-verify` on `git commit` or `--no-verify` / `--force` on `git push`.
Refuse if the user requests them and suggest the command without the flag.

---

## Pre-Commit Hooks

Run hooks on **changed files only** by default — never `--all-files` unless explicitly requested.

```bash
git diff --name-only <base>...HEAD                      # get changed files
pre-commit run --files <file1> <file2> ...              # run hooks on them
```

`detect-secrets` passing is the minimum acceptable bar for push approval.
If any hook fails, refuse to push and report which hooks failed.
Do not stage or modify files based on hook output.

---

## Pull Requests

### Step 1 — Infer the base branch automatically

Before presenting any options, Bob MUST attempt to determine the base branch using the following signals in priority order. Stop at the first high-confidence result.

| Priority | Command | Use result when |
|---|---|---|
| 1 | `GH_HOST=<host> gh api /repos/<owner>/<repo> --jq '.default_branch'` | API returns a value — this is the repo default branch |
| 2 | `git merge-base --is-ancestor origin/<candidate> HEAD` | Candidate is an ancestor AND matches the API default |
| 3 | `git log --oneline origin/<candidate>...HEAD` | Low commit count (≤ 20) against the candidate |
| 4 | Branch name convention | `fix/*`, `feat/*`, `chore/*` → default branch; `fix/*-main`, `hotfix/*-release` → named branch |

**Auto-select (no user input)** when signals 1 + 2 agree — which covers the vast majority of PRs.

**Ask the user** only when:
- The API call fails or the repo has no default branch set
- Two or more candidate branches are equally close ancestors (e.g. `main` and `release/1.x` both have low commit counts)
- The branch name contains an explicit target hint that contradicts the API default

### Step 2 — Ask the user which option they want

Present these options **after** the base branch is known (auto-inferred or asked):

```
How would you like to proceed?

[Default] Base branch: <inferred> | Hooks: all hooks on changed files only
       A  Override base branch    | Hooks: all hooks on changed files only
       B  Override base branch    | Hooks: detect-secrets only on changed files
       C  Override base branch    | Hooks: all hooks on ALL files
       D  Override base branch    | Hooks: provide a screenshot instead
```

- **Default** — proceed immediately with the inferred branch and all hooks on changed files. No further questions.
- **A–D** — ask for the base branch override, then proceed as described.

### Step 3 — Show a pre-flight summary

Before running any commands, show a summary using live values and ask for confirmation:

```
PR Pre-flight Summary
─────────────────────────────────────────────
Base branch  : <inferred-or-overridden>
Hook scope   : <chosen scope>
Template     : <path or "none found">

Changed files (vs <base>):
  <file>   +<added> / -<removed>
  ...
─────────────────────────────────────────────
Proceed? (yes / no)
```

Only proceed after explicit confirmation.

### Step 4 — Run pre-commit hooks

Run the chosen hook scope. If hooks fail, stop and report failures — do not create the PR.

### Step 5 — Create the PR

Check for `.github/pull_request_template.md`. If it exists, populate every section — never remove the checklist.
Create the PR against the confirmed base branch.

```bash
gh pr create --base <confirmed-base> --title "..." --body "..."
```
