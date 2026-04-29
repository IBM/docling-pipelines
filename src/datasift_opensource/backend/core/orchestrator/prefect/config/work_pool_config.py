"""
Typed work pool configuration models for Prefect batch execution.

These dataclasses model the work-pool-specific configuration currently supported
by this repository. They intentionally preserve the existing config surface
while making deployment parameter creation typed and maintainable.
"""

from dataclasses import dataclass, field, fields
from typing import Any

from core.orchestrator.prefect.domain.models import (
    BatchStrategyConstants,
    WorkPoolType,
)


@dataclass
class ProcessWorkPoolConfig:
    """
    Configuration for process work pools.

    Process work pools execute in the worker's local Python environment and do
    not require container images, but still need runtime environment variables
    for Prefect connectivity and Datasift dependency/config bootstrapping.

    Attributes:
        deployment_path: Runtime path where the flow entrypoint is available in
            the worker execution environment.  Defaults to ``None`` which tells
            the adapter to use ``os.getcwd()`` (correct when submitter and
            worker share the same filesystem, e.g. local dev).  Set this
            explicitly when the worker runs in a different filesystem context
            (e.g. Docker container where code lives at
            ``/app/src/datasift_opensource/backend``).
        env: Environment variables injected into the worker job process.
    """

    deployment_path: str | None = None
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class BaseContainerWorkPoolConfig:
    """
    Base configuration for container-based work pool types.

    Attributes:
        deployment_path: Runtime path where the flow entrypoint is available in
            the worker execution environment.
        image: Container image used by the worker job.
        env: Environment variables injected into the worker job container.
    """

    deployment_path: str = BatchStrategyConstants.DEFAULT_DEPLOYMENT_PATH
    image: str = "datasift-opensource:latest"
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class DockerWorkPoolConfig(BaseContainerWorkPoolConfig):
    """
    Configuration for Docker work pools.

    Attributes:
        image_pull_policy: Docker image pull policy override.
        networks: Optional Docker networks for spawned containers.
    """

    image_pull_policy: str = "Never"
    networks: list[str] | None = None


@dataclass
class KubernetesWorkPoolConfig(BaseContainerWorkPoolConfig):
    """
    Configuration for Kubernetes work pools.

    Attributes:
        image_pull_policy: Kubernetes image pull policy.
        namespace: Namespace used for job execution.
        service_account_name: Service account attached to job pods.
        finished_job_ttl: TTL in seconds for completed jobs.
        pod_watch_timeout_seconds: Timeout for pod watch operations.
        stream_output: Whether worker logs should be streamed.
        cpu_request: CPU request for the job container.
        cpu_limit: CPU limit for the job container.
        memory_request: Memory request for the job container.
        memory_limit: Memory limit for the job container.
        image_pull_secrets: List of secret names for pulling private container images.
    """

    image_pull_policy: str = "IfNotPresent"
    namespace: str = "datasift"
    service_account_name: str = "prefect-worker"
    finished_job_ttl: int = 60
    pod_watch_timeout_seconds: int = 300
    stream_output: bool = True
    cpu_request: str = "1000m"
    cpu_limit: str = "2000m"
    memory_request: str = "2Gi"
    memory_limit: str = "4Gi"
    image_pull_secrets: list[str] | None = None


@dataclass
class ECSWorkPoolConfig(BaseContainerWorkPoolConfig):
    """Configuration for ECS work pools currently supported by this repository."""


def _filter_config_for_dataclass(*, config_dict: dict[str, Any], config_cls: type) -> dict[str, Any]:
    """Filter raw config to the fields accepted by the target dataclass."""
    valid_field_names = {config_field.name for config_field in fields(config_cls)}
    return {key: value for key, value in config_dict.items() if key in valid_field_names}


def create_work_pool_config(
    *,
    work_pool_type: str,
    config_dict: dict[str, Any],
) -> ProcessWorkPoolConfig | BaseContainerWorkPoolConfig:
    """
    Create a typed work pool configuration from raw strategy config.

    Unknown keys are ignored to preserve compatibility with the broader strategy
    configuration, which also contains non-dataclass keys such as work pool
    name, deployment name, type, and batch storage settings.
    """
    config_class_map = {
        WorkPoolType.DOCKER.value: DockerWorkPoolConfig,
        WorkPoolType.KUBERNETES.value: KubernetesWorkPoolConfig,
        WorkPoolType.ECS.value: ECSWorkPoolConfig,
    }
    config_cls = config_class_map.get(work_pool_type, ProcessWorkPoolConfig)
    filtered_config = _filter_config_for_dataclass(
        config_dict=config_dict,
        config_cls=config_cls,
    )
    return config_cls(**filtered_config)
