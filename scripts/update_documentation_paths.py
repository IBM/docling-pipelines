#!/usr/bin/env python3
"""
Documentation Path Update Script for datasift-opensource

This script updates all path references in documentation files after repository reorganization.
It handles file paths, import statements, PYTHONPATH references, and directory navigation commands.

Usage:
    python scripts/update_documentation_paths.py --dry-run  # Preview changes
    python scripts/update_documentation_paths.py --execute  # Execute updates
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class DocumentationPathUpdater:
    """Updates path references in documentation files."""

    def __init__(self, *, repo_root: Path):
        self.repo_root = repo_root
        self.path_mappings = self._get_path_mappings()
        self.changes_made = []

    def _get_path_mappings(self) -> Dict[str, str]:
        """Define mappings from old paths to new ones."""
        return {
            # File paths in documentation
            r"src/datasift_opensource/backend/": "src/datasift/",
            r"src/datasift_opensource/backend": "src/datasift",
            
            # Python import paths in code examples
            r"datasift_opensource\.backend\.core\.operators": "datasift.core.operators",
            r"datasift_opensource\.backend\.core\.orchestrator": "datasift.core.orchestration",
            r"datasift_opensource\.backend\.core\.assets_management": "datasift.core.flows",
            r"datasift_opensource\.backend\.core\.data_access": "datasift.core.data_access",
            r"datasift_opensource\.backend\.app": "datasift.api",
            r"datasift_opensource\.backend\.cli": "datasift.cli",
            r"datasift_opensource\.backend\.common\.clients": "datasift.integrations",
            r"datasift_opensource\.backend\.common\.util": "datasift.utils",
            r"datasift_opensource\.backend\.common\.constants": "datasift.core.constants",
            r"datasift_opensource\.backend\.common\.exceptions": "datasift.exceptions",
            r"datasift_opensource\.backend\.common\.models": "datasift.core.models",
            r"datasift_opensource\.backend\.common\.document_classes": "datasift.core.document_classes",
            r"datasift_opensource\.backend\.storage": "datasift.storage",
            r"datasift_opensource\.backend\.lib": "datasift.lib",
            r"datasift_opensource\.backend\.core": "datasift.core",
            r"datasift_opensource\.backend\.common": "datasift",
            r"datasift_opensource\.backend": "datasift",
            
            # PYTHONPATH environment variable references
            r'\$\(pwd\)/src/datasift_opensource/backend': "$(pwd)/src/datasift",
            r'\$\(cd \.\./\.\./\.\. && pwd\)/src/datasift_opensource/backend': "$(cd ../../.. && pwd)/src/datasift",
            r'"/app/src/datasift_opensource/backend"': '"/app/src/datasift"',
            r"'/app/src/datasift_opensource/backend'": "'/app/src/datasift'",
            r"/app/src/datasift_opensource/backend": "/app/src/datasift",
            
            # Directory navigation in bash commands
            r"cd src/datasift_opensource/backend": "cd src/datasift",
            
            # Virtual environment paths
            r"src/datasift_opensource/backend/\.venv": "src/datasift/.venv",
            r"backend/\.venv": ".venv",
            
            # Source activation commands
            r"source src/datasift_opensource/backend/\.venv/bin/activate": "source src/datasift/.venv/bin/activate",
            
            # Python version file references
            r"src/datasift_opensource/backend/\.python-version": "src/datasift/.python-version",
            
            # pyproject.toml references
            r"src/datasift_opensource/backend/pyproject\.toml": "src/datasift/pyproject.toml",
        }

    def find_documentation_files(self) -> List[Path]:
        """Find all markdown files in the repository."""
        md_files = []
        
        # Search in root directory
        md_files.extend(self.repo_root.glob("*.md"))
        
        # Search in docs directory
        docs_dir = self.repo_root / "docs"
        if docs_dir.exists():
            md_files.extend(docs_dir.rglob("*.md"))
        
        # Search in examples directory
        examples_dir = self.repo_root / "examples"
        if examples_dir.exists():
            md_files.extend(examples_dir.rglob("*.md"))
        
        # Search in tests directory
        tests_dir = self.repo_root / "tests"
        if tests_dir.exists():
            md_files.extend(tests_dir.rglob("*.md"))
        
        # Search in operator documentation
        operators_dir = self.repo_root / "src/datasift_opensource/backend/core/operators"
        if operators_dir.exists():
            md_files.extend(operators_dir.rglob("*.md"))
        
        # Search in other backend documentation
        backend_dir = self.repo_root / "src/datasift_opensource/backend"
        if backend_dir.exists():
            md_files.extend(backend_dir.rglob("*.md"))
        
        # Search in scripts directory
        scripts_dir = self.repo_root / "scripts"
        if scripts_dir.exists():
            md_files.extend(scripts_dir.glob("*.md"))
        
        return [f for f in md_files if f.is_file()]

    def update_file_paths(self, *, file_path: Path, dry_run: bool = True) -> Tuple[bool, List[str]]:
        """Update paths in a single documentation file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            original_content = content
            changes = []
            
            # Apply each mapping
            for old_pattern, new_pattern in self.path_mappings.items():
                # Find all matches for reporting
                matches = list(re.finditer(old_pattern, content))
                if matches:
                    for match in matches:
                        old_text = match.group(0)
                        new_text = re.sub(old_pattern, new_pattern, old_text)
                        if old_text != new_text:
                            changes.append(f"  {old_text} → {new_text}")
                
                # Apply the replacement
                content = re.sub(old_pattern, new_pattern, content)
            
            # Check if content changed
            if content != original_content:
                if not dry_run:
                    file_path.write_text(content, encoding="utf-8")
                return True, changes
            
            return False, []
            
        except Exception as e:
            print(f"⚠️  Error processing {file_path}: {e}")
            return False, []

    def preview_changes(self) -> None:
        """Preview all path changes without executing them."""
        print("\n📋 Preview of documentation path updates:\n")
        print("=" * 80)
        
        md_files = self.find_documentation_files()
        print(f"Found {len(md_files)} documentation files to check\n")
        
        files_with_changes = 0
        total_changes = 0
        
        for file_path in md_files:
            changed, changes = self.update_file_paths(file_path=file_path, dry_run=True)
            if changed:
                files_with_changes += 1
                total_changes += len(changes)
                rel_path = file_path.relative_to(self.repo_root)
                print(f"📄 {rel_path}")
                for change in changes[:10]:  # Limit to first 10 changes per file
                    print(change)
                if len(changes) > 10:
                    print(f"  ... and {len(changes) - 10} more changes")
                print()
        
        print("=" * 80)
        print(f"\nSummary:")
        print(f"  Files with changes: {files_with_changes}")
        print(f"  Total path updates: {total_changes}")
        print(f"\n💡 This was a dry run. Use --execute to apply changes.")

    def execute_updates(self) -> bool:
        """Execute path updates across all documentation files."""
        print("\n🚀 Executing documentation path updates...\n")
        
        md_files = self.find_documentation_files()
        print(f"Processing {len(md_files)} documentation files...\n")
        
        files_updated = 0
        total_changes = 0
        
        for file_path in md_files:
            changed, changes = self.update_file_paths(file_path=file_path, dry_run=False)
            if changed:
                files_updated += 1
                total_changes += len(changes)
                rel_path = file_path.relative_to(self.repo_root)
                print(f"✓ Updated: {rel_path} ({len(changes)} changes)")
        
        print("\n" + "=" * 80)
        print(f"\n✅ Documentation path updates completed!")
        print(f"  Files updated: {files_updated}")
        print(f"  Total changes: {total_changes}")
        
        if files_updated > 0:
            print(f"\n⚠️  IMPORTANT: Please verify the changes:")
            print("  1. Review git diff to confirm changes are correct")
            print("  2. Check that all links and references still work")
            print("  3. Verify code examples are accurate")
        
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Update path references in documentation after repository reorganization"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without executing them"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the path updates"
    )
    
    args = parser.parse_args()
    
    # Determine repository root
    repo_root = Path(__file__).parent.parent.resolve()
    
    print("=" * 80)
    print("Documentation Path Update Script")
    print("=" * 80)
    print(f"Repository root: {repo_root}\n")
    
    updater = DocumentationPathUpdater(repo_root=repo_root)
    
    if args.dry_run:
        updater.preview_changes()
        sys.exit(0)
    
    if args.execute:
        success = updater.execute_updates()
        sys.exit(0 if success else 1)
    
    # No action specified
    print("Please specify an action:")
    print("  --dry-run   : Preview changes")
    print("  --execute   : Execute path updates")
    sys.exit(1)


if __name__ == "__main__":
    main()

# Made with Bob
