# Git Command Policy Rules

## Command Restrictions

### Blocked Git Flags
- **NEVER** execute `git commit` with the `--no-verify` flag
- **NEVER** execute `git push` with the `--no-verify` or `--force` flags
- **ALWAYS** validate that commits go through pre-commit hooks
- This applies to **ALL** git operations, whether initiated by the user OR by Bob (the AI assistant)

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
- This ensures all pre-commit hooks run for code quality, security, and formatting validation

### No Exceptions Allowed
- There are **NO EXCEPTIONS** to this policy
- Even if the user explicitly requests to bypass with `--no-verify`, the command **MUST BE REFUSED**
- This is a hard enforcement to maintain code quality and security standards
- Users cannot override this policy through Bob's IDE

## Pull Request Template Policy

### Template Usage Requirements
- **ALWAYS** check for the existence of `pull_request_template.md` in the project root
- If `pull_request_template.md` exists, it **MUST** be used as the body template for all GitHub PRs
- **NEVER** bypass or ignore the pull request template if it exists
- The template ensures consistency, completeness, and adherence to project standards

### PR Creation Workflow
When creating a pull request:

1. **Check for Template:**
   - Look for `pull_request_template.md` in the project root
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
