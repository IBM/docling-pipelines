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

        try:
            result = subprocess.run([sys.executable, str(build_script)], capture_output=True, text=True, check=True)
            print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        except subprocess.CalledProcessError as e:
            print(f"Frontend build failed: {e.stderr}", file=sys.stderr)
            # Don't fail the build if frontend build fails
            print("Warning: Continuing without frontend assets")
