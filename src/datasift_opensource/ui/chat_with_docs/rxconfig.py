import os
from pathlib import Path

import reflex as rx

# Load the project-root .env file so DATASIFT_INDEX, OPENSEARCH_*, OLLAMA_HOST
# etc. are available to all state modules without needing to pass them on the
# command line every time.
_PROJECT_ROOT = Path(__file__).parents[4]  # .../datasift-opensource/
_ENV_FILE = _PROJECT_ROOT / ".env"
if _ENV_FILE.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=_ENV_FILE, override=False)  # don't override explicit env vars
    except ImportError:
        # dotenv not installed — fall back to manual parsing
        with _ENV_FILE.open() as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _, _v = _line.partition("=")
                    os.environ.setdefault(_k.strip(), _v.strip())

config = rx.Config(
    app_name="chat_with_file_ingestion", plugins=[rx.plugins.TailwindV3Plugin()]
)
