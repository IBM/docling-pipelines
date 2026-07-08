"""Integration test for LocalAssetRepository with existing LocalFlowRepository.

This test verifies that the new unified architecture correctly wraps and delegates
to the existing LocalFlowRepository, ensuring backward compatibility and proper
data flow.
"""

from uuid import uuid4

import pytest

from docpipe.core.assets.common.adapters.repositories.local_asset_repository import LocalAssetRepository
from docpipe.core.assets.flows.domain.models.flow import Flow


class TestLocalAssetRepositoryIntegration:
    """Test LocalAssetRepository integration with LocalFlowRepository."""

    @pytest.fixture
    def temp_storage(self, tmp_path):
        """Create temporary storage directory for test isolation."""
        storage_path = tmp_path / "test_assets"
        storage_path.mkdir(parents=True, exist_ok=True)
        return str(storage_path)

    @pytest.fixture
    def repo(self, temp_storage):
        """Create LocalAssetRepository with temp storage."""
        return LocalAssetRepository(asset_type=Flow, storage_path=temp_storage)

    def test_create_and_retrieve_flow(self, repo):
        """Test creating and retrieving a Flow through LocalAssetRepository."""

        # Create a Flow
        flow = Flow(
            name="test_flow",
            description="Test flow for integration",
            definition={
                "doc_type": "pipeline",
                "version": "3.0",
                "id": str(uuid4()),
                "primary_pipeline": str(uuid4()),
                "pipelines": [],
                "schemas": [],
            },
            tags=["test", "integration"],
        )

        # Save flow
        saved_flow = repo.save(asset=flow)

        # Verify flow was saved
        assert saved_flow.asset_id is not None
        assert saved_flow.name == "test_flow"
        assert saved_flow.description == "Test flow for integration"
        assert "test" in saved_flow.tags

        # Retrieve flow by ID
        retrieved_flow = repo.find_by_id(asset_id=saved_flow.asset_id)
        assert retrieved_flow is not None
        assert retrieved_flow.asset_id == saved_flow.asset_id
        assert retrieved_flow.name == saved_flow.name

        # Retrieve flow by name
        retrieved_by_name = repo.find_by_name(name="test_flow")
        assert retrieved_by_name is not None
        assert retrieved_by_name.asset_id == saved_flow.asset_id

        # Clean up
        repo.delete(asset_id=saved_flow.asset_id)

    def test_list_flows(self, repo):
        """Test listing flows through LocalAssetRepository."""

        # Create multiple flows
        flows = []
        for i in range(3):
            flow = Flow(
                name=f"test_flow_{i}",
                description=f"Test flow {i}",
                definition={
                    "doc_type": "pipeline",
                    "version": "3.0",
                    "id": str(uuid4()),
                    "primary_pipeline": str(uuid4()),
                    "pipelines": [],
                    "schemas": [],
                },
                tags=["test"],
            )
            saved_flow = repo.save(asset=flow)
            flows.append(saved_flow)

        # List all flows
        all_flows = repo.find_all()
        assert len(all_flows) >= 3

        # Verify our flows are in the list
        flow_names = [f.name for f in all_flows]
        for i in range(3):
            assert f"test_flow_{i}" in flow_names

        # Clean up
        for flow in flows:
            repo.delete(asset_id=flow.asset_id)

    def test_update_flow(self, repo):
        """Test updating a flow through LocalAssetRepository."""

        # Create flow
        flow = Flow(
            name="test_flow_update",
            description="Original description",
            definition={
                "doc_type": "pipeline",
                "version": "3.0",
                "id": str(uuid4()),
                "primary_pipeline": str(uuid4()),
                "pipelines": [],
                "schemas": [],
            },
        )
        saved_flow = repo.save(asset=flow)
        assert saved_flow.asset_id is not None

        # Update flow
        saved_flow.description = "Updated description"
        saved_flow.tags.append("updated")
        updated_flow = repo.update(asset=saved_flow)

        # Verify update
        assert updated_flow.description == "Updated description"
        assert "updated" in updated_flow.tags

        # Retrieve and verify
        retrieved_flow = repo.find_by_id(asset_id=saved_flow.asset_id)
        assert retrieved_flow is not None
        assert retrieved_flow.description == "Updated description"
        assert "updated" in retrieved_flow.tags

        # Clean up
        repo.delete(asset_id=saved_flow.asset_id)

    def test_exists_checks(self, repo):
        """Test existence checks through LocalAssetRepository."""

        # Create flow
        flow = Flow(
            name="test_flow_exists",
            description="Test existence checks",
            definition={
                "doc_type": "pipeline",
                "version": "3.0",
                "id": str(uuid4()),
                "primary_pipeline": str(uuid4()),
                "pipelines": [],
                "schemas": [],
            },
        )
        saved_flow = repo.save(asset=flow)
        assert saved_flow.asset_id is not None

        # Test exists by ID
        assert repo.exists(asset_id=saved_flow.asset_id) is True
        assert repo.exists(asset_id="nonexistent-id") is False

        # Test exists by name
        assert repo.exists_by_name(name="test_flow_exists") is True
        assert repo.exists_by_name(name="nonexistent_flow") is False

        # Clean up
        repo.delete(asset_id=saved_flow.asset_id)

    def test_search_flows(self, repo):
        """Test searching flows through LocalAssetRepository."""

        # Create flows with searchable content
        flows = []
        for i in range(2):
            flow = Flow(
                name=f"searchable_flow_{i}",
                description="This flow is searchable",
                definition={
                    "doc_type": "pipeline",
                    "version": "3.0",
                    "id": str(uuid4()),
                    "primary_pipeline": str(uuid4()),
                    "pipelines": [],
                    "schemas": [],
                },
            )
            saved_flow = repo.save(asset=flow)
            flows.append(saved_flow)

        # Search by finding all and filtering (search method not implemented yet)
        all_flows = repo.find_all()
        results = [f for f in all_flows if "searchable" in f.name.lower()]
        assert len(results) >= 2

        # Verify search results
        result_names = [f.name for f in results]
        assert "searchable_flow_0" in result_names
        assert "searchable_flow_1" in result_names

        # Clean up
        for flow in flows:
            repo.delete(asset_id=flow.asset_id)

    def test_health_check(self, repo):
        """Test health check through LocalAssetRepository."""

        # Perform health check
        health = repo.health_check()

        # Verify health check response
        assert health["status"] == "healthy"
        assert "storage_path" in health
        assert "storage_exists" in health
        assert "storage_writable" in health
        assert "asset_count" in health
