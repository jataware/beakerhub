"""Admin dashboard API handlers for BeakerHub.

Provides aggregated summary statistics and optional Kubernetes cluster
information for the admin dashboard page.
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from tornado import web
from jupyterhub.apihandlers import APIHandler
from jupyterhub.scopes import needs_scope
from jupyterhub.orm import User, Spawner
from sqlalchemy import func

from beakerhub import __version__
from beakerhub.orm import (
    BeakerSession,
    Context,
    Integration,
    Language,
    NodeImages,
    NodeImageTask,
    NodeSecret,
    Workflow,
)

log = logging.getLogger(__name__)


class AdminDashboardSummaryHandler(APIHandler):
    """Aggregated counts and summary statistics for the admin dashboard."""

    def compute_etag(self) -> None:
        return None

    @needs_scope('admin:users')
    async def get(self):
        db = self.db

        # Entity counts
        images_total = db.query(func.count(NodeImages.id)).scalar() or 0
        images_enabled = db.query(func.count(NodeImages.id)).filter(
            NodeImages.enabled == True
        ).scalar() or 0

        contexts_total = db.query(func.count(Context.id)).scalar() or 0
        contexts_enabled = db.query(func.count(Context.id)).filter(
            Context.enabled == True
        ).scalar() or 0

        workflows_total = db.query(func.count(Workflow.id)).scalar() or 0
        workflows_enabled = db.query(func.count(Workflow.id)).filter(
            Workflow.enabled == True
        ).scalar() or 0

        integrations_total = db.query(func.count(Integration.id)).scalar() or 0
        integrations_enabled = db.query(func.count(Integration.id)).filter(
            Integration.enabled == True
        ).scalar() or 0

        languages_total = db.query(func.count(Language.slug)).scalar() or 0

        secrets_total = db.query(func.count(NodeSecret.id)).scalar() or 0
        secrets_global = db.query(func.count(NodeSecret.id)).filter(
            NodeSecret.node_image_id.is_(None)
        ).scalar() or 0

        # User counts
        users_total = db.query(func.count(User.id)).scalar() or 0
        users_admin = db.query(func.count(User.id)).filter(
            User.admin == True
        ).scalar() or 0

        # Active sessions: JupyterHub spawners with a server_id (meaning running)
        active_servers = db.query(func.count(Spawner.id)).filter(
            Spawner.server_id.isnot(None)
        ).scalar() or 0

        # BeakerSession counts (historical)
        beaker_sessions_total = db.query(func.count(BeakerSession.id)).scalar() or 0

        # Recent import tasks (last 5)
        recent_tasks = db.query(NodeImageTask).join(
            NodeImages, NodeImageTask.node_image_id == NodeImages.id
        ).order_by(
            NodeImageTask.updated_at.desc()
        ).limit(5).all()

        recent_imports = []
        for task in recent_tasks:
            recent_imports.append({
                "task_id": task.id,
                "node_image_slug": task.node_image.slug if task.node_image else None,
                "task_type": task.task_type,
                "status": task.status,
                "job_name": task.job_name,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                "error": task.error,
                "result": task.result,
            })

        result = {
            "app_version": __version__,
            "counts": {
                "images": {"total": images_total, "enabled": images_enabled},
                "contexts": {"total": contexts_total, "enabled": contexts_enabled},
                "workflows": {"total": workflows_total, "enabled": workflows_enabled},
                "integrations": {"total": integrations_total, "enabled": integrations_enabled},
                "languages": {"total": languages_total},
                "secrets": {"total": secrets_total, "global": secrets_global, "per_node": secrets_total - secrets_global},
                "users": {"total": users_total, "admin": users_admin},
                "sessions": {
                    "active_servers": active_servers,
                    "beaker_sessions_total": beaker_sessions_total,
                },
            },
            "recent_imports": recent_imports,
        }

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))


class AdminDashboardClusterHandler(APIHandler):
    """Kubernetes cluster information for the admin dashboard.

    Queries the K8s API for pod, PVC, event, and job information.
    Returns available: false if K8s access is not available.
    """

    def compute_etag(self) -> None:
        return None

    @needs_scope('admin:users')
    async def get(self):
        try:
            result = self._get_cluster_info()
        except Exception as e:
            log.warning(f"Failed to fetch K8s cluster info: {e}")
            result = {
                "available": False,
                "error": str(e),
            }

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))

    def _get_cluster_info(self) -> dict[str, Any]:
        from kubernetes import client as k8s_client
        from kubernetes import config as k8s_config

        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            try:
                k8s_config.load_kube_config()
            except k8s_config.ConfigException:
                return {"available": False, "error": "No K8s configuration found"}

        core_api = k8s_client.CoreV1Api()
        batch_api = k8s_client.BatchV1Api()

        app = self.settings.get("app")
        namespace = getattr(app, "task_namespace", "beakerhub")

        # Pods
        pods_result = self._get_pod_info(core_api, namespace)

        # PVCs
        pvcs_result = self._get_pvc_info(core_api, namespace)

        # Jobs
        jobs_result = self._get_job_info(batch_api, namespace)

        # Recent warning events (last hour)
        events_result = self._get_recent_events(core_api, namespace)

        # Cluster nodes (cluster-scoped — requires ClusterRole)
        nodes_result = self._get_node_info(core_api)

        # Helm releases (stored as secrets with owner=helm label)
        helm_result = self._get_helm_releases(core_api, namespace)

        return {
            "available": True,
            "namespace": namespace,
            "pods": pods_result,
            "pvcs": pvcs_result,
            "jobs": jobs_result,
            "events": events_result,
            "nodes": nodes_result,
            "helm_releases": helm_result,
        }

    def _get_pod_info(self, core_api, namespace: str) -> dict[str, Any]:
        try:
            pods = core_api.list_namespaced_pod(namespace=namespace)
        except Exception as e:
            return {"error": str(e)}

        total = len(pods.items)
        by_phase: dict[str, int] = {}
        by_component: dict[str, dict[str, Any]] = {}

        for pod in pods.items:
            phase = pod.status.phase or "Unknown"
            by_phase[phase] = by_phase.get(phase, 0) + 1

            # Determine component from labels
            labels = pod.metadata.labels or {}
            component = labels.get(
                "app.kubernetes.io/component",
                labels.get("component", "other")
            )
            # Detect notebook pods by JupyterHub labels or pod name prefix
            if labels.get("component") == "singleuser-server" or (
                pod.metadata.name and pod.metadata.name.startswith("session-")
            ):
                component = "notebook"
            elif "hub" in (pod.metadata.name or ""):
                component = "hub"
            elif "proxy" in (pod.metadata.name or ""):
                component = "proxy"

            if component not in by_component:
                by_component[component] = {"count": 0, "phases": {}}
            by_component[component]["count"] += 1
            phases = by_component[component]["phases"]
            phases[phase] = phases.get(phase, 0) + 1

        return {
            "total": total,
            "by_phase": by_phase,
            "by_component": by_component,
        }

    def _get_pvc_info(self, core_api, namespace: str) -> list[dict[str, Any]]:
        try:
            pvcs = core_api.list_namespaced_persistent_volume_claim(namespace=namespace)
        except Exception as e:
            return [{"error": str(e)}]

        result = []
        for pvc in pvcs.items:
            capacity = None
            if pvc.status.capacity:
                capacity = pvc.status.capacity.get("storage")
            result.append({
                "name": pvc.metadata.name,
                "capacity": capacity,
                "phase": pvc.status.phase,
                "storage_class": pvc.spec.storage_class_name,
            })
        return result

    def _get_job_info(self, batch_api, namespace: str) -> dict[str, Any]:
        try:
            jobs = batch_api.list_namespaced_job(
                namespace=namespace,
                label_selector="app.kubernetes.io/name=beakerhub",
            )
        except Exception as e:
            return {"error": str(e)}

        active = 0
        succeeded = 0
        failed = 0
        for job in jobs.items:
            if job.status.active:
                active += job.status.active
            if job.status.succeeded:
                succeeded += job.status.succeeded
            if job.status.failed:
                failed += job.status.failed

        return {
            "total": len(jobs.items),
            "active": active,
            "succeeded": succeeded,
            "failed": failed,
        }

    def _get_recent_events(self, core_api, namespace: str) -> list[dict[str, Any]]:
        try:
            events = core_api.list_namespaced_event(namespace=namespace)
        except Exception as e:
            return [{"error": str(e)}]

        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        recent = []
        for event in events.items:
            last_ts = event.last_timestamp
            if last_ts and last_ts.replace(tzinfo=timezone.utc) < cutoff:
                continue
            if event.type != "Warning":
                continue
            recent.append({
                "type": event.type,
                "reason": event.reason,
                "message": event.message,
                "involved_object": event.involved_object.name if event.involved_object else None,
                "last_timestamp": last_ts.isoformat() if last_ts else None,
                "count": event.count,
            })

        # Sort by most recent first, limit to 20
        recent.sort(key=lambda e: e.get("last_timestamp") or "", reverse=True)
        return recent[:20]

    def _get_node_info(self, core_api) -> list[dict[str, Any]]:
        """Get cluster node information including capacity, allocatable, and allocated.

        This requires cluster-scoped permissions (ClusterRole).
        Returns an empty list with an error key if access is denied.
        """
        try:
            nodes = core_api.list_node()
        except Exception as e:
            log.debug(f"Cannot list cluster nodes (likely missing ClusterRole): {e}")
            return [{"error": str(e)}]

        # Get per-node allocated resources by summing pod resource requests
        allocated_by_node = self._get_allocated_by_node(core_api)

        result = []
        for node in nodes.items:
            labels = node.metadata.labels or {}
            capacity = node.status.capacity or {}
            allocatable = node.status.allocatable or {}

            # Determine node readiness
            ready = False
            conditions_summary = []
            for cond in (node.status.conditions or []):
                if cond.type == "Ready":
                    ready = cond.status == "True"
                if cond.status == "True" and cond.type != "Ready":
                    conditions_summary.append(cond.type)
                elif cond.type == "Ready":
                    conditions_summary.insert(0, f"Ready={cond.status}")

            node_name = node.metadata.name
            node_allocated = allocated_by_node.get(node_name, {})

            # Node info from status
            node_info = node.status.node_info
            result.append({
                "name": node_name,
                "ready": ready,
                "conditions": conditions_summary,
                "instance_type": labels.get("node.kubernetes.io/instance-type", labels.get("beta.kubernetes.io/instance-type", "")),
                "os": labels.get("kubernetes.io/os", ""),
                "arch": labels.get("kubernetes.io/arch", ""),
                "kubelet_version": node_info.kubelet_version if node_info else None,
                "container_runtime": node_info.container_runtime_version if node_info else None,
                "capacity": {
                    "cpu": capacity.get("cpu"),
                    "memory": capacity.get("memory"),
                    "pods": capacity.get("pods"),
                },
                "allocatable": {
                    "cpu": allocatable.get("cpu"),
                    "memory": allocatable.get("memory"),
                    "pods": allocatable.get("pods"),
                },
                "allocated": {
                    "cpu": self._format_cpu_millicores(node_allocated.get("cpu_millicores", 0)),
                    "memory": self._format_memory_ki(node_allocated.get("memory_ki", 0)),
                    "pods": str(node_allocated.get("pods", 0)),
                },
            })
        return result

    def _get_allocated_by_node(self, core_api) -> dict[str, dict[str, int]]:
        """Sum resource requests for all running/pending pods grouped by node.

        Returns a dict of node_name -> {"cpu_millicores": int, "memory_ki": int, "pods": int}.
        """
        try:
            all_pods = core_api.list_pod_for_all_namespaces()
        except Exception as e:
            log.debug(f"Cannot list pods cluster-wide for allocation tracking: {e}")
            return {}

        allocated: dict[str, dict[str, int]] = {}
        for pod in all_pods.items:
            # Only count pods that are consuming resources
            phase = pod.status.phase
            if phase not in ("Running", "Pending"):
                continue

            node_name = pod.spec.node_name
            if not node_name:
                continue

            if node_name not in allocated:
                allocated[node_name] = {"cpu_millicores": 0, "memory_ki": 0, "pods": 0}

            allocated[node_name]["pods"] += 1

            for container in (pod.spec.containers or []):
                requests = (container.resources.requests or {}) if container.resources else {}
                cpu_req = requests.get("cpu")
                mem_req = requests.get("memory")
                if cpu_req:
                    allocated[node_name]["cpu_millicores"] += self._parse_cpu_to_millicores(cpu_req)
                if mem_req:
                    allocated[node_name]["memory_ki"] += self._parse_memory_to_ki(mem_req)

        return allocated

    @staticmethod
    def _parse_cpu_to_millicores(value: str) -> int:
        """Parse a Kubernetes CPU value (e.g. '500m', '1', '2.5') to millicores."""
        if value.endswith("m"):
            return int(value[:-1])
        try:
            return int(float(value) * 1000)
        except ValueError:
            return 0

    @staticmethod
    def _parse_memory_to_ki(value: str) -> int:
        """Parse a Kubernetes memory value to kibibytes (Ki)."""
        suffixes = {
            "Ki": 1,
            "Mi": 1024,
            "Gi": 1024 * 1024,
            "Ti": 1024 * 1024 * 1024,
            "K": 1,       # treat K as Ki for simplicity
            "M": 1024,
            "G": 1024 * 1024,
            "T": 1024 * 1024 * 1024,
        }
        for suffix, multiplier in sorted(suffixes.items(), key=lambda x: -len(x[0])):
            if value.endswith(suffix):
                try:
                    return int(float(value[:-len(suffix)]) * multiplier)
                except ValueError:
                    return 0
        # Plain bytes (no suffix)
        try:
            return int(int(value) / 1024)
        except ValueError:
            return 0

    @staticmethod
    def _format_cpu_millicores(millicores: int) -> str:
        """Format millicores to a Kubernetes-style CPU string."""
        if millicores == 0:
            return "0"
        if millicores % 1000 == 0:
            return str(millicores // 1000)
        return f"{millicores}m"

    @staticmethod
    def _format_memory_ki(ki: int) -> str:
        """Format kibibytes to a human-friendly Kubernetes memory string."""
        if ki == 0:
            return "0"
        if ki >= 1024 * 1024:
            return f"{ki // (1024 * 1024)}Gi"
        if ki >= 1024:
            return f"{ki // 1024}Mi"
        return f"{ki}Ki"

    def _get_helm_releases(self, core_api, namespace: str) -> list[dict[str, Any]]:
        """Get Helm release info from secrets in the namespace.

        Helm 3 stores release data as secrets with type=helm.sh/release.v1
        and labels owner=helm, name=<release>, status=<deployed|...>.
        """
        try:
            secrets = core_api.list_namespaced_secret(
                namespace=namespace,
                label_selector="owner=helm",
            )
        except Exception as e:
            log.debug(f"Cannot list Helm release secrets: {e}")
            return [{"error": str(e)}]

        # Group by release name, take the latest version
        releases: dict[str, dict[str, Any]] = {}
        for secret in secrets.items:
            labels = secret.metadata.labels or {}
            release_name = labels.get("name", "")
            version = int(labels.get("version", "0"))

            existing = releases.get(release_name)
            if existing and existing.get("_version", 0) >= version:
                continue

            releases[release_name] = {
                "_version": version,
                "name": release_name,
                "status": labels.get("status", "unknown"),
                "version": version,
                "updated": secret.metadata.creation_timestamp.isoformat() if secret.metadata.creation_timestamp else None,
            }

        # Strip internal fields and return
        result = []
        for rel in releases.values():
            rel.pop("_version", None)
            result.append(rel)
        return sorted(result, key=lambda r: r.get("name", ""))


class AdminPodLogsHandler(APIHandler):
    """Fetch container logs for a session pod.

    Locates the pod via the ``hub.jupyter.org/servername`` label and reads
    logs from the specified container (default: ``notebook``).
    """

    def compute_etag(self) -> None:
        return None

    @needs_scope('admin:users')
    async def get(self, owner: str, session_id: str):
        container = self.get_argument("container", "notebook")
        try:
            tail_lines = int(self.get_argument("tail_lines", "5000"))
        except ValueError:
            tail_lines = 5000
        tail_lines = max(1, min(tail_lines, 100000))

        try:
            result = self._get_pod_logs(session_id, container, tail_lines)
        except Exception as e:
            log.warning(f"Failed to fetch pod logs for {owner}/{session_id}: {e}")
            raise web.HTTPError(500, reason=str(e))

        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(result))

    def _get_pod_logs(
        self, server_name: str, container: str, tail_lines: int
    ) -> dict[str, Any]:
        from kubernetes import client as k8s_client
        from kubernetes import config as k8s_config

        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            try:
                k8s_config.load_kube_config()
            except k8s_config.ConfigException:
                raise web.HTTPError(503, reason="No Kubernetes configuration found")

        core_api = k8s_client.CoreV1Api()

        app = self.settings.get("app")
        namespace = getattr(app, "task_namespace", "beakerhub")

        # Find the pod by JupyterHub server-name label
        label_selector = f"hub.jupyter.org/servername={server_name}"
        pods = core_api.list_namespaced_pod(
            namespace=namespace, label_selector=label_selector
        )
        if not pods.items:
            raise web.HTTPError(
                404, reason=f"No pod found with servername={server_name}"
            )

        pod = pods.items[0]
        pod_name = pod.metadata.name

        try:
            logs = core_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container,
                tail_lines=tail_lines,
            )
        except k8s_client.exceptions.ApiException as e:
            if e.status == 400:
                raise web.HTTPError(
                    400,
                    reason=f"Container '{container}' not found in pod '{pod_name}'",
                )
            raise

        log_lines = logs.split("\n") if logs else []
        truncated = len(log_lines) >= tail_lines

        return {
            "pod_name": pod_name,
            "container": container,
            "logs": logs or "",
            "tail_lines": tail_lines,
            "truncated": truncated,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


dashboard_handlers = [
    (r"/api/beakerhub/admin/dashboard/summary", AdminDashboardSummaryHandler),
    (r"/api/beakerhub/admin/dashboard/cluster", AdminDashboardClusterHandler),
    (r"/api/beakerhub/admin/dashboard/pod-logs/([^/]+)/([^/]+)", AdminPodLogsHandler),
]
