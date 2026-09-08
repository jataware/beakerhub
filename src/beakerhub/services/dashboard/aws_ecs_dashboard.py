"""AWS ECS implementation of the dashboard service."""

from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError

from beakerhub.runtimes.aws_ecs import AwsEcsRuntime
from beakerhub.services.dashboard.base import (
    BaseDashboardService,
    DashboardServiceError,
)


class AwsEcsDashboardService(BaseDashboardService):
    """Provide AWS ECS runtime data and session logs to the dashboard."""

    def _runtime(self) -> AwsEcsRuntime:
        parent_runtime = getattr(self.parent, "runtime", None)
        if isinstance(parent_runtime, AwsEcsRuntime):
            return parent_runtime
        return AwsEcsRuntime(parent=self.parent)

    def get_dashboard(self) -> dict[str, Any]:
        runtime = self._runtime()
        cluster_name = runtime.cluster_name
        if not cluster_name:
            return {
                "available": False,
                "error": "No ECS cluster is configured",
            }

        try:
            cluster = runtime.ecs_client.describe_clusters(
                clusters=[cluster_name],
            ).get("clusters", [])[0]
        except (ClientError, IndexError) as error:
            return {"available": False, "error": str(error)}

        try:
            services = self._describe_services(runtime, cluster_name)
            tasks = self._describe_tasks(runtime, cluster_name)
            stopped_tasks = self._describe_stopped_tasks(runtime, cluster_name)
            instances = self._describe_container_instances(runtime, cluster_name)
        except ClientError as error:
            return {"available": False, "error": str(error)}

        is_fargate = self._is_fargate(runtime, tasks, instances)
        running_tasks = sum(1 for task in tasks if task.get("lastStatus") == "RUNNING")
        pending_tasks = sum(1 for task in tasks if task.get("lastStatus") == "PENDING")
        failed_tasks = self._failed_tasks(stopped_tasks)
        task_detail = f"{running_tasks} running, {pending_tasks} pending"
        if failed_tasks:
            task_detail += f", {len(failed_tasks)} failed"
        return {
            "available": True,
            "runtime": {
                "provider": "Amazon ECS",
                "scope": self._short_name(cluster.get("clusterArn", cluster_name)),
            },
            "summary": [
                {
                    "label": "Services",
                    "value": len(services),
                    "detail": f"{sum(service.get('runningCount', 0) for service in services)} running",
                },
                {
                    "label": "Tasks",
                    "value": len(tasks),
                    "detail": task_detail,
                    "severity": "danger" if failed_tasks else None,
                },
                {
                    "label": "Compute instances",
                    "value": len(instances),
                    "detail": (
                        "Compute is managed by AWS Fargate. This cluster has no "
                        "registered container instances."
                        if is_fargate
                        else f"{sum(1 for item in instances if item.get('status') == 'ACTIVE')} active"
                    ),
                },
            ],
            "workloads": self._workloads(services, tasks),
            "resources_empty_message": (
                "AWS Fargate manages the underlying compute resources. Per-instance "
                "capacity is not available."
                if is_fargate and not instances
                else None
            ),
            "resources": [
                {
                    "name": self._short_name(instance.get("containerInstanceArn", "Unknown")),
                    "status": instance.get("status", "UNKNOWN").lower(),
                    "details": [
                        {"label": "Agent", "value": instance.get("agentConnected", False) and "Connected" or "Disconnected"},
                        {"label": "Running tasks", "value": instance.get("runningTasksCount", 0)},
                        {"label": "Pending tasks", "value": instance.get("pendingTasksCount", 0)},
                    ],
                }
                for instance in instances
            ],
            "alerts": [
                {
                    "reason": "Stopped task",
                    "message": task.get("stoppedReason", "Task stopped"),
                    "object": self._short_name(task.get("taskArn", "Unknown")),
                    "timestamp": task.get("stoppedAt", datetime.now(timezone.utc)).isoformat(),
                }
                for task in failed_tasks
            ][:20],
        }

    def get_session_logs(
        self,
        session_id: str,
        container: str,
        tail_lines: int,
    ) -> dict[str, Any]:
        runtime = self._runtime()
        if not runtime.cluster_name:
            raise DashboardServiceError(503, "No ECS cluster is configured")
        task = runtime.describe_task(runtime.cluster_name, session_id)
        if task is None:
            raise DashboardServiceError(404, "Session task was not found")

        task_id = session_id.rsplit("/", maxsplit=1)[-1]
        task_container = next(
            (item for item in task.get("containers", []) if item.get("name") == container),
            None,
        )
        if task_container is None and container == "notebook":
            task_container = next(iter(task.get("containers", [])), None)
        if task_container is None:
            raise DashboardServiceError(404, f"Container '{container}' was not found")
        container_name = task_container.get("name", container)
        if not runtime.log_group:
            raise DashboardServiceError(503, "CloudWatch log group is not configured")

        stream_name = task_container.get(
            "logStreamName",
            f"{runtime.log_stream_prefix}/{container_name}/{task_id}",
        )
        try:
            messages, truncated = runtime.get_log_tail(
                runtime.log_group,
                stream_name,
                tail_lines,
            )
        except RuntimeError as error:
            raise DashboardServiceError(502, str(error)) from error
        return {
            "runtime_name": self._short_name(task.get("taskArn", session_id)),
            "pod_name": self._short_name(task.get("taskArn", session_id)),
            "container": container_name,
            "logs": "\n".join(messages),
            "tail_lines": tail_lines,
            "truncated": truncated,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _failed_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        failure_stop_codes = {"EssentialContainerExited", "TaskFailedToStart"}
        return [
            task
            for task in tasks
            if task.get("stopCode") in failure_stop_codes
            or (
                task.get("stopCode") != "UserInitiated"
                and any(
                    container.get("exitCode", 0) != 0
                    for container in task.get("containers", [])
                )
            )
        ]

    @staticmethod
    def _is_fargate(
        runtime: AwsEcsRuntime,
        tasks: list[dict[str, Any]],
        instances: list[dict[str, Any]],
    ) -> bool:
        """Determine whether the displayed capacity is Fargate-managed."""
        if instances:
            return False
        providers = {
            task.get("capacityProviderName")
            for task in tasks
            if task.get("capacityProviderName")
        }
        if providers:
            return providers <= {"FARGATE", "FARGATE_SPOT"}
        strategy = runtime.launch_options.get("capacityProviderStrategy", [])
        if strategy:
            return {
                item.get("capacityProvider") for item in strategy
            } <= {"FARGATE", "FARGATE_SPOT"}
        return runtime.launch_type == "FARGATE"

    def _workloads(
        self,
        services: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Group service-owned tasks under their ECS service."""
        managed_task_arns: set[str] = set()
        workloads = []
        for service in services:
            service_name = service.get("serviceName", "Unknown service")
            owned_tasks = [
                task
                for task in tasks
                if task.get("group") == f"service:{service_name}"
            ]
            children = [self._task_workload(task) for task in owned_tasks]
            managed_task_arns.update(task.get("taskArn", "") for task in owned_tasks)
            workloads.append(
                {
                    "name": service_name,
                    "kind": "Service",
                    "status": service.get("status", "UNKNOWN").lower(),
                    "detail": (
                        f"{service.get('runningCount', 0)} running / "
                        f"{service.get('desiredCount', 0)} desired"
                    ),
                    "children": children,
                }
            )
        workloads.extend(
            self._task_workload(task)
            for task in tasks
            if task.get("taskArn", "") not in managed_task_arns
        )
        return workloads

    def _task_workload(self, task: dict[str, Any]) -> dict[str, str]:
        return {
            "name": self._short_name(task.get("taskArn", "Unknown task")),
            "kind": "Task",
            "status": task.get("lastStatus", "UNKNOWN").lower(),
            "detail": task.get("taskDefinitionArn", "").rsplit("/", maxsplit=1)[-1],
        }

    @staticmethod
    def _short_name(value: str) -> str:
        return value.rsplit("/", maxsplit=1)[-1]

    @staticmethod
    def _list_all(client_method, result_key: str, **kwargs: Any) -> list[str]:
        values: list[str] = []
        next_token: str | None = None
        while True:
            request = dict(kwargs)
            if next_token:
                request["nextToken"] = next_token
            response = client_method(**request)
            values.extend(response.get(result_key, []))
            next_token = response.get("nextToken")
            if not next_token:
                return values

    def _describe_services(self, runtime: AwsEcsRuntime, cluster: str) -> list[dict[str, Any]]:
        arns = self._list_all(
            runtime.ecs_client.list_services,
            "serviceArns",
            cluster=cluster,
        )
        return [
            service
            for start in range(0, len(arns), 10)
            for service in runtime.ecs_client.describe_services(
                cluster=cluster, services=arns[start : start + 10]
            ).get("services", [])
        ]

    def _describe_tasks(self, runtime: AwsEcsRuntime, cluster: str) -> list[dict[str, Any]]:
        arns = self._list_all(
            runtime.ecs_client.list_tasks,
            "taskArns",
            cluster=cluster,
        )
        return [
            task
            for start in range(0, len(arns), 100)
            for task in runtime.ecs_client.describe_tasks(
                cluster=cluster, tasks=arns[start : start + 100]
            ).get("tasks", [])
        ]

    def _describe_stopped_tasks(
        self, runtime: AwsEcsRuntime, cluster: str
    ) -> list[dict[str, Any]]:
        arns = self._list_all(
            runtime.ecs_client.list_tasks,
            "taskArns",
            cluster=cluster,
            desiredStatus="STOPPED",
        )
        return [
            task
            for start in range(0, len(arns), 100)
            for task in runtime.ecs_client.describe_tasks(
                cluster=cluster, tasks=arns[start : start + 100]
            ).get("tasks", [])
        ]

    def _describe_container_instances(
        self, runtime: AwsEcsRuntime, cluster: str
    ) -> list[dict[str, Any]]:
        arns = self._list_all(
            runtime.ecs_client.list_container_instances,
            "containerInstanceArns",
            cluster=cluster,
        )
        return [
            instance
            for start in range(0, len(arns), 100)
            for instance in runtime.ecs_client.describe_container_instances(
                cluster=cluster, containerInstances=arns[start : start + 100]
            ).get("containerInstances", [])
        ]
