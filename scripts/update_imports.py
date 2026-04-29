#!/usr/bin/env python3
"""
Import Path Update Script for datasift-opensource

This script updates import statements throughout the codebase after reorganization.
It handles the transition from datasift_opensource.backend.* to datasift.*

Usage:
    python scripts/update_imports.py --dry-run  # Preview changes
    python scripts/update_imports.py --execute  # Execute updates
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class ImportUpdater:
    """Updates import statements throughout the codebase."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.import_mappings = self._get_import_mappings()
        self.changes_made = []

    def _get_import_mappings(self) -> Dict[str, str]:
        """Define mappings from old import paths to new ones."""
        return {
            # Relative imports that assume backend/ is in PYTHONPATH
            # These must come BEFORE the datasift_opensource patterns
            r"from app\.": "from datasift.api.",
            r"import app\.": "import datasift.api.",
            r"from app import": "from datasift.api import",
            
            r"from cli\.": "from datasift.cli.",
            r"import cli\.": "import datasift.cli.",
            r"from cli import": "from datasift.cli import",

            r"@patch\(\"cli\.datasift_cli\.": "@patch(\"datasift.cli.datasift_cli.",
            
            r"from core\.assets_management\.": "from datasift.core.flows.",
            r"import core\.assets_management\.": "import datasift.core.flows.",
            r"\"core\.assets_management\.": "\"datasift.core.flows.",
            
            r"from core\.orchestrator\.": "from datasift.core.orchestration.",
            r"import core\.orchestrator\.": "import datasift.core.orchestration.",
            
            r"\"core\.orchestrator\.": "\"datasift.core.orchestration.",

            r"from core\.": "from datasift.core.",
            r"import core\.": "import datasift.core.",
            r"from core import": "from datasift.core import",
            r"\"core\.operators\.": "\"datasift.core.operators.",
            
            # Direct module imports (for intermediate migration paths)
            r"^from constants\.": "from datasift.core.constants.",
            r"^import constants\.": "import datasift.core.constants.",
            r"^from constants import": "from datasift.core.constants import",
            
            r"^from exceptions\.": "from datasift.exceptions.",
            r"^import exceptions\.": "import datasift.exceptions.",
            r"^from exceptions import": "from datasift.exceptions import",
            
            r"^from utils\.": "from datasift.utils.",
            r"^import utils\.": "import datasift.utils.",
            r"^from utils import": "from datasift.utils import",
            
            r"^from integrations\.": "from datasift.integrations.",
            r"^import integrations\.": "import datasift.integrations.",
            r"^from integrations import": "from datasift.integrations import",
            
            # Direct imports from common.clients (convenience imports from __init__.py)
            r"from common\.clients import BaseLLMClient": "from datasift.integrations.base_llm_client import BaseLLMClient",
            r"from common\.clients import HuggingFaceLLMClient": "from datasift.integrations.huggingface.client import HuggingFaceLLMClient",
            r"from common\.clients import LiteLLMLLMClient": "from datasift.integrations.litellm.client import LiteLLMLLMClient",
            r"from common\.clients\.litellm_llm_client import LiteLLMLLMClient": "from datasift.integrations.litellm.client import LiteLLMLLMClient",
            r"from common\.clients import OllamaClient": "from datasift.integrations.ollama.client import OllamaClient",
            r"from common\.clients import InteractionMode": "from datasift.integrations.ollama.client import InteractionMode",
            r"from common\.clients import require_package": "from datasift.integrations.base_llm_client import require_package",
            r"from common\.clients import retry_with_backoff": "from datasift.integrations.base_llm_client import retry_with_backoff",
            
            # String literals in patch statements for old module paths (must come before import patterns)
            r"common\.clients\.ollama_client\.OllamaClient": "datasift.integrations.ollama.client.OllamaClient",
            r"common\.clients\.ollama_client\.litellm_llm_client": "datasift.integrations.ollama.client.LiteLLMLLMClient",
            r"\"common\.clients\.ollama_client\.": "\"datasift.integrations.ollama.client.",
            r"\"common\.clients\.litellm_llm_client\.": "\"datasift.integrations.litellm.client.",
            
            # Specific client imports (must come before generic clients pattern)
            r"from common\.clients\.ollama": "from datasift.integrations.ollama",
            r"from common\.clients\.docling_serve_client": "from datasift.integrations.docling.client",
            r"\"common\.clients\.docling_serve_client": "\"datasift.integrations.docling.client",
            r"from common\.clients\.docling": "from datasift.integrations.docling",
            r"from common\.clients\.litellm": "from datasift.integrations.litellm",
            r"from common\.clients\.huggingface": "from datasift.integrations.huggingface",
            r"from common\.clients\.base_llm_client": "from datasift.integrations.base_llm_client",
            r"from common\.clients\.rest_client": "from datasift.integrations.rest_client",
            r"from common\.clients\.vlm_pipeline_options_provider": "from datasift.integrations.docling.vlm_pipeline_options_provider",
            r"from common\.clients\.": "from datasift.integrations.",
            
            r"\"common\.clients\.vlm_pipeline_options_provider": "\"datasift.integrations.docling.vlm_pipeline_options_provider",

            r"from common\.util\.": "from datasift.utils.",
            r"import common\.util\.": "import datasift.utils.",
            r"\"common\.util\.job_tracker\.storage\.": "\"datasift.utils.job_tracker.storage.",
            r"\"common\.util\.core\.": "\"datasift.utils.core.",
            
            r"@patch\(\"common\.util\.": "@patch(\"datasift.utils.",

            r"from common\.constants\.": "from datasift.core.constants.",
            r"from common\.exceptions\.": "from datasift.exceptions.",
            r"from common\.models\.": "from datasift.core.models.",
            r"from common\.document_classes\.": "from datasift.core.document_classes.",
            r"from common\.": "from datasift.",
            r"import common\.": "import datasift.",
            
            # Storage module
            r"from storage\.": "from datasift.storage.",
            r"import storage\.": "import datasift.storage.",
            r"from storage import": "from datasift.storage import",
            
            # Lib module
            r"from lib\.": "from datasift.lib.",
            r"import lib\.": "import datasift.lib.",
            r"from lib import": "from datasift.lib import",
            r"\"lib\.datasift_flow_manager": "\"datasift.lib.datasift_flow_manager",

            # Intermediate migration paths (datasift.* to datasift.*)
            r"from common\.constants": "from datasift.core.constants",
            r"from common\.exceptions": "from datasift.exceptions",
            r"from common\.util": "from datasift.utils",
            r"\"common\.util\.": "\"datasift.utils.",
            
            # Fix incorrect datasift.* imports (already partially migrated)
            r"from datasift\.constants": "from datasift.core.constants",
            r"import datasift\.constants": "import datasift.core.constants",
            r"from datasift\.exceptions": "from datasift.exceptions",
            r"import datasift\.exceptions": "import datasift.exceptions",
            
            # Fix incorrect ollama imports
            r"from datasift\.integrations\.ollama_client": "from datasift.integrations.ollama.client",
            r"import datasift\.integrations\.ollama_client": "import datasift.integrations.ollama.client",
            r"from datasift\.integrations\.ollama_embeddings_adapter": "from datasift.integrations.ollama.embeddings",
            r"import datasift\.integrations\.ollama_embeddings_adapter": "import datasift.integrations.ollama.embeddings",
            
            # Fix incorrect datasift.clients imports - need specific mappings
            r"^from datasift\.clients import BaseLLMClient": "from datasift.integrations.base_llm_client import BaseLLMClient",
            r"^from datasift\.clients import HuggingFaceLLMClient": "from datasift.integrations.huggingface.client import HuggingFaceLLMClient",
            r"^from datasift\.clients import LiteLLMLLMClient": "from datasift.integrations.litellm.client import LiteLLMLLMClient",
            r"^from datasift\.clients import OllamaClient": "from datasift.integrations.ollama.client import OllamaClient",
            r"^from datasift\.clients import InteractionMode": "from datasift.integrations.ollama.client import InteractionMode",
            r"^from datasift\.clients import require_package": "from datasift.integrations.base_llm_client import require_package",
            r"^from datasift\.clients import retry_with_backoff": "from datasift.integrations.base_llm_client import retry_with_backoff",
            r"^from datasift\.clients": "from datasift.integrations",
            r"^import datasift\.clients": "import datasift.integrations",
            
            # Full path imports with src.datasift_opensource.backend (absolute imports from tests)
            r"from src\.datasift_opensource\.backend\.app\.": "from datasift.api.",
            r"import src\.datasift_opensource\.backend\.app\.": "import datasift.api.",
            r"\"src\.datasift_opensource\.backend\.app\.": "\"datasift.api.",
            r"\"app\.": "\"datasift.api.",
            
            r"from src\.datasift_opensource\.backend\.cli\.": "from datasift.cli.",
            r"import src\.datasift_opensource\.backend\.cli\.": "import datasift.cli.",
            
            r"from src\.datasift_opensource\.backend\.common\.constants\.": "from datasift.core.constants.",
            r"from src\.datasift_opensource\.backend\.common\.exceptions\.": "from datasift.exceptions.",
            r"from src\.datasift_opensource\.backend\.common\.models\.": "from datasift.core.models.",
            r"from src\.datasift_opensource\.backend\.common\.": "from datasift.",
            r"import src\.datasift_opensource\.backend\.common\.": "import datasift.",
            
            r"from src\.datasift_opensource\.backend\.core\.orchestrator\.": "from datasift.core.orchestration.",
            r"import src\.datasift_opensource\.backend\.core\.orchestrator\.": "import datasift.core.orchestration.",
            
            r"from src\.datasift_opensource\.backend\.core\.assets_management\.": "from datasift.core.flows.",
            r"import src\.datasift_opensource\.backend\.core\.assets_management\.": "import datasift.core.flows.",
            
            r"from src\.datasift_opensource\.backend\.core\.": "from datasift.core.",
            r"import src\.datasift_opensource\.backend\.core\.": "import datasift.core.",
            
            r"from src\.datasift_opensource\.backend\.storage\.": "from datasift.storage.",
            r"import src\.datasift_opensource\.backend\.storage\.": "import datasift.storage.",
            
            r"from src\.datasift_opensource\.backend\.lib\.": "from datasift.lib.",
            r"import src\.datasift_opensource\.backend\.lib\.": "import datasift.lib.",
            
            r"from src\.datasift_opensource\.backend\.": "from datasift.",
            r"import src\.datasift_opensource\.backend\.": "import datasift.",
            
            # patch statements for mocking
            r"\"src\.datasift_opensource\.backend\.": "\"datasift.",

            # Full path imports with datasift_opensource (without src prefix)
            r"from datasift_opensource\.backend\.app\.": "from datasift.api.",
            r"import datasift_opensource\.backend\.app\.": "import datasift.api.",
            
            r"from datasift_opensource\.backend\.cli\.": "from datasift.cli.",
            r"import datasift_opensource\.backend\.cli\.": "import datasift.cli.",
            
            # Direct imports from common.clients (full path - convenience imports from __init__.py)
            r"from datasift_opensource\.backend\.common\.clients import BaseLLMClient": "from datasift.integrations.base_llm_client import BaseLLMClient",
            r"from datasift_opensource\.backend\.common\.clients import HuggingFaceLLMClient": "from datasift.integrations.huggingface.client import HuggingFaceLLMClient",
            r"from datasift_opensource\.backend\.common\.clients import LiteLLMLLMClient": "from datasift.integrations.litellm.client import LiteLLMLLMClient",
            r"from datasift_opensource\.backend\.common\.clients import OllamaClient": "from datasift.integrations.ollama.client import OllamaClient",
            r"from datasift_opensource\.backend\.common\.clients import InteractionMode": "from datasift.integrations.ollama.client import InteractionMode",
            r"from datasift_opensource\.backend\.common\.clients import require_package": "from datasift.integrations.base_llm_client import require_package",
            r"from datasift_opensource\.backend\.common\.clients import retry_with_backoff": "from datasift.integrations.base_llm_client import retry_with_backoff",
            
            # Specific client imports (full path)
            r"from datasift_opensource\.backend\.common\.clients\.ollama": "from datasift.integrations.ollama",
            r"from datasift_opensource\.backend\.common\.clients\.docling_serve_client": "from datasift.integrations.docling.client",
            r"from datasift_opensource\.backend\.common\.clients\.docling": "from datasift.integrations.docling",
            r"from datasift_opensource\.backend\.common\.clients\.litellm": "from datasift.integrations.litellm",
            r"from datasift_opensource\.backend\.common\.clients\.huggingface": "from datasift.integrations.huggingface",
            r"from datasift_opensource\.backend\.common\.clients\.base_llm_client": "from datasift.integrations.base_llm_client",
            r"from datasift_opensource\.backend\.common\.clients\.rest_client": "from datasift.integrations.rest_client",
            r"from datasift_opensource\.backend\.common\.clients\.vlm_pipeline_options_provider": "from datasift.integrations.docling.vlm_pipeline_options_provider",
            
            r"\"common\.clients\.vlm_pipeline_options_provider\.": "\"datasift.integrations.docling.vlm_pipeline_options_provider.",
            r"\"common\.clients\.rest_client\.": "\"datasift.integrations.rest_client.",

            r"from datasift_opensource\.backend\.common\.util\.": "from datasift.utils.",
            r"import datasift_opensource\.backend\.common\.util\.": "import datasift.utils.",
            
            r"from datasift_opensource\.backend\.common\.constants\.": "from datasift.core.constants.",
            r"from datasift_opensource\.backend\.common\.exceptions\.": "from datasift.exceptions.",
            r"from datasift_opensource\.backend\.common\.models\.": "from datasift.core.models.",
            r"from datasift_opensource\.backend\.common\.document_classes\.": "from datasift.core.document_classes.",
            
            r"\"common\.models\.": "\"datasift.core.models.",

            r"from datasift_opensource\.backend\.core\.orchestrator\.": "from datasift.core.orchestration.",
            r"import datasift_opensource\.backend\.core\.orchestrator\.": "import datasift.core.orchestration.",
            
            r"from datasift_opensource\.backend\.core\.assets_management\.": "from datasift.core.flows.",
            r"import datasift_opensource\.backend\.core\.assets_management\.": "import datasift.core.flows.",
            
            r"from datasift_opensource\.backend\.core\.": "from datasift.core.",
            r"import datasift_opensource\.backend\.core\.": "import datasift.core.",
            
            # Storage module (full path)
            r"from datasift_opensource\.backend\.storage\.": "from datasift.storage.",
            r"import datasift_opensource\.backend\.storage\.": "import datasift.storage.",
            
            # Lib module (full path)
            r"from datasift_opensource\.backend\.lib\.": "from datasift.lib.",
            r"import datasift_opensource\.backend\.lib\.": "import datasift.lib.",
            
            # Generic fallback for any remaining backend references
            r"from datasift_opensource\.backend\.common\.": "from datasift.",
            r"import datasift_opensource\.backend\.common\.": "import datasift.",
            r"from datasift_opensource\.backend\.": "from datasift.",
            r"import datasift_opensource\.backend\.": "import datasift.",
        }

    def find_python_files(self) -> List[Path]:
        """Find all Python files in the repository."""
        python_files = []
        
        # Search in src directory
        src_dir = self.repo_root / "src"
        if src_dir.exists():
            python_files.extend(src_dir.rglob("*.py"))
        
        # Search in tests directory
        tests_dir = self.repo_root / "tests"
        if tests_dir.exists():
            python_files.extend(tests_dir.rglob("*.py"))
        
        # Search in examples directory
        examples_dir = self.repo_root / "examples"
        if examples_dir.exists():
            python_files.extend(examples_dir.rglob("*.py"))
        
        # Search in scripts directory
        #scripts_dir = self.repo_root / "scripts"
        #if scripts_dir.exists():
        #    python_files.extend(scripts_dir.rglob("*.py"))
        
        return [f for f in python_files if f.is_file()]

    def update_file_imports(self, file_path: Path, *, dry_run: bool = True) -> Tuple[bool, List[str]]:
        """Update imports in a single file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            original_content = content
            changes = []
            
            # Apply each mapping
            for old_pattern, new_pattern in self.import_mappings.items():
                matches = re.finditer(old_pattern, content, re.MULTILINE)
                for match in matches:
                    old_import = match.group(0)
                    new_import = re.sub(old_pattern, new_pattern, old_import, flags=re.MULTILINE)
                    if old_import != new_import:
                        changes.append(f"  {old_import} → {new_import}")
                
                content = re.sub(old_pattern, new_pattern, content, flags=re.MULTILINE)
            
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
        """Preview all import changes without executing them."""
        print("\n📋 Preview of import updates:\n")
        print("=" * 80)
        
        python_files = self.find_python_files()
        print(f"Found {len(python_files)} Python files to check\n")
        
        files_with_changes = 0
        total_changes = 0
        
        for file_path in python_files:
            changed, changes = self.update_file_imports(file_path, dry_run=True)
            if changed:
                files_with_changes += 1
                total_changes += len(changes)
                rel_path = file_path.relative_to(self.repo_root)
                print(f"📄 {rel_path}")
                for change in changes:
                    print(change)
                print()
        
        print("=" * 80)
        print(f"\nSummary:")
        print(f"  Files with changes: {files_with_changes}")
        print(f"  Total import updates: {total_changes}")
        print(f"\n💡 This was a dry run. Use --execute to apply changes.")

    def execute_updates(self) -> bool:
        """Execute import updates across all files."""
        print("\n🚀 Executing import updates...\n")
        
        python_files = self.find_python_files()
        print(f"Processing {len(python_files)} Python files...\n")
        
        files_updated = 0
        total_changes = 0
        
        for file_path in python_files:
            changed, changes = self.update_file_imports(file_path, dry_run=False)
            if changed:
                files_updated += 1
                total_changes += len(changes)
                rel_path = file_path.relative_to(self.repo_root)
                print(f"✓ Updated: {rel_path} ({len(changes)} changes)")
        
        print("\n" + "=" * 80)
        print(f"\n✅ Import updates completed!")
        print(f"  Files updated: {files_updated}")
        print(f"  Total changes: {total_changes}")
        
        if files_updated > 0:
            print(f"\n⚠️  IMPORTANT: Please verify the changes:")
            print("  1. Run tests to ensure everything works")
            print("  2. Check for any remaining manual import fixes needed")
            print("  3. Review git diff to confirm changes are correct")
        
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Update import statements after repository reorganization"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without executing them"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the import updates"
    )
    
    args = parser.parse_args()
    
    # Determine repository root
    repo_root = Path(__file__).parent.parent.resolve()
    
    print("=" * 80)
    print("Import Path Update Script")
    print("=" * 80)
    print(f"Repository root: {repo_root}\n")
    
    updater = ImportUpdater(repo_root)
    
    if args.dry_run:
        updater.preview_changes()
        sys.exit(0)
    
    if args.execute:
        success = updater.execute_updates()
        sys.exit(0 if success else 1)
    
    # No action specified
    print("Please specify an action:")
    print("  --dry-run   : Preview changes")
    print("  --execute   : Execute import updates")
    sys.exit(1)


if __name__ == "__main__":
    main()

# Made with Bob
