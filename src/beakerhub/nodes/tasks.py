"""
Kubernetes Job management for node image tasks.

Creates and monitors K8s Jobs that run commands against node images
(e.g., `beaker context dump` for importing context data).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import uuid4

from kubernetes import client as k8s_client
from kubernetes import config as k8s_config

if TYPE_CHECKING:
    from beakerhub.app import BeakerHub
    from beakerhub.orm import NodeImages

log = logging.getLogger(__name__)


def _get_k8s_clients(namespace: str) -> tuple[k8s_client.BatchV1Api, k8s_client.CoreV1Api, str]:
    """Load in-cluster config and return batch + core API clients."""
    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()
    return k8s_client.BatchV1Api(), k8s_client.CoreV1Api(), namespace


def create_import_job(
    app: BeakerHub,
    node_image: NodeImages,
    callback_url: str,
    callback_token: str,
    namespace: str = "beakerhub",
) -> str:
    """
    Create a K8s Job that runs `beaker context dump` on the given node image
    and reports results back to the hub via the reporter container.

    Args:
        app: The BeakerHub application instance (for task configuration).
        node_image: The NodeImages record to import from.
        callback_url: The URL the reporter will POST results to.
        callback_token: Auth token for the reporter callback.
        namespace: K8s namespace to create the Job in.

    Returns:
        The Job name.
    """
    batch_api, _, _ = _get_k8s_clients(namespace)

    job_name = f"node-import-{node_image.slug}-{uuid4().hex[:8]}"
    node_image_ref = node_image.default_img_string
    output_volume_name = "task-output"
    stdout_path = "/output/stdout"
    stderr_path = "/output/stderr"

    # Init container: run the node image to dump context data
    init_container = k8s_client.V1Container(
        name="context-dump",
        image=node_image_ref,
        command=["sh", "-c", f"beaker context dump > {stdout_path} 2> {stderr_path}"],
        volume_mounts=[
            k8s_client.V1VolumeMount(
                name=output_volume_name,
                mount_path="/output",
            )
        ],
        resources=_build_resource_requirements(app.task_node_image_resources),
    )

    # Main container: reporter reads output and POSTs to callback
    reporter_container = k8s_client.V1Container(
        name="reporter",
        image=app.task_reporter_image,
        image_pull_policy=app.task_reporter_pull_policy,
        env=[
            k8s_client.V1EnvVar(name="CALLBACK_URL", value=callback_url),
            k8s_client.V1EnvVar(name="CALLBACK_TOKEN", value=callback_token),
            k8s_client.V1EnvVar(name="STDOUT_PATH", value=stdout_path),
            k8s_client.V1EnvVar(name="STDERR_PATH", value=stderr_path),
        ],
        volume_mounts=[
            k8s_client.V1VolumeMount(
                name=output_volume_name,
                mount_path="/output",
            )
        ],
        resources=_build_resource_requirements(app.task_reporter_resources),
    )

    # Pod spec
    pod_spec = k8s_client.V1PodSpec(
        init_containers=[init_container],
        containers=[reporter_container],
        volumes=[
            k8s_client.V1Volume(
                name=output_volume_name,
                empty_dir=k8s_client.V1EmptyDirVolumeSource(),
            )
        ],
        restart_policy="Never",
        node_selector=app.task_node_selector or None,
        tolerations=[
            k8s_client.V1Toleration(**t) for t in app.task_tolerations
        ] if app.task_tolerations else None,
    )

    # Job spec
    job = k8s_client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=k8s_client.V1ObjectMeta(
            name=job_name,
            namespace=namespace,
            labels={
                "app.kubernetes.io/name": "beakerhub",
                "app.kubernetes.io/component": "node-image-task",
                "beakerhub/task-type": "context-import",
                "beakerhub/node-image": node_image.slug,
            },
        ),
        spec=k8s_client.V1JobSpec(
            template=k8s_client.V1PodTemplateSpec(
                metadata=k8s_client.V1ObjectMeta(
                    labels={
                        "app.kubernetes.io/name": "beakerhub",
                        "app.kubernetes.io/component": "node-image-task",
                    },
                ),
                spec=pod_spec,
            ),
            backoff_limit=app.task_backoff_limit,
            active_deadline_seconds=app.task_active_deadline_seconds,
            ttl_seconds_after_finished=app.task_ttl_seconds_after_finished,
        ),
    )

    batch_api.create_namespaced_job(namespace=namespace, body=job)
    log.info(f"Created import job {job_name} for node image {node_image.slug}")
    return job_name


def get_job_status(job_name: str, namespace: str = "beakerhub") -> dict:
    """
    Query the status of a K8s Job.

    Returns a dict with:
        status: "pending" | "running" | "completed" | "failed"
        message: Human-readable status message
    """
    batch_api, core_api, _ = _get_k8s_clients(namespace)

    try:
        job = batch_api.read_namespaced_job(name=job_name, namespace=namespace)
    except k8s_client.ApiException as e:
        if e.status == 404:
            return {"status": "failed", "message": f"Job {job_name} not found"}
        raise

    status = job.status
    if status.succeeded and status.succeeded > 0:
        return {"status": "completed", "message": "Job completed successfully"}

    if status.failed and status.failed > 0:
        message = _get_job_failure_message(core_api, job_name, namespace)
        return {"status": "failed", "message": message}

    if status.active and status.active > 0:
        return {"status": "running", "message": "Job is running"}

    return {"status": "pending", "message": "Job is pending"}


def _get_job_failure_message(
    core_api: k8s_client.CoreV1Api,
    job_name: str,
    namespace: str,
) -> str:
    """Extract a useful error message from a failed Job's Pod events/status."""
    try:
        pods = core_api.list_namespaced_pod(
            namespace=namespace,
            label_selector=f"job-name={job_name}",
        )
    except k8s_client.ApiException:
        return "Job failed (could not retrieve pod details)"

    if not pods.items:
        return "Job failed (no pods found)"

    pod = pods.items[0]

    # Check init container statuses first (where context-dump runs)
    for cs in (pod.status.init_container_statuses or []):
        if cs.state and cs.state.waiting:
            reason = cs.state.waiting.reason or "Unknown"
            msg = cs.state.waiting.message or ""
            return f"Init container '{cs.name}' waiting: {reason}. {msg}".strip()
        if cs.state and cs.state.terminated and cs.state.terminated.exit_code != 0:
            reason = cs.state.terminated.reason or "Error"
            msg = cs.state.terminated.message or ""
            return f"Init container '{cs.name}' failed ({reason}, exit code {cs.state.terminated.exit_code}). {msg}".strip()

    # Check main container statuses
    for cs in (pod.status.container_statuses or []):
        if cs.state and cs.state.waiting:
            reason = cs.state.waiting.reason or "Unknown"
            msg = cs.state.waiting.message or ""
            return f"Container '{cs.name}' waiting: {reason}. {msg}".strip()
        if cs.state and cs.state.terminated and cs.state.terminated.exit_code != 0:
            reason = cs.state.terminated.reason or "Error"
            msg = cs.state.terminated.message or ""
            return f"Container '{cs.name}' failed ({reason}, exit code {cs.state.terminated.exit_code}). {msg}".strip()

    # Fallback: check pod-level conditions
    phase = pod.status.phase or "Unknown"
    reason = pod.status.reason or ""
    return f"Job failed (pod phase: {phase}). {reason}".strip()


def delete_job(job_name: str, namespace: str = "beakerhub") -> None:
    """Delete a Job and its associated Pods."""
    batch_api, _, _ = _get_k8s_clients(namespace)
    try:
        batch_api.delete_namespaced_job(
            name=job_name,
            namespace=namespace,
            body=k8s_client.V1DeleteOptions(
                propagation_policy="Background",
            ),
        )
    except k8s_client.ApiException as e:
        if e.status != 404:
            raise


def _build_resource_requirements(
    resources: dict,
) -> k8s_client.V1ResourceRequirements | None:
    """Convert a resource dict from config into a K8s ResourceRequirements object."""
    if not resources:
        return None
    return k8s_client.V1ResourceRequirements(
        requests=resources.get("requests"),
        limits=resources.get("limits"),
    )
