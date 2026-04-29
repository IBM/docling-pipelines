# Repository Reorganization Scripts

This directory contains scripts for reorganizing the datasift-opensource repository structure.

## Scripts Overview

### 1. reorganize_repository.py

Main script that reorganizes the repository structure from the nested `src/datasift_opensource/backend/` to a cleaner `src/datasift/` structure.

**Features:**
- ✅ Structure validation before execution
- ✅ Automatic backup creation
- ✅ Safe file moving with error handling
- ✅ Creates missing standard files (LICENSE, CHANGELOG.md, CODE_OF_CONDUCT.md)
- ✅ Rollback capability

**Usage:**
```bash
# Back up the existing code. Optional, if not backing up, then run "git reset --hard" to revert the changes
python scripts/reorganize_repository.py --backup

# Preview changes without executing
python scripts/reorganize_repository.py --dry-run

# Execute the reorganization
python scripts/reorganize_repository.py --execute

# Rollback to backup if needed
python scripts/reorganize_repository.py --rollback
```

### 2. update_imports.py

Updates import statements throughout the codebase after reorganization.

**Features:**
- ✅ Scans all Python files in src/, tests/, examples/, scripts/
- ✅ Updates import paths automatically
- ✅ Preview mode to see changes before applying
- ✅ Handles multiple import patterns

**Usage:**
```bash
# Preview import changes
python scripts/update_imports.py --dry-run

# Execute import updates
python scripts/update_imports.py --execute
```

## Quick Start

Follow these steps in order:

```bash
# 1. Preview the reorganization
python scripts/reorganize_repository.py --dry-run

# 2. Back up the existing code (optional)
python scripts/reorganize_repository.py --backup

# 3. Execute reorganization (creates backup automatically)
python scripts/reorganize_repository.py --execute

# 4. Preview import updates
python scripts/update_imports.py --dry-run

# 5. Execute import updates
python scripts/update_imports.py --execute

# 6. fix the pyproject.toml file
python scripts/fix_pyproject_toml.py

# 7. Verify changes with unit tests (from project root)
source .venv/bin/activate
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
uv run pytest tests/unit -v

# 8. Verify changes with integration tests (from project root)
uv run pytest tests/integration -v

# 9. Preview the document updation
python scripts/update_documentation.py --dry-run

# 10. Finally update the documentation
python scripts/update_documentation.py --execute
```

## Safety Features

Both scripts include safety features:

1. **Dry-run mode**: Preview all changes before execution
2. **Backups**: Optionally create backups in, if required `.reorganization_backup/`
3. **Rollback capability**: Can restore from backup if needed
4. **Validation**: Checks structure before making changes
5. **Error handling**: Continues on non-critical errors, reports issues

## What Gets Changed

### File Structure Changes

**Before:**
```
src/datasift_opensource/backend/
├── app/            → src/datasift/api/
├── cli/            → src/datasift/cli/
├── common/
│   ├── clients/    → src/datasift/integrations/
│   ├── util/       → src/datasift/utils/
│   ├── constants/  → src/datasift/core/constants/
│   └── exceptions/ → src/datasift/exceptions/
└── core/
    ├── operators/         → src/datasift/core/operators/
    ├── orchestrator/      → src/datasift/core/orchestration/
    └── assets_management/ → src/datasift/core/flows/
```

**After:**
```
src/datasift/
├── api/              # FastAPI application
├── cli/              # CLI commands
├── core/             # Core business logic
│   ├── operators/
│   ├── orchestration/
│   ├── flows/
│   ├── constants/
│   └── models/
├── integrations/     # External services
│   ├── ollama/
│   ├── opensearch/
│   ├── docling/
│   └── cloud/
├── utils/            # Shared utilities
└── exceptions.py
```

### Import Changes

**Before:**
```python
from datasift_opensource.backend.core.operators import ExtractOperator
from datasift_opensource.backend.app.routes import flows
from datasift_opensource.backend.common.clients.ollama_client import OllamaClient
```

**After:**
```python
from datasift.core.operators import ExtractOperator
from datasift.api.routes import flows
from datasift.integrations.ollama import OllamaClient
```

## Backup and Recovery

### Backup Location

Backups are stored in `.reorganization_backup/` with a manifest file tracking all changes.

### Rollback Process

If something goes wrong:

```bash
# Option 1: Use the rollback script
python scripts/reorganize_repository.py --rollback

# Option 2: Use git (if you created a backup branch)
git checkout backup-pre-reorganization
```

### Manual Recovery

If scripts fail, you can manually restore from backup:

```bash
# Remove new structure
rm -rf src/datasift

# Restore from backup
cp -r .reorganization_backup/src/datasift_opensource src/
```

## Troubleshooting

### Script Fails During Execution

1. Check the error message for specific issues
2. Verify you have write permissions
3. Ensure no files are locked or in use
4. Use rollback to restore: `python scripts/reorganize_repository.py --rollback`

### Import Errors After Update

1. Verify all imports were updated: `python scripts/update_imports.py --dry-run`
2. Check for manual import fixes needed
3. Ensure `__init__.py` files exist in all directories
4. Reinstall package from project root: `uv sync --extra dev`

### Tests Failing

1. Check PYTHONPATH is set correctly
2. Verify virtual environment is activated
3. Review git diff for unexpected changes
4. Run specific failing tests with `-v` flag for details

## Best Practices

1. **Always run dry-run first**: Preview changes before executing
2. **Commit before reorganizing**: Ensure clean git state
3. **Create backup branch**: `git checkout -b backup-pre-reorganization`
4. **Test thoroughly**: Run full test suite after changes
5. **Keep backup**: Don't delete `.reorganization_backup/` until verified

## Additional Resources

- **[Architecture Documentation](../ARCHITECTURE.md)**: Understanding the new structure
- **[Contributing Guide](../CONTRIBUTING.md)**: Development workflow

## Support

For issues or questions:
1. Review script output for error messages
2. Check git history: `git log --oneline`
3. Create an issue with details

---

**Note**: These scripts make significant structural changes. Always backup your work and test thoroughly after execution.