#!/usr/bin/env python3
"""
Build script to compile the React frontend and prepare it for inclusion in the Python wheel.
This script is executed during the wheel build process.
"""

import shutil
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], cwd: Path) -> None:
    """Run a command and handle errors."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    print(result.stdout)


def main():
    """Build the frontend and BFF and copy both into the Python package."""
    project_root = Path(__file__).parent.parent
    frontend_dir = project_root / "frontend"
    frontend_dist = frontend_dir / "dist"
    bff_out = frontend_dir / "bff" / "server.cjs"
    static_target = project_root / "src" / "docpipe" / "api" / "static"
    bff_target = project_root / "src" / "docpipe" / "api" / "bff"

    print("=" * 60)
    print("Building React Frontend and BFF for Python Package")
    print("=" * 60)

    if not frontend_dir.exists():
        print("Warning: frontend directory not found. Skipping frontend build.")
        return

    if not (frontend_dir / "package.json").exists():
        print("Warning: package.json not found. Skipping frontend build.")
        return

    try:
        subprocess.run(["npm", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Warning: npm not found. Skipping frontend build.")
        print("To include the frontend, install Node.js and npm, then rebuild.")
        return

    # Install dependencies
    print("\n1. Installing frontend dependencies...")
    run_command(["npm", "install"], frontend_dir)

    # Build the React frontend
    print("\n2. Building frontend for production...")
    run_command(["npm", "run", "build"], frontend_dir)

    if not frontend_dist.exists():
        print("Error: Frontend build failed - dist directory not found")
        sys.exit(1)

    # Bundle the BFF into a single self-contained CJS file (no node_modules needed at runtime)
    print("\n3. Bundling BFF server...")
    run_command(["npm", "run", "build:bff"], frontend_dir)

    if not bff_out.exists():
        print("Error: BFF build failed - bff/server.cjs not found")
        sys.exit(1)

    # Copy frontend static assets
    print("\n4. Copying built assets to Python package...")
    if static_target.exists():
        shutil.rmtree(static_target)
    static_target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(frontend_dist, static_target, dirs_exist_ok=True)

    # Copy BFF bundle
    if bff_target.exists():
        shutil.rmtree(bff_target)
    bff_target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bff_out, bff_target / "server.cjs")

    print(f"\n[OK] Frontend built and copied to {static_target}")
    print(f"[OK] BFF bundled and copied to {bff_target}")
    print("=" * 60)


if __name__ == "__main__":
    main()
