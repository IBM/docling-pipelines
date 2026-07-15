# Git Command Policy Rules

## Command Restrictions

### Blocked Git Flags
- **NEVER** execute `git commit` with the `--no-verify` flag
- **NEVER** execute `git push` with the `--no-verify` or `--force` flags (including `--force-with-lease`)
- **ALWAYS** validate that commits go through pre-commit hooks
- This applies to **ALL** git operations, whether initiated by the user OR by Bob (the AI assistant)
- This restriction applies to **ALL** scenarios including:
  - Initial push attempts
  - Re-execution of push commands
  - New tasks or workflows
  - Emergency situations
  - Any other circumstance - **NO EXCEPTIONS**

### Before Executing Git Commands
1. Check if the command contains `--no-verify` or `--force`
2. If found, REFUSE to execute and explain why it's blocked
3. Suggest the correct command without the blocked flag
4. Inform the user about the policy

### Enforcement
When the user requests a git command with `--no-verify`:
- Do NOT execute the command
- Respond with: "This command is blocked by project policy. The `--no-verify` flag bypasses important pre-commit hooks and quality checks."
- Suggest the alternative: "Please run the command without `--no-verify` to ensure all validations pass."

**Bob's Commitment Behavior:**
- When Bob commits code, it will ALWAYS use: `git commit -m "message"`
- Bob will NEVER use: `git commit --no-verify -m "message"`
- This ensures all pre-commit hooks run for code quality, security, and formatting validation.

### No Exceptions Allowed
- There are **NO EXCEPTIONS** to this policy.
- Even if the user explicitly requests to bypass with `--no-verify`, the command **MUST BE REFUSED**
- This is a hard enforcement to maintain code quality and security standards.
- Users cannot override this policy through Bob's IDE.

## Pre-Commit Hook Verification Policy

### Before Pushing Code
When a user requests to push code to a remote repository, Bob MUST follow this workflow:

1. **Offer Verification Options:**
   Bob should present the user with three options:
   - Option A: Run pre-commit hooks automatically (`pre-commit run`)
   - Option B: Run a specific hook (e.g., `pre-commit run detect-secrets`)
   - Option C: Provide a screenshot showing pre-commit hook execution

2. **Execute Pre-Commit Hooks (Options A or B):**
   - If user chooses Option A or B, Bob will execute the pre-commit command
   - Bob will analyze the output to determine if all hooks passed
   - **Decision Criteria:**
     - If ALL hooks pass: Proceed with `git push`
     - If ANY hook fails: REFUSE to push and explain which hooks failed
   - Bob does NOT make any file changes or stage files based on hook output
   - Bob only uses the output to decide whether to allow the push

3. **Screenshot Verification (Option C):**
   - User provides a screenshot showing pre-commit hook execution
   - Screenshot MUST show:
     - Pre-commit hook execution
     - Hook names matching `.pre-commit-config.yaml` (ruff-format, ruff, mypy, detect-secrets, etc.)
     - Success indicators: "Passed", "✓", or successful completion messages
     - No hooks were skipped or failed
     - No error messages present
   - **Acceptable Verification**: While all hooks should be executed, showing that the `detect-secrets` hook passed is sufficient verification for push approval

4. **Refuse Push on Failure:**
   - If pre-commit hooks fail (via execution or screenshot shows failures), REFUSE to execute `git push`
   - Explain which hooks failed and what needs to be fixed
   - Do NOT accept verbal acknowledgments or confirmations
   - Do NOT provide options to skip verification
   - **NEVER** suggest skipping pre-commit hooks or bypassing verification in any circumstance
   - There are **NO EXCEPTIONS** to this verification requirement

### Workflow Examples

**Option A: Automatic Pre-Commit Execution**
```
User: "Push my changes to remote"
Bob: "Before pushing, I can verify pre-commit hooks. Choose an option:
      A) Run all pre-commit hooks
      B) Run detect-secrets hook only
      C) Provide a screenshot of hook execution"

User: "Run all hooks"
Bob: [Executes: pre-commit run]
Bob: [Analyzes output] "All pre-commit hooks passed. Proceeding with push."
[Executes: git push origin branch-name]
```

**Option B: Specific Hook Execution**
```
User: "Push my changes to remote"
Bob: "Before pushing, I can verify pre-commit hooks. Choose an option:
      A) Run all pre-commit hooks
      B) Run detect-secrets hook only
      C) Provide a screenshot of hook execution"

User: "Run detect-secrets only"
Bob: [Executes: pre-commit run detect-secrets]
Bob: [Analyzes output] "detect-secrets hook passed. Proceeding with push."
[Executes: git push origin branch-name]
```

**Option C: Screenshot Verification**
```
User: "Push my changes to remote"
Bob: "Before pushing, I can verify pre-commit hooks. Choose an option:
      A) Run all pre-commit hooks
      B) Run detect-secrets hook only
      C) Provide a screenshot of hook execution"

User: "I'll provide a screenshot"
Bob: "Please provide a screenshot showing that pre-commit hooks passed."
User: [Provides screenshot showing all hooks passed]
Bob: [Verifies screenshot shows hooks passed] "Pre-commit hooks verified from screenshot. Proceeding with push."
[Executes: git push origin branch-name]
```

**Failure Scenario**
```
User: "Push my changes to remote"
Bob: [Executes: pre-commit run]
Bob: "Pre-commit hooks failed:
      - ruff: 32 errors remaining
      - mypy: 11 type checking errors
      - detect-secrets: Found potential secrets

      Cannot push until these issues are resolved. Please fix the errors and try again."
```

### Enforcement Rules
- **NEVER** execute `git push` without first verifying pre-commit hooks (via execution or screenshot)
- This applies to ALL push operations, regardless of branch or urgency
- Bob does NOT modify files or stage changes based on pre-commit output
- Bob ONLY uses pre-commit output to decide whether to allow the push
- If user insists on pushing without verification, explain the policy and refuse
- This is a strict enforcement to ensure code quality standards are met

## Pull Request Template Policy

### Template Usage Requirements
- **ALWAYS** check for the existence of `.github/pull_request_template.md`
- If `.github/pull_request_template.md` exists, it **MUST** be used as the body template for all GitHub PRs
- **NEVER** bypass or ignore the pull request template if it exists
- The template ensures consistency, completeness, and adherence to project standards

### PR Creation Workflow
When creating a pull request:

1. **Check for Template:**
   - Look for `.github/pull_request_template.md`
   - If found, read its contents

2. **Use Template:**
   - If template exists: Use it as the base for the PR body
   - Fill in all applicable sections from the template
   - Remove only sections explicitly marked as optional or not applicable
   - **NEVER** remove the PR Checklist section - it is mandatory

3. **Template Not Found:**
   - If no template exists, create a comprehensive PR body with:
     - Issue reference/link
     - Description of changes
     - Testing details
     - Breaking changes (if any)
     - Screenshots/visuals (if applicable)

4. **Required Template Sections:**
   - Issue reference
   - PR Checklist (mandatory - never remove)
   - Description
   - Testing Details
   - Screenshots/Visuals (if applicable)
   - Notes (if applicable)

### Template Enforcement
- Do NOT create PRs without checking for the template first
- Do NOT create custom PR bodies when a template exists
- Do NOT skip or abbreviate template sections unless explicitly marked optional
- Ensure all checklist items are included in the PR body

## Rationale

### Pre-commit Hooks
Pre-commit hooks enforce code quality, security checks, and formatting standards. Bypassing them can introduce bugs, security vulnerabilities, or inconsistent code into the repository.

### PR Templates
Pull request templates ensure:
- Consistent PR structure across the project
- All necessary information is provided for reviewers
- Quality gates and checklists are followed
- Documentation and testing requirements are met
- Project-specific guidelines are adhered to
