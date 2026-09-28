"""Hatch build hook to build frontend during wheel creation."""

import subprocess
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface  # type: ignore[import-not-found]


class CustomBuildHook(BuildHookInterface):
    """Custom build hook to compile React frontend."""

    PLUGIN_NAME = "custom"

    def initialize(self, version, build_data):
        """Run frontend build before creating wheel."""
        if self.target_name != "wheel":
            return

        print("=" * 60)
        print("Running frontend build hook")
        print("=" * 60)

        # Run the build script
        build_script = Path(__file__).parent / "scripts" / "build_frontend.py"

        result = subprocess.run([sys.executable, str(build_script)], capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if result.returncode != 0:
            print(f"Frontend build failed (exit {result.returncode})", file=sys.stderr)
            raise SystemExit(result.returncode)
