"""Request and response DTOs for event-to-flow mapping management."""

from pydantic import BaseModel, ConfigDict, Field

from docpipe.core.event_streaming.models import ROUTING_KEY_PATTERN


class EventMappingDTO(BaseModel):
    """Create or return an event routing mapping."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(
        pattern=ROUTING_KEY_PATTERN,
        description=("Case-insensitive routing key containing only ASCII letters, digits, hyphens, and underscores."),
        examples=["tenant-a_invoices-updated"],
    )
    flow_id: str = Field(
        min_length=1,
        description="Identifier of an existing flow",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )


class EventMappingUpdateRequest(BaseModel):
    """Request body for changing the flow assigned to an existing key."""

    model_config = ConfigDict(extra="forbid")

    flow_id: str = Field(
        min_length=1,
        description="Identifier of an existing flow",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
