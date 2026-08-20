"""Pydantic config model for the Milvus vector store adapter."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ADAPTER_NAME = "milvus"


class MilvusConfig(BaseModel):
    """User-facing configuration for the Milvus vector store adapter.

    Describes the fields the user writes inside ``provider_config`` when
    selecting the ``milvus`` provider in a VectorDB operator node.
    """

    model_config = ConfigDict(extra="ignore")

    collection_name: str = Field(
        description="Name of the Milvus collection to write to.",
    )
    host: str = Field(
        default="localhost",
        description="Milvus server hostname or IP address.",
    )
    port: int = Field(
        default=19530,
        description="Milvus server port.",
    )
    uri: str | None = Field(
        default=None,
        description="Full connection URI (e.g. https://xxx.zillizcloud.com). Takes precedence over host/port when provided.",
    )
    token: str | None = Field(
        default=None,
        description="API token for Milvus cloud or wx.data deployments.",
    )
    username: str | None = Field(
        default=None,
        description="Username for password-based authentication.",
    )
    password: str | None = Field(
        default=None,
        description="Password for password-based authentication.",
    )
    database: str = Field(
        default="default",
        description="Milvus database name.",
    )
    auth_type: str | None = Field(
        default=None,
        description="Authentication type override (e.g. 'wx.data'). Leave unset for standard Milvus auth.",
    )
    secure: bool = Field(
        default=False,
        description="Whether to use a TLS/SSL connection.",
    )
    batch_size: int = Field(
        default=100,
        description="Number of documents to insert per batch.",
    )
    index_type: Literal[
        "FLAT",
        "IVF_FLAT",
        "IVF_SQ8",
        "IVF_PQ",
        "HNSW",
        "DISKANN",
        "AUTOINDEX",
        "SPARSE_INVERTED_INDEX",
        "SPARSE_WAND",
    ] = Field(
        default="HNSW",
        description="Vector index algorithm.",
    )
    metric_type: Literal["L2", "IP", "COSINE", "BM25"] = Field(
        default="L2",
        description="Vector similarity metric.",
    )
    index_parameters: dict = Field(
        default_factory=dict,
        description='Index-specific parameters (e.g. {"M": 16, "efConstruction": 256} for HNSW).',
    )
    add_sparse_vector: bool = Field(
        default=False,
        description="Enable sparse vector support using BM25. When true, a sparse vector field and BM25 function are added alongside dense vectors.",
    )
