from typing import Optional
from pydantic import BaseModel


class Cp4DAppConfig(BaseModel):
    name: str
    iam_public_key_url: str
    cp4d_base_url: str
    wml_url: str
    data_folder: str
    log_level: str
    local_mode: bool
    datasift_postgres_host: str
    datasift_postgres_port: int
    datasift_postgres_database: str
    datasift_postgres_user: str
    datasift_postgres_password: str


class CloudAppConfig(BaseModel):
    name: str
    iam_public_key_url: str
    cp4d_base_url: str
    wml_url: str
    resource_controller_url: str
    flight_url: Optional[str]
    data_folder: str
    log_level: str
    local_mode: bool

class LocalAppConfig(BaseModel):
    name: str
    iam_public_key_url: str
    cp4d_base_url: str
    wml_url: str
    data_folder: str
    log_level: str
    local_mode: bool
    audit_logging: str
    test_cp4d_base_url: str
    test_cp4d_project_id: str
    test_cp4d_catalog_id: str
    test_cp4d_asset_ids: list
    test_cp4d_flow_id: str
    test_cp4d_s3_connection_id: str
    test_cp4d_milvus_connection_id: str
    test_cp4d_es_connection_id: str
    test_cp4d_presto_connection_id: str
    test_cp4d_document_library_id: str
    datasift_postgres_host: str
    datasift_postgres_port: int
    datasift_postgres_database: str
    datasift_postgres_user: str
    datasift_postgres_password: str


class ConfigParam:
    name: str
    type: str
    mandatory: bool
