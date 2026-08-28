"""Pytest fixtures for projects unit tests."""

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from docpipe.core.assets.common.domain.ports.asset_repository import AssetRepository
from docpipe.core.assets.flows.application.services.flow_service import FlowService
from docpipe.core.assets.flows.domain.models.flow import Flow
from docpipe.core.job_management.domain.ports.job_stats_service import JobStatsService
from docpipe.core.projects.domain.models.project import Project
from docpipe.core.projects.domain.ports.project_repository import ProjectRepository


@pytest.fixture
def sample_project() -> Project:
    """A minimal valid Project with a fixed project_id."""
    return Project(
        project_id="proj-001",
        name="Alpha Project",
        description="First test project",
        tags=["research", "nlp"],
        created_on=datetime(2024, 6, 1, 10, 0, 0, tzinfo=UTC),
        modified_on=datetime(2024, 6, 1, 10, 0, 0, tzinfo=UTC),
        created_by="alice",
    )


@pytest.fixture
def another_project() -> Project:
    """A second Project with a different ID and name."""
    return Project(
        project_id="proj-002",
        name="Beta Project",
        description="Second test project",
        tags=["analytics"],
        created_on=datetime(2024, 6, 2, 8, 0, 0, tzinfo=UTC),
        modified_on=datetime(2024, 6, 2, 8, 0, 0, tzinfo=UTC),
        created_by="bob",
    )


@pytest.fixture
def multiple_projects(sample_project, another_project) -> list[Project]:
    """A list of sample projects for list/filter tests."""
    third = Project(
        project_id="proj-003",
        name="Gamma Project",
        description="Third test project",
        tags=["research"],
        created_by="carol",
    )
    return [sample_project, another_project, third]


@pytest.fixture
def mock_project_repository() -> Mock:
    """Mock ProjectRepository with safe defaults."""
    repo = Mock(spec=ProjectRepository)
    repo.save.return_value = None  # set per test
    repo.get.return_value = None
    repo.find_all.return_value = []
    repo.update.return_value = None
    repo.delete.return_value = True
    repo.exists.return_value = False
    repo.exists_by_name.return_value = False
    return repo


@pytest.fixture
def mock_flow_repository() -> Mock:
    """Mock AssetRepository[Flow] with no flows by default."""
    repo = Mock(spec=AssetRepository[Flow])
    repo.find_all.return_value = []
    return repo


@pytest.fixture
def mock_flow_service() -> Mock:
    """Mock FlowService for cascade-delete testing."""
    svc = Mock(spec=FlowService)
    svc.bulk_delete_flows.return_value = {
        "deleted": [],
        "failed": [],
        "total_requested": 0,
        "total_deleted": 0,
        "total_failed": 0,
    }
    return svc


@pytest.fixture
def mock_job_stats_service() -> Mock:
    """Mock JobStatsService for ProjectService instantiation."""
    return Mock(spec=JobStatsService)


@pytest.fixture
def flow_for_project(sample_project) -> Flow:
    """A Flow whose container_id points to sample_project."""
    return Flow(
        asset_id="flow-aaa",
        name="Flow in Alpha",
        definition={"doc_type": "pipeline", "pipelines": []},
        container_kind="project",
        container_id=sample_project.project_id,
    )
