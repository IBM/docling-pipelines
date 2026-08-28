#!/usr/bin/env python3
"""
migrate_imports.py — Update your branch's Python files after the datasift → docpipe rename.

The repository was renamed from datasift-opensource to docling-pipelines.
All internal Python imports changed from `datasift.*` to `docpipe.*` and all
public-facing names changed to `docling-pipelines` / `docpipe`.

Run this script on your feature branch BEFORE rebasing onto main:

    python scripts/migrate_imports.py

It will update every file in your branch that still uses the old names.
Dry-run first (shows what would change without writing):

    python scripts/migrate_imports.py --dry-run

Limit to specific paths:

    python scripts/migrate_imports.py src/docpipe/my_new_operator.py tests/unit/

After running, review with `git diff` and commit the result.
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Full ordered replacement table (most specific → least specific).
# This is the canonical mapping from the original rename commit.
# ---------------------------------------------------------------------------
REPLACEMENTS: list[tuple[str, str]] = [
    # ── module-path references ─────────────────────────────────────────────
    ("datasift.cli.datasift_cli", "docpipe.cli.docpipe_cli"),
    ("datasift.lib.datasift_flow_manager", "docpipe.lib.docpipe_flow_manager"),
    ("datasift.exceptions.datasift_exceptions", "docpipe.exceptions.docpipe_exceptions"),
    # ── class / symbol names ───────────────────────────────────────────────
    ("DatasiftFlowManager", "DocpipeFlowManager"),
    ("DatasiftConstants", "DocpipeConstants"),
    ("DatasiftException", "DocpipeException"),
    # ── CLI entry-point command strings ───────────────────────────────────
    ("datasift-orchestrator", "docling-pipelines"),
    ("datasift-api", "docling-pipelines-api"),
    # ── package / project names ────────────────────────────────────────────
    ("datasift-opensource", "docling-pipelines"),
    ("datasift-config.yaml", "docling-pipelines-config.yaml"),
    # ── Python import prefixes ─────────────────────────────────────────────
    ("from datasift.", "from docpipe."),
    ("import datasift.", "import docpipe."),
    # ── environment variable prefix ────────────────────────────────────────
    ("DATASIFT_", "DOCPIPE_"),
    # ── string literal owner tags ──────────────────────────────────────────
    ('"datasift_enterprise"', '"docpipe_enterprise"'),
    ("'datasift_enterprise'", "'docpipe_enterprise'"),
    ('"DATASIFT"', '"DOCPIPE"'),
    ("'DATASIFT'", "'DOCPIPE'"),
    ('"datasift_logs"', '"docpipe_logs"'),
    ("'datasift_logs'", "'docpipe_logs'"),
    ('"datasift"', '"docpipe"'),
    ("'datasift'", "'docpipe'"),
    # ── UI/backend package path ────────────────────────────────────────────
    ("datasift_opensource", "docpipe_app"),
    # ── catch-all (comments, docstrings, remaining identifiers) ───────────
    ("datasift", "docpipe"),
    ("Datasift", "Docpipe"),
    ("DataSift", "Docpipe"),
    ("DATASIFT", "DOCPIPE"),
]

# File extensions to process
INCLUDE_EXTENSIONS = {
    ".py",
    ".toml",
    ".cfg",
    ".ini",
    ".yaml",
    ".yml",
    ".json",
    ".md",
    ".txt",
    ".sh",
    ".env",
    ".example",
    ".rst",
    ".ipynb",
    ".html",
    ".css",
    ".js",
    ".ts",
}

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    ".vtest",
    "dist",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "node_modules",
}

SKIP_FILES = {"uv.lock", ".secrets.baseline", "migrate_imports.py"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def should_process(path: Path) -> bool:
    for part in path.parts:
        if part in SKIP_DIRS:
            return False
    if path.name in SKIP_FILES:
        return False
    if path.suffix in INCLUDE_EXTENSIONS:
        return True
    # Files with no extension (Dockerfile, Jenkinsfile, CODEOWNERS, …)
    if "." not in path.name:
        return True
    return False


def apply_replacements(text: str) -> str:
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    return text


def collect_targets(paths: list[Path]) -> list[Path]:
    """Return all processable files under the given paths."""
    targets: list[Path] = []
    for p in paths:
        if p.is_file():
            if should_process(p):
                targets.append(p)
        elif p.is_dir():
            for child in p.rglob("*"):
                if child.is_file() and should_process(child):
                    targets.append(child)
    return targets


def git_changed_files() -> list[Path]:
    """Return files that differ from main (staged + unstaged + new)."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "origin/main...HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Fall back: all tracked files
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    return [ROOT / p.strip() for p in result.stdout.splitlines() if p.strip()]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate datasift→docpipe import references on your branch.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update only files changed on your branch (default)
  python scripts/migrate_imports.py

  # Dry-run: show what would change
  python scripts/migrate_imports.py --dry-run

  # Update all files in the repo (use when rebasing a very old branch)
  python scripts/migrate_imports.py --all

  # Update specific files or directories
  python scripts/migrate_imports.py src/docpipe/my_operator.py tests/unit/
        """,
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files or directories to migrate. Defaults to files changed on this branch.",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        dest="process_all",
        help="Process every file in the repository (slow; use for very old branches).",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Print what would be changed without writing any files.",
    )

    args = parser.parse_args()

    if args.paths:
        candidates = collect_targets([p.resolve() for p in args.paths])
    elif args.process_all:
        candidates = collect_targets([ROOT])
    else:
        candidates = [f for f in git_changed_files() if f.exists() and should_process(f)]

    if not candidates:
        print("No files to migrate.")
        sys.exit(0)

    changed: list[Path] = []
    unchanged: list[Path] = []

    for fpath in candidates:
        try:
            original = fpath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError) as exc:
            print(f"  [skip] {fpath.relative_to(ROOT)}: {exc}")
            continue

        updated = apply_replacements(original)
        if updated == original:
            unchanged.append(fpath)
            continue

        if args.dry_run:
            print(f"  [would update] {fpath.relative_to(ROOT)}")
        else:
            fpath.write_text(updated, encoding="utf-8")
            print(f"  [updated] {fpath.relative_to(ROOT)}")
        changed.append(fpath)

    verb = "would update" if args.dry_run else "updated"
    print(f"\nDone: {len(changed)} files {verb}, {len(unchanged)} already up to date.")

    if args.dry_run and changed:
        print("\nRe-run without --dry-run to apply changes.")

    if not args.dry_run and changed:
        print("\nNext steps:")
        print("  git diff           # review changes")
        print("  git add -u         # stage updates")
        print("  git commit -m 'chore: migrate datasift→docpipe imports'")


if __name__ == "__main__":
    main()
