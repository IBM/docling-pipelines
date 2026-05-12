"""Flow DTO to Domain model mapper.

This module provides conversion between DTOs (Data Transfer Objects) and domain models
following hexagonal architecture principles. Mappers belong in the adapter layer,
keeping the router thin and focused on HTTP concerns.
"""

from uuid import uuid4

from datasift.api.dto.flow_dto import FlowCreateRequest, FlowResponse
from datasift.core.assets.flows.domain.models.flow import Flow
from datasift.exceptions.datasift_exceptions import FlowInvalidDataException


class FlowMapper:
    """Mapper for converting between Flow DTOs and domain models.

    This class provides static methods for bidirectional conversion between:
    - FlowCreateRequest DTO (API request) ↔ Flow domain model
    - FlowUpdateRequest DTO (API request) → Flow domain model updates
    - Flow domain model ↔ FlowResponse DTO (API response)

    Benefits:
    - Single Responsibility: Conversion logic separated from routing
    - Reusability: Can be used by multiple adapters (REST API, CLI, GraphQL)
    - Testability: Can be unit tested independently
    - Maintainability: All conversion logic in one place
    """

    @staticmethod
    def create_request_to_domain(dto: FlowCreateRequest) -> Flow:
        """Convert FlowCreateRequest DTO to Flow domain model.

        Args:
            dto: FlowCreateRequest DTO from API request

        Returns:
            Flow domain model with all fields mapped and defaults applied

        Notes:
            When the request omits ``definition``, this method creates a minimal
            Elyra-style pipeline definition. The generated ``definition["id"]`` and
            pipeline ``id`` values are internal identifiers required by that
            structure and are distinct from the persisted domain ``Flow.flow_id``.

        Example:
            >>> dto = FlowCreateRequest(
            ...     name="My Flow",
            ...     definition={"doc_type": "pipeline", "pipelines": []}
            ... )
            >>> domain = FlowMapper.create_request_to_domain(dto)
            >>> isinstance(domain, Flow)
            True
        """
        # Generate a minimal Elyra-style definition when the client does not supply one.
        # The generated IDs below belong to the definition payload only; the persisted
        # Flow.flow_id is still generated separately by Flow.__post_init__.
        definition = dto.definition
        if definition is None:
            definition_id = str(uuid4())
            primary_pipeline_id = str(uuid4())
            definition = {
                "doc_type": "pipeline",
                "version": "3.0",
                "json_schema": "https://api.dataplatform.ibm.com/schemas/common-pipeline/pipeline-flow/pipeline-flow-v3-schema.json",
                "id": definition_id,
                "primary_pipeline": primary_pipeline_id,
                "pipelines": [
                    {
                        "id": primary_pipeline_id,
                        "nodes": [],
                        "app_data": {
                            "ds_flow": {
                                "name": dto.name,
                                "description": dto.description or "",
                                "job_name": f"{dto.name} Job",
                                "schedule": {},
                                "global_config": {
                                    "doc_column": "content",
                                    "data_storage_type": "local",
                                    "disable_validation": False,
                                },
                            },
                            "ui_data": {"comments": []},
                        },
                        "runtime_ref": "",
                    }
                ],
                "schemas": [],
            }

        return Flow(
            flow_id=None,  # Will be generated in Flow.__post_init__
            container_kind=dto.container_kind,
            container_id=dto.container_id,
            name=dto.name,
            description=dto.description,
            definition=definition,
            tags=dto.tags or [],
            is_hidden=dto.is_hidden if dto.is_hidden is not None else False,
            flow_version=dto.flow_version or "2.0",
            created_on=None,  # Will be set in Flow.__post_init__
            modified_on=None,  # Will be set in Flow.__post_init__
            job_id=dto.job_id,
            created_by=dto.created_by,
            modified_by=None,
            href=None,
        )

    @staticmethod
    def domain_to_dto(domain: Flow) -> FlowResponse:
        """Convert Flow domain model to FlowResponse DTO.

        Validates that required fields are present before conversion. The Flow domain
        model should guarantee these fields are set after __post_init__, but this
        validation provides an additional safety check.

        Args:
            domain: Flow domain model with all required fields populated

        Returns:
            FlowResponse DTO for API response

        Raises:
            FlowInvalidDataException: If domain model has missing required fields
                (flow_id, created_on, or modified_on). This indicates a programming
                error in the domain model initialization.

        Example:
            >>> domain = Flow(
            ...     container_kind="project",
            ...     container_id="550e8400-e29b-41d4-a716-446655440000",
            ...     name="My Flow",
            ...     definition={"doc_type": "pipeline", "pipelines": []}
            ... )
            >>> dto = FlowMapper.domain_to_dto(domain)
            >>> isinstance(dto, FlowResponse)
            True
        """
        # Validate required fields are present
        # Domain model guarantees these are set after __post_init__, but validate anyway
        if domain.flow_id is None or domain.created_on is None or domain.modified_on is None:
            raise FlowInvalidDataException(
                message="Flow domain model has missing required fields (flow_id, created_on, or modified_on)",
                field_name="flow_id"
                if domain.flow_id is None
                else ("created_on" if domain.created_on is None else "modified_on"),
            )

        return FlowResponse(
            flow_id=domain.flow_id,
            container_kind=domain.container_kind,
            container_id=domain.container_id,
            name=domain.name,
            description=domain.description,
            definition=domain.definition,
            tags=domain.tags,
            is_hidden=domain.is_hidden if domain.is_hidden is not None else False,
            flow_version=domain.flow_version or "2.0",
            created_on=domain.created_on,
            modified_on=domain.modified_on,
            job_id=domain.job_id,
            created_by=domain.created_by,
            modified_by=domain.modified_by,
            href=domain.href,
        )
