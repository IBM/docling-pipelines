#!/usr/bin/env python3
"""
Script to fix pyproject.toml for the reorganized src/datasift structure.

This script:
1. Adds version constraint to docling[vlm]
2. Removes duplicate pytest-asyncio dependency
3. Fixes case inconsistency for o365 package
4. Updates script entry points from datasift_opensource to datasift
5. Updates hatch build configuration for new structure
6. Removes obsolete force-include section
7. Updates ruff isort known-first-party configuration
"""

import re
import sys
from pathlib import Path


def fix_pyproject_toml(*, file_path: Path) -> bool:
    """
    Fix pyproject.toml for the reorganized structure.
    
    Args:
        file_path: Path to pyproject.toml file
        
    Returns:
        True if changes were made, False otherwise
    """
    if not file_path.exists():
        print(f"Error: {file_path} not found")
        return False
    
    content = file_path.read_text()
    original_content = content
    
    # 1. Add version constraint to docling[vlm]
    content = re.sub(
        r'"docling\[vlm\]",',
        '"docling[vlm]>=2.0.0",',
        content
    )
    
    # 2. Remove duplicate pytest-asyncio (keep the one with >=0.23.0)
    content = re.sub(
        r'(\s+"pytest-asyncio>=0\.23\.0",\s+.*?\s+.*?\s+)"pytest-asyncio>=0\.21\.0",\s+',
        r'\1',
        content,
        flags=re.DOTALL
    )
    
    # 3. Fix O365 case inconsistency
    content = re.sub(
        r'"O365==2\.1\.9"',
        '"o365==2.1.9"',
        content
    )
    
    # 4. Update script entry points
    content = re.sub(
        r'datasift-api = "datasift_opensource\.app\.main:app"',
        'datasift-api = "datasift.api.main:app"',
        content
    )
    content = re.sub(
        r'datasift-orchestrator = "datasift_opensource\.cli\.datasift_cli:main"',
        'datasift-orchestrator = "datasift.cli.datasift_cli:main"',
        content
    )
    
    # 5. Update hatch build packages
    content = re.sub(
        r'packages = \["common", "core", "app", "cli", "lib"\]',
        'packages = ["src/datasift"]',
        content
    )
    
    # 6. Remove force-include section
    force_include_pattern = r'\[tool\.hatch\.build\.targets\.wheel\.force-include\]\s+.*?(?=\n\[|\Z)'
    content = re.sub(
        force_include_pattern,
        '',
        content,
        flags=re.DOTALL
    )
    
    # 7. Update ruff isort known-first-party
    content = re.sub(
        r'known-first-party = \["datasift_opensource"\]',
        'known-first-party = ["datasift"]',
        content
    )
    
    # Write back if changes were made
    if content != original_content:
        file_path.write_text(content)
        print(f"Successfully updated {file_path}")
        print("\nChanges made:")
        print("1. Added version constraint to docling[vlm]>=2.0.0")
        print("2. Removed duplicate pytest-asyncio dependency")
        print("3. Fixed O365 → o365 case inconsistency")
        print("4. Updated script entry points to datasift.*")
        print("5. Updated packages to ['src/datasift']")
        print("6. Removed obsolete force-include section")
        print("7. Updated known-first-party to ['datasift']")
        return True
    else:
        print(f"No changes needed for {file_path}")
        return False


def main() -> int:
    """Main entry point."""
    # Find pyproject.toml in repository root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    pyproject_path = repo_root / "pyproject.toml"
    
    print(f"Fixing {pyproject_path}...")
    success = fix_pyproject_toml(file_path=pyproject_path)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
