import os
from pathlib import Path
from typing import Tuple, Type, Optional, Union
import toml
from pydantic import Field
from pydantic_settings import (
    BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, TomlConfigSettingsSource
)

from datasift_opensource.backend.common.models.request_model import Cp4DAppConfig, CloudAppConfig, LocalAppConfig
from datasift_opensource.backend.common.util.constants import DatasiftConstants

CONFIG_DIR = str(Path(__file__).parent.parent.resolve())


def load_config_from_env():
    # Set common environment variables from Helm chart values
    # Map Helm chart environment variables to expected format
    # These are set in helm/datasift-api-chart/values.*.yaml files
    
    # Data folder configuration
    data_folder = os.getenv("datasift_api_data_folder", "/data")
    os.environ[DatasiftConstants.DATA_FOLDER] = data_folder


def get_config_file():
    """
    Get configuration file path. For local environment, load from TOML file.
    """

    # Local environment: use TOML file in the same directory as config.py
    relative_path = "/config/config_test.toml"
    config_file = CONFIG_DIR + relative_path
    if '.zip' in CONFIG_DIR:
        config_file = os.path.dirname(CONFIG_DIR) + relative_path

    # Load TOML and set environment variables for local
    data = toml.load(config_file)
    os.environ[DatasiftConstants.DATA_FOLDER] = data["app_config"]["data_folder"]
    if "operant_namespace" in data["app_config"]:
        os.environ[DatasiftConstants.OPERAND_NAMESPACE] = data["app_config"]["operand_namespace"]
    os.environ["TLS_PATH"] = data["app_config"]["tls_path"]
    os.environ[DatasiftConstants.WDU_SERVER] = data["app_config"]["cp4d_base_url"]
    os.environ["AUDIT_LOGGING"] = data["app_config"]["audit_logging"]
    os.environ["ENABLE_ATRACKER"] = data["app_config"]["at_tracker"]
    os.environ["WAREHOUSE_FOLDER"] = data["app_config"]["warehouse_folder"]
    os.environ[DatasiftConstants.WML_SERVER] = data["app_config"]["wml_server"]

    return config_file


class Settings(BaseSettings):
    
    model_config = SettingsConfigDict(toml_file=get_config_file() if get_config_file() else None)
    app_config: Union[Cp4DAppConfig, CloudAppConfig, LocalAppConfig]
    operand_namespace: Optional[str] = Field(default=None, validation_alias=DatasiftConstants.OPERAND_NAMESPACE)
    tls_path: str = Field(default="/tmp/tls", validation_alias="TLS_PATH")

    def __init__(self, **data):
        super().__init__(**data)


    @classmethod
    def settings_customise_sources(
            cls,
            settings_cls: Type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:

        # For local environment, use TOML file
        return (
            TomlConfigSettingsSource(settings_cls),
            env_settings,
            init_settings,
            dotenv_settings,
            file_secret_settings
        )


settings = Settings()
