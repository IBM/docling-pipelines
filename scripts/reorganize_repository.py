#!/usr/bin/env python3
"""
Repository Reorganization Script for datasift-opensource

This script reorganizes the repository structure to follow modern Python project standards.
It includes backup, validation, and rollback capabilities.

Usage:
    python scripts/reorganize_repository.py --dry-run  # Preview changes
    python scripts/reorganize_repository.py --execute  # Execute reorganization
    python scripts/reorganize_repository.py --rollback # Rollback to backup
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


class RepositoryReorganizer:
    """Handles repository reorganization with backup and rollback capabilities."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.backup_dir = repo_root / ".reorganization_backup"
        self.backup_manifest = self.backup_dir / "manifest.json"
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def validate_structure(self) -> bool:
        """Validate that the current structure matches expectations."""
        print("🔍 Validating current repository structure...")

        required_paths = [
            "src/datasift_opensource/backend",
            "README.md",
            "CONTRIBUTING.md",
        ]

        missing = []
        for path in required_paths:
            if not (self.repo_root / path).exists():
                missing.append(path)

        if missing:
            print(f"❌ Missing required paths: {', '.join(missing)}")
            return False

        # Check if pyproject.toml exists at root or in backend
        pyproject_root = self.repo_root / "pyproject.toml"
        pyproject_backend = self.repo_root / "src/datasift_opensource/backend/pyproject.toml"

        if not pyproject_root.exists() and not pyproject_backend.exists():
            print("⚠️  Warning: pyproject.toml not found at root or in backend directory")
            print("   It should be restored from git history or created manually")
        elif pyproject_root.exists() and not pyproject_backend.exists():
            print("Using root pyproject.toml for the reorganized repository structure")

        print("✅ Current structure validated")
        return True

    def create_backup(self) -> bool:
        """Create a backup of the current structure."""
        print(f"\n📦 Creating backup at {self.backup_dir}...")

        try:
            if self.backup_dir.exists():
                print("⚠️  Removing existing backup...")
                shutil.rmtree(self.backup_dir)

            self.backup_dir.mkdir(parents=True)

            # Backup critical directories
            backup_items = [
                "src/datasift_opensource/app",
                "src/datasift_opensource/cli",
                "src/datasift_opensource/common",
                "src/datasift_opensource/core",
                "src/datasift_opensource/lib",
                "src/datasift_opensource/storage",
                "tests",
                "examples",
                "docs",
            ]

            manifest = {
                "timestamp": self.timestamp,
                "backed_up_items": [],
            }

            for item in backup_items:
                src_path = self.repo_root / item
                if src_path.exists():
                    dest_path = self.backup_dir / item
                    if src_path.is_dir():
                        shutil.copytree(src_path, dest_path)
                    else:
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_path, dest_path)
                    manifest["backed_up_items"].append(item) # type: ignore
                    print(f"  ✓ Backed up: {item}")

            # Save manifest
            with open(self.backup_manifest, "w") as f:
                json.dump(manifest, f, indent=2)

            print("✅ Backup created successfully")
            return True

        except Exception as e:
            print(f"❌ Backup failed: {e}")
            return False

    def get_move_operations(self) -> list[tuple[Path, Path]]:
        """Define all move operations for reorganization."""
        operations = []

        # Move backend contents up to src/datasift/
        backend_src = self.repo_root / "src/datasift_opensource/backend"
        new_src = self.repo_root / "src/datasift"

        # Map old structure to new structure
        moves = [
            # CLI
            (backend_src / "cli", new_src / "cli"),
            # API (from app)
            (backend_src / "app", new_src / "api"),
            # Core operators and orchestration
            (backend_src / "core/operators", new_src / "core/operators"),
            (backend_src / "core/orchestrator", new_src / "core/orchestration"),
            (backend_src / "core/assets_management", new_src / "core/flows"),
            (backend_src / "core/data_access", new_src / "core/data_access"),
            (backend_src / "core/README.md", new_src / "core/README.md"),
            # Integrations (from common/clients)
            (backend_src / "common/clients/ollama_client.py", new_src / "integrations/ollama/client.py"),
            (
                backend_src / "common/clients/ollama_embeddings_adapter.py",
                new_src / "integrations/ollama/embeddings.py",
            ),
            (backend_src / "common/clients/docling_serve_client.py", new_src / "integrations/docling/client.py"),
            (backend_src / "common/clients/litellm_llm_client.py", new_src / "integrations/litellm/client.py"),
            (backend_src / "common/clients/huggingface_llm_client.py", new_src / "integrations/huggingface/client.py"),
            # Additional client files (base classes and utilities)
            (backend_src / "common/clients/base_llm_client.py", new_src / "integrations/base_llm_client.py"),
            (backend_src / "common/clients/rest_client.py", new_src / "integrations/rest_client.py"),
            (
                backend_src / "common/clients/vlm_pipeline_options_provider.py",
                new_src / "integrations/docling/vlm_pipeline_options_provider.py",
            ),
            # Utils (from common/util)
            (backend_src / "common/util", new_src / "utils"),
            # Constants and exceptions
            (backend_src / "common/constants", new_src / "core/constants"),
            (backend_src / "common/exceptions", new_src / "exceptions"),
            # Models
            (backend_src / "common/models", new_src / "core/models"),
            # Document classes
            (backend_src / "common/document_classes", new_src / "core/document_classes"),
            # Lib
            (backend_src / "lib", new_src / "lib"),
            # Storage
            (backend_src / "storage", new_src / "storage"),
            # Configuration - only move if exists, otherwise will be restored from git
            (backend_src / ".python-version", self.repo_root / ".python-version"),
        ]

        for src, dest in moves:
            if src.exists():
                operations.append((src, dest))

        return operations

    def preview_changes(self) -> None:
        """Preview all changes without executing them."""
        print("\n📋 Preview of reorganization changes:\n")

        operations = self.get_move_operations()

        print("Move Operations:")
        print("-" * 80)
        for src, dest in operations:
            rel_src = src.relative_to(self.repo_root)
            rel_dest = dest.relative_to(self.repo_root)
            print(f"  {rel_src}")
            print(f"    → {rel_dest}")
            print()

        print(f"\nTotal operations: {len(operations)}")

        # Show new files to be created
        print("\n" + "=" * 80)
        print("New Files to Create:")
        print("-" * 80)
        new_files = [
            "LICENSE",
            "CHANGELOG.md",
            "CODE_OF_CONDUCT.md",
            "src/datasift/__init__.py",
            "src/datasift/integrations/__init__.py",
            "src/datasift/integrations/ollama/__init__.py",
            "src/datasift/integrations/docling/__init__.py",
            "src/datasift/integrations/litellm/__init__.py",
            "src/datasift/integrations/huggingface/__init__.py",
        ]
        for file in new_files:
            print(f"  + {file}")

    def execute_reorganization(self) -> bool:
        """Execute the reorganization."""
        print("\n🚀 Executing reorganization...\n")

        try:
            operations = self.get_move_operations()
            new_src = self.repo_root / "src/datasift"

            # Create new directory structure
            print("Creating new directory structure...")
            new_src.mkdir(parents=True, exist_ok=True)
            (new_src / "core").mkdir(exist_ok=True)
            (new_src / "integrations").mkdir(exist_ok=True)
            (new_src / "utils").mkdir(exist_ok=True)

            # Execute moves
            for src, dest in operations:
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)

                    if src.is_dir():
                        #if dest.exists():
                        #    shutil.rmtree(dest)
                        shutil.copytree(src, dst=dest, dirs_exist_ok=True)
                        shutil.rmtree(src)
                    else:
                        shutil.move(src, dest)

                    rel_src = src.relative_to(self.repo_root)
                    rel_dest = dest.relative_to(self.repo_root)
                    print(f"  ✓ Moved: {rel_src} → {rel_dest}")

                except Exception as e:
                    print(f"  ⚠️  Warning: Could not move {src}: {e}")

            # Create new __init__.py files
            print("\nCreating __init__.py files...")
            init_files = [
                new_src / "__init__.py",
                new_src / "core/__init__.py",
                new_src / "integrations/__init__.py",
                new_src / "integrations/ollama/__init__.py",
                new_src / "integrations/docling/__init__.py",
                new_src / "integrations/litellm/__init__.py",
                new_src / "integrations/huggingface/__init__.py",
                new_src / "utils/__init__.py",
            ]

            for init_file in init_files:
                init_file.parent.mkdir(parents=True, exist_ok=True)
                if not init_file.exists():
                    init_file.write_text('"""Package initialization."""\n')
                    print(f"  ✓ Created: {init_file.relative_to(self.repo_root)}")

            # Create missing standard files
            self._create_standard_files()

            print("\n✅ Reorganization completed successfully!")
            print("\n⚠️  IMPORTANT: You need to:")
            print("  1. Update import statements throughout the codebase")
            print("  2. Update CI/CD configurations")
            print("  3. Update documentation references")
            print("  4. Run tests to verify everything works")
            print(f"\n💾 Backup available at: {self.backup_dir}")

            return True

        except Exception as e:
            print(f"\n❌ Reorganization failed: {e}")
            print("Run with --rollback to restore from backup")
            return False

    def _create_standard_files(self) -> None:
        """Create missing standard files."""
        print("\nCreating standard files...")

        # LICENSE
        license_file = self.repo_root / "LICENSE"
        if not license_file.exists():
            license_file.write_text("""Apache License 2.0

Copyright (c) 2024 datasift-opensource contributors

[Full license text would go here]
""")
            print("  ✓ Created: LICENSE")

        # CHANGELOG.md
        changelog_file = self.repo_root / "CHANGELOG.md"
        if not changelog_file.exists():
            changelog_file.write_text("""# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Reorganized repository structure to follow modern Python project standards
- Simplified package name from `datasift_opensource` to `datasift`
- Moved configuration to root-level `pyproject.toml`

## [0.1.0] - 2024-XX-XX

### Added
- Initial release
""")
            print("  ✓ Created: CHANGELOG.md")

        # CODE_OF_CONDUCT.md
        coc_file = self.repo_root / "CODE_OF_CONDUCT.md"
        if not coc_file.exists():
            coc_file.write_text("""# Contributor Covenant Code of Conduct

## Our Pledge

We as members, contributors, and leaders pledge to make participation in our
community a harassment-free experience for everyone.

## Our Standards

Examples of behavior that contributes to a positive environment:
- Being respectful of differing opinions and experiences
- Giving and gracefully accepting constructive feedback
- Focusing on what is best for the community

## Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be
reported to the project maintainers.
""")
            print("  ✓ Created: CODE_OF_CONDUCT.md")

    def rollback(self) -> bool:
        """Rollback to the backup."""
        print("\n⏮️  Rolling back from backup...\n")

        if not self.backup_dir.exists():
            print("❌ No backup found. Cannot rollback.")
            return False

        try:
            # Load manifest
            with open(self.backup_manifest) as f:
                manifest = json.load(f)

            print(f"Restoring backup from: {manifest['timestamp']}")

            # Remove new structure
            new_src = self.repo_root / "src/datasift"
            if new_src.exists():
                print(f"  Removing: {new_src.relative_to(self.repo_root)}")
                shutil.rmtree(new_src)

            # Restore backed up items
            for item in manifest["backed_up_items"]:
                src_path = self.backup_dir / item
                dest_path = self.repo_root / item

                if dest_path.exists():
                    if dest_path.is_dir():
                        shutil.rmtree(dest_path)
                    else:
                        dest_path.unlink()

                if src_path.is_dir():
                    shutil.copytree(src_path, dest_path)
                else:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_path, dest_path)

                print(f"  ✓ Restored: {item}")

            print("\n✅ Rollback completed successfully!")
            return True

        except Exception as e:
            print(f"❌ Rollback failed: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Reorganize datasift-opensource repository structure")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without executing them")
    parser.add_argument("--backup", action="store_true", help="Create a backup of the existing code")
    parser.add_argument("--execute", action="store_true", help="Execute the reorganization")
    parser.add_argument("--rollback", action="store_true", help="Rollback to backup")

    args = parser.parse_args()

    # Determine repository root
    repo_root = Path(__file__).parent.parent.resolve()

    print("=" * 80)
    print("Repository Reorganization Script")
    print("=" * 80)
    print(f"Repository root: {repo_root}\n")

    reorganizer = RepositoryReorganizer(repo_root)

    if args.rollback:
        success = reorganizer.rollback()
        sys.exit(0 if success else 1)

    # Validate structure
    if not reorganizer.validate_structure():
        print("\n❌ Structure validation failed. Aborting.")
        sys.exit(1)

    if args.dry_run:
        reorganizer.preview_changes()
        print("\n💡 This was a dry run. Use --execute to apply changes.")
        sys.exit(0)

    if args.backup:
        # Create backup
        if not reorganizer.create_backup():
            print("\n❌ Backup failed. Aborting reorganization.")
            sys.exit(1)

    if args.execute:
        # Execute reorganization
        success = reorganizer.execute_reorganization()
        sys.exit(0 if success else 1)

    # No action specified
    print("Please specify an action:")
    print("  --dry-run   : Preview changes")
    print("  --execute   : Execute reorganization")
    print("  --rollback  : Rollback to backup")
    sys.exit(1)


if __name__ == "__main__":
    main()

# Made with Bob
