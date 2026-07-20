"""LocalProjectRepository — filesystem-based project persistence adapter.

Stores each project as a single JSON file:
    ~/Documents/pipeline/projects/{project_id}.json

Named 'local' to contrast with future remote/cloud adapters
(e.g. CamsProjectRepository, PostgresProjectRepository), consistent with how
LocalAssetRepository is named in the assets layer. The underlying file
format being JSON is an implementation detail, not a differentiator.

Uses filelock for write-safety under concurrent access, matching the
pattern used by JsonJobStatsStore.
"""

import json
from pathlib import Path

from filelock import FileLock

from docpipe.core.projects.domain.models.project import Project
from docpipe.core.projects.domain.ports.project_repository import ProjectRepository
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()

_DEFAULT_PROJECTS_PATH = Path.home() / "Documents" / "pipeline" / "projects"


class LocalProjectRepository(ProjectRepository):
    """Filesystem-based project repository.

    One JSON file per project stored at:
        ~/Documents/pipeline/projects/{project_id}.json

    Args:
        base_dir: Optional custom storage directory. Defaults to
            ~/Documents/pipeline/projects, consistent with how
            LocalAssetRepository stores flows under
            ~/Documents/pipeline/assets.
    """

    def __init__(self, *, base_dir: str | Path | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else _DEFAULT_PROJECTS_PATH
        self._base_dir.mkdir(parents=True, exist_ok=True)
        logger.info("LocalProjectRepository initialised at %s", self._base_dir)

    # ── Helpers ──────────────────────────────────────────────────────

    def _file_path(self, project_id: str) -> Path:
        return self._base_dir / f"{project_id}.json"

    def _lock_path(self, project_id: str) -> str:
        return str(self._file_path(project_id)) + ".lock"

    # ── ProjectRepository interface ───────────────────────────────────

    def save(self, *, project: Project) -> Project:
        """Write project to disk as JSON. Acquires a file-level lock."""
        path = self._file_path(project.project_id)
        with FileLock(self._lock_path(project.project_id)):
            path.write_text(project.to_json(), encoding="utf-8")
        logger.info("Saved project %s (%s)", project.project_id, project.name)
        return project

    def get(self, *, project_id: str) -> Project | None:
        """Read a project from disk by ID."""
        path = self._file_path(project_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Project.from_storage_dict(data)
        except Exception as exc:
            logger.warning("Failed to load project %s: %s", project_id, exc)
            return None

    def find_all(self) -> list[Project]:
        """Load all project JSON files from the storage directory."""
        projects: list[Project] = []
        for path in self._base_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                projects.append(Project.from_storage_dict(data))
            except Exception as exc:
                logger.warning("Skipping unreadable project file %s: %s", path, exc)
        return projects

    def update(self, *, project: Project) -> Project:
        """Overwrite an existing project file."""
        return self.save(project=project)

    def delete(self, *, project_id: str) -> bool:
        """Delete a project file. Returns False if it does not exist."""
        path = self._file_path(project_id)
        if not path.exists():
            return False
        path.unlink()
        # Remove stale lock file if present
        lock = Path(self._lock_path(project_id))
        if lock.exists():
            lock.unlink(missing_ok=True)
        logger.info("Deleted project %s", project_id)
        return True

    def exists(self, *, project_id: str) -> bool:
        """Return True if a JSON file exists for the given project_id."""
        return self._file_path(project_id).exists()

    def exists_by_name(self, *, name: str) -> bool:
        """Scan all projects and return True if any has the given name."""
        return any(p.name == name for p in self.find_all())
