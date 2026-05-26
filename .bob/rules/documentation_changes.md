## Documentation Changes

### Overview
Whenever changes are made to the project that affect documentation, ensure all relevant documentation files are updated to maintain consistency and accuracy.

### Core Documentation Files to Track

#### 1. **README.md**
**Update When:**
- Adding new features or operators
- Changing project structure or organization
- Modifying setup requirements or prerequisites
- Adding new integrations (Ollama, OpenSearch, etc.)
- Changing installation steps
- Updating project goals or scope

**Examples:**
- New operator category added → Update operator list in README
- New external service integration → Add to prerequisites section
- Project structure reorganization → Update directory structure documentation

#### 2. **ARCHITECTURE.md**
**Update When:**
- Modifying system architecture or design patterns
- Adding, removing, or modifying operators
- Changing data flow or pipeline execution model
- Updating orchestration layer (Prefect configuration)
- Modifying operator categories or organization
- Changing PyArrow table schema or data structures
- Adding new architectural components or layers

**Examples:**
- New operator added → Document in operator catalog with parameters
- Data flow changes → Update architecture diagrams and descriptions
- New operator category → Add to OperatorCategory enum documentation

#### 3. **CONTRIBUTING.md**
**Update When:**
- Changing development workflow or processes
- Modifying code standards or style guidelines
- Updating PR review process or requirements
- Changing testing requirements or procedures
- Adding new development tools or dependencies
- Modifying branch naming conventions
- Updating commit message guidelines

**Examples:**
- New linting rules → Update code standards section
- Changed PR template → Document new requirements
- New testing framework → Update testing guidelines

#### 4. **USER_GUIDE_PIPELINE_SETUP.md**
**Update When:**
- Changing installation steps or prerequisites
- Modifying pipeline execution process
- Updating environment setup (Python version, uv, dependencies)
- Changing Ollama or OpenSearch setup instructions
- Modifying flow configuration structure
- Adding new operator examples
- Updating verification or testing procedures

**Examples:**
- Python version requirement changed → Update prerequisites section
- New environment variable required → Add to setup instructions
- Flow JSON structure modified → Update configuration examples

#### 5. **QUICKSTART.md**
**Update When:**
- Changing quick start steps or initial setup
- Modifying minimal working example
- Updating first-time user experience
- Changing default configurations
- Simplifying or streamlining onboarding process

**Examples:**
- Simplified installation process → Update quick start steps
- New default flow example → Replace existing example
- Changed CLI commands → Update command examples

#### 6. **OPERATOR_REFERENCE.md**
**Update When:**
- Adding new operators to any category
- Modifying operator parameters or configurations
- Changing operator behavior or functionality
- Updating operator input/output specifications
- Adding operator usage examples
- Deprecating or removing operators
- Changing operator naming conventions

**Examples:**
- New ExtractOperator added → Add to Extract category with full parameter documentation
- Operator parameter renamed → Update all references and examples
- New operator category → Add new section with operators

#### 7. **TROUBLESHOOTING.md**
**Update When:**
- Discovering new common issues or errors
- Finding solutions to recurring problems
- Identifying integration-specific issues (Ollama, OpenSearch)
- Documenting workarounds for known limitations
- Adding debugging tips or techniques
- Resolving environment-specific problems

**Examples:**
- Ollama connection failures → Add troubleshooting section with solutions
- Common flow validation errors → Document error messages and fixes
- Performance issues → Add optimization tips

#### 8. **docs/operators/**
**Update When:**
- Adding new operators
- Modifying operator parameters or behavior
- Changing operator configuration options
- Adding new provider support (for operators like ExtractOperator, DocumentClassifier)
- Updating operator usage examples

**Examples:**
- New operator added → Create new markdown file in docs/operators/
- Operator parameters changed → Update parameter tables and examples
- New provider added → Document provider configuration and examples

### Documentation Update Rules

1. **No Timestamps or Changelogs**
   - Do not add "updated on" dates or timestamps to documentation files
   - Do not maintain inline changelogs within documentation
   - Keep documentation focused on current state, not historical changes

2. **Verification Required**
   - Verify all changes before adding to documentation
   - Do not hallucinate or assume functionality
   - Test examples and code snippets before documenting
   - Ensure accuracy of technical details and parameters

3. **Consistency Across Files**
   - Maintain consistent terminology across all documentation
   - Use the same examples and naming conventions
   - Cross-reference related sections in different files
   - Keep operator names and parameters synchronized

4. **Completeness**
   - Update all affected documentation files in a single change
   - Do not leave documentation partially updated
   - Include examples where appropriate
   - Document both what changed and why (in context)

5. **Clarity and Precision**
   - Be specific about what you are adding or changing
   - Avoid vague or ambiguous language
   - Provide concrete examples for complex concepts
   - Ensure documentation does not mislead users

### Change Impact Matrix

| Change Type | Files to Update |
|-------------|----------------|
| New Operator | ARCHITECTURE.md, OPERATOR_REFERENCE.md, docs/operators/, README.md (if significant) |
| Architecture Change | ARCHITECTURE.md, README.md (if user-facing) |
| Installation Change | USER_GUIDE_PIPELINE_SETUP.md, QUICKSTART.md, README.md |
| New Integration | README.md, USER_GUIDE_PIPELINE_SETUP.md, ARCHITECTURE.md, TROUBLESHOOTING.md |
| Flow Structure Change | USER_GUIDE_PIPELINE_SETUP.md, ARCHITECTURE.md |
| Development Process | CONTRIBUTING.md |
| Common Issue Found | TROUBLESHOOTING.md |
| Quick Start Change | QUICKSTART.md, README.md (if affects overview) |

### Workflow

When making changes that affect documentation:

1. **Identify Impact**: Determine which documentation files are affected
2. **Read Current State**: Review existing documentation before making changes
3. **Update All Files**: Make changes to all affected files in a single operation
4. **Verify Accuracy**: Ensure all technical details are correct
5. **Check Consistency**: Verify terminology and examples are consistent across files
6. **Test Examples**: If adding code examples, verify they work
7. **Review Cross-References**: Update any cross-references between documentation files