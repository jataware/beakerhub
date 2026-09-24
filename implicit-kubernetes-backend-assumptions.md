# Implicit Kubernetes Backend Assumptions

This document maps backend code that assumes Kubernetes even when it is not
part of the configured spawner implementation. These assumptions need separate
handling if BeakerHub uses ECS as a runtime backend.

## Scope

Included:

- Python backend code under `src/beakerhub` that directly uses Kubernetes
  concepts or APIs.
- Backend data models and API fields whose names expose Kubernetes concepts.
- Node configuration that selects a Kubernetes-named implementation outside
  the spawner itself.

Excluded:

- `src/beakerhub/spawner/kubernetes.py`, because it is the explicit Kubernetes
  spawner implementation.
- `src/beakerhub/spawner/aws/ecs.py`, because it is the explicit ECS spawner
  implementation.
- `helm/`, because Helm and its chart templates are Kubernetes deployment
  artifacts by definition.

No source file currently refers to EKS explicitly. The assumptions below are
generic Kubernetes assumptions.

## Summary

There are four significant areas of implicit coupling:

1. `BeakerHub` selects the Kubernetes spawner by default and defines
   Kubernetes-specific node-image task configuration.
2. Node-image imports are implemented directly as Kubernetes Jobs.
3. The admin dashboard and session-log endpoint query Kubernetes resources
   directly.
4. Task persistence and APIs expose the Kubernetes term `job_name` as the
   external runtime identifier.

The node-side local provisioner also has a Kubernetes-specific name, although
its behavior is not inherently Kubernetes-specific.

## Application defaults and configuration

### Default spawner

`src/beakerhub/app.py:126-129` imports and returns `BeakerKubeSpawner` from the
application's `spawner_class` default.

This makes Kubernetes the implicit runtime whenever deployment configuration
does not explicitly select another spawner. The default is separate from the
Kubernetes spawner implementation itself and is therefore part of backend
selection behavior.

### Node-image task configuration

`src/beakerhub/app.py:26-72` defines application traits for node-image import
tasks:

- `task_backoff_limit`
- `task_active_deadline_seconds`
- `task_ttl_seconds_after_finished`
- `task_node_selector`
- `task_tolerations`
- `task_namespace`

The reporter image and resource dictionaries can apply to other container
runtimes, but the retry, TTL, node selector, toleration, Pod, Job, and namespace
semantics are Kubernetes-specific. The task subsystem consumes these traits
directly rather than through a runtime task-backend interface.

`task_namespace` is also used outside the task subsystem by the admin cluster
dashboard and session-log endpoint. It currently acts as the general
Kubernetes namespace despite its task-specific name.

## Node-image import tasks

### Kubernetes client construction

`src/beakerhub/nodes/tasks.py:13-29` imports the Kubernetes Python client, tries
in-cluster configuration, falls back to kubeconfig, and constructs
`BatchV1Api` and `CoreV1Api` clients.

The module has no runtime-neutral task abstraction. All create, inspect, and
delete operations use Kubernetes clients and resource types.

### Task creation

`src/beakerhub/nodes/tasks.py:32-144` implements an import task as a Kubernetes
`batch/v1` Job:

- An init container runs `beaker context dump` in the selected node image.
- A reporter container reads the result and sends it to the hub callback.
- Both containers exchange output through an `emptyDir` volume.
- The Pod uses Kubernetes resource requirements, restart policy, node selector,
  and tolerations.
- The Job uses Kubernetes metadata and labels, a backoff limit, an active
  deadline, and a TTL after completion.
- Submission uses `create_namespaced_job`.

The two-container workflow and callback protocol are conceptually portable,
but their current orchestration and shared-output mechanism are Kubernetes
resource definitions.

### Task polling and failure diagnosis

`src/beakerhub/nodes/tasks.py:147-222` polls a Kubernetes Job with
`read_namespaced_job`. It maps Kubernetes Job counters to BeakerHub task states:

- `status.succeeded` becomes `completed`.
- `status.failed` becomes `failed`.
- `status.active` becomes `running`.
- No counter becomes `pending`.

Failure diagnosis finds a Pod through the `job-name` label and examines init
container, main container, and Pod status objects. The generated messages use
Kubernetes terms such as init container, container, and Pod phase.

### Task deletion and resources

`src/beakerhub/nodes/tasks.py:225-250` deletes a namespaced Job with Kubernetes
background propagation and converts resource dictionaries to
`V1ResourceRequirements`.

`delete_job` is not currently called elsewhere under `src/beakerhub`, but it is
still part of the task module's backend surface.

### Import orchestration

`src/beakerhub/nodes/import_handlers.py` binds the general import workflow to
the Kubernetes task implementation:

- Line 21 imports `beakerhub.nodes.tasks` as `k8s_tasks`.
- Lines 34-57 describe the operation and errors as Kubernetes Job operations.
- Lines 81-94 read `task_namespace` and call `create_import_job` directly.
- Lines 95-101 persist and expose a `Failed to create K8s Job` error.
- Lines 103-108 store and log the returned identifier as `job_name`.
- Lines 162-172 call `get_job_status` directly while a task is running.
- Line 199 describes the callback caller as a Kubernetes Pod.

There is also a namespace inconsistency relevant to this coupling. Creation
passes the configured `task_namespace`, but line 165 polls without passing a
namespace. Polling therefore uses the hard-coded `"beakerhub"` default from
`nodes/tasks.py`.

The callback endpoint and callback-token protocol are otherwise runtime
neutral. They receive JSON from a reporter and update the database without
using a Kubernetes API.

## Admin cluster dashboard

`src/beakerhub/dashboard_handlers.py:127-509` implements the cluster dashboard
as a direct Kubernetes cluster inspection endpoint.

### Client and resource assumptions

Lines 151-167 load in-cluster configuration or kubeconfig, construct Core and
Batch API clients, and use `task_namespace` as the inspected namespace.

Lines 169-195 always build the response from these Kubernetes resource groups:

- Pods
- PersistentVolumeClaims
- Jobs
- Events
- Nodes
- Helm releases stored as Secrets

If Kubernetes configuration is unavailable, the endpoint returns
`available: false`. It has no dispatch based on the configured runtime backend.

### Pod inventory

Lines 198-238 list namespaced Pods and group them by phase and component. The
classification depends on:

- `app.kubernetes.io/component`
- JupyterHub's `component=singleuser-server` Pod label
- The `session-` Pod-name prefix
- Hub and proxy substrings in Pod names

An ECS task cannot appear in this inventory without an alternate data source
and response mapping.

### Storage, Jobs, and Events

- Lines 240-257 list PVCs and return Kubernetes capacity, phase, and storage
  class fields.
- Lines 259-284 list Kubernetes Jobs selected by
  `app.kubernetes.io/name=beakerhub` and aggregate their Job status counters.
- Lines 286-311 list namespaced Kubernetes warning Events from the last hour.

These response sections describe the Kubernetes deployment as well as user
runtimes. A multi-backend dashboard may therefore need to distinguish platform
deployment information from configured runtime information.

### Cluster nodes and allocated resources

Lines 313-413 list Kubernetes Nodes and calculate allocated CPU, memory, and
Pod counts by summing resource requests from running and pending Pods across all
namespaces.

The returned node metadata depends on Kubernetes labels and node status:

- `node.kubernetes.io/instance-type`
- `beta.kubernetes.io/instance-type`
- `kubernetes.io/os`
- `kubernetes.io/arch`
- kubelet version
- container runtime version
- Kubernetes capacity and allocatable quantities

Lines 415-468 parse and format Kubernetes CPU and memory quantity syntax.

### Helm release discovery

Lines 470-509 list Kubernetes Secrets with `owner=helm`, then infer Helm
release name, status, revision, and update time from Secret labels and metadata.

This section concerns how BeakerHub itself is deployed rather than the notebook
runtime, but the backend endpoint still assumes access to a Kubernetes cluster.

## Session log access

`src/beakerhub/dashboard_handlers.py:512-591` implements session logs as
Kubernetes Pod logs:

- It loads in-cluster configuration or kubeconfig.
- It uses `task_namespace` as the notebook namespace.
- It locates the session Pod through the
  `hub.jupyter.org/servername=<session_id>` label.
- It reads a named container with `read_namespaced_pod_log`.
- Its response includes `pod_name`.
- Its errors refer to Pods and containers.

This endpoint is directly coupled to KubeSpawner's Pod labels and Kubernetes
log API. It cannot find or read an ECS-backed session even if the ECS spawner
successfully starts that session.

## Persistence and exposed terminology

`src/beakerhub/orm.py:222-240` describes `NodeImageTask` as tracking Kubernetes
Jobs and stores the external task identifier in `job_name`.

The same field is exposed by several otherwise runtime-neutral surfaces:

- `src/beakerhub/nodes/import_handlers.py:67,103,133,163-177`
- `src/beakerhub/cli/main.py:88`
- `src/beakerhub/admin_handlers.py:334,401`
- `src/beakerhub/dashboard_handlers.py:84-103`

These callers do not themselves use Kubernetes APIs. Their coupling is in the
data contract and user-facing terminology. A runtime-neutral task identifier
would need either a schema/API change or a compatibility mapping to the
existing `job_name` field.

## Kubernetes-named local provisioner

`src/beakerhub/spawner/provisioner.py:5-13` defines
`KubernetesLocalProvisioner`. It forwards launched kernel stdout and stderr to
the parent process streams so container logs reach the platform log collector.

The behavior is useful in both Kubernetes and ECS. Only the class name,
docstring, and registered provisioner name are Kubernetes-specific.

The notebook configuration generated outside `src` selects the literal
`kubernetes-local-provisioner` name. That configuration is excluded from this
document's file inventory because it is under `helm`, but it is the consumer
that makes this name operationally significant.

## Text-only spawner references

The following documentation strings name `BeakerKubeSpawner` as the producer
of the secret-policy environment protocol:

- `src/beakerhub/services/secrets/__init__.py:3-4`
- `src/beakerhub/services/secrets/beakerhub.py:43-58`

The environment construction now lives in the shared spawner base, so these
references are stale implementation terminology rather than functional
Kubernetes dependencies.

## Backend boundaries indicated by the current code

The implicit assumptions group around three runtime operations that are not
provided by the configured spawner alone:

| Operation | Current implementation |
| --- | --- |
| Node-image task lifecycle | Kubernetes Job create, poll, diagnose, and delete |
| Runtime inventory and health | Kubernetes Pods, Jobs, Nodes, Events, PVCs, and Helm Secrets |
| Session logs | Kubernetes Pod lookup and Pod log API |

Default backend selection and Kubernetes-specific task settings are configured
on `BeakerHub` itself. Task identifiers and some API response fields also expose
the Kubernetes implementation beyond these operational boundaries.

## Proposed backend organization

The backend should be a namespace and configuration profile, not a single
service that performs all backend operations. It can group related
implementations and provide a coherent set of defaults while leaving each
component independently configurable on the application.

A backend package could contain implementations for:

- A JupyterHub spawner
- A node-image task runner
- Dashboard data providers or widgets
- A session log provider
- A node launch-spec resolver
- Runtime-specific secret delivery

For example, a Kubernetes profile could default these components to Kubernetes
implementations, while an ECS profile could default them to ECS and AWS
implementations. Explicit component configuration should be able to override
individual profile defaults. This permits mixed configurations, such as ECS
notebook sessions with Kubernetes import tasks.

The intended configuration precedence is:

1. Component's built-in default
2. Backend profile default
3. Explicit component configuration

The backend profile should select classes and supply default configuration. It
should not own initialized clients, credentials, mutable runtime state, or the
actual component lifecycle.

### Package organization and many-to-many mapping

Provider-first package organization becomes ambiguous when implementations are
independently selectable. AWS is both a vendor and a collection of unrelated
services: selecting ECS does not imply Secrets Manager, CloudWatch, S3, or any
particular combination of them.

A capability-first implementation tree keeps discovery and ownership clearer:

```text
beakerhub/backends/
├── contracts/
│   ├── task_runner.py
│   ├── dashboard.py
│   ├── log_provider.py
│   ├── secret_vault.py
│   └── node_spec.py
├── task_runners/
│   ├── kubernetes.py
│   └── aws_ecs.py
├── dashboards/
│   ├── kubernetes.py
│   └── aws_ecs.py
├── log_providers/
│   ├── kubernetes.py
│   └── aws_cloudwatch.py
├── secret_vaults/
│   ├── orm.py
│   └── aws_secrets_manager.py
├── secret_delivery/
│   ├── environment.py
│   ├── kubernetes.py
│   └── aws_ecs.py
├── node_specs/
│   ├── kubernetes.py
│   └── aws_ecs.py
└── profiles/
    ├── default.py
    ├── kubernetes.py
    └── aws_ecs.py
```

Under this organization, the AWS Secrets Manager implementation belongs at
`backends/secret_vaults/aws_secrets_manager.py`, not under the ECS package. If
the implementation grows, it can become a package at the same location:

```text
backends/secret_vaults/aws_secrets_manager/
├── __init__.py
├── vault.py
├── models.py
└── client.py
```

The consequence is that code for one vendor appears under several capability
directories. That matches the normal discovery question: which task runners,
secret vaults, or log providers are available? Vendor-oriented inspection can
still use repository search and consistent prefixes such as `aws_`.

### Sparse profiles and independent overrides

A backend profile should be an explicit, potentially sparse mapping from
capabilities to default implementations. For example, an ECS profile could
select defaults for session spawning, background tasks, dashboard data, logs,
and workload-spec resolution:

```python
class AwsEcsBackendProfile(BackendProfile):
    spawner_class = BeakerAwsECSSpawner
    task_runner_class = AwsEcsTaskRunner
    dashboard_provider_class = AwsEcsDashboardProvider
    log_provider_class = AwsCloudWatchLogProvider
    node_spec_provider_class = AwsEcsNodeSpecProvider
```

It should not select AWS Secrets Manager only because it selects ECS. Secret
storage is orthogonal and should remain independently configurable:

```python
c.BeakerHub.backend_profile = "aws-ecs"
c.BeakerHub.secret_vault_class = (
    "beakerhub.backends.secret_vaults.aws_secrets_manager."
    "AwsSecretsManagerVault"
)
```

The default profile can supply the current ORM vault when no explicit vault is
configured. Mixed configurations must not require a new named profile for each
combination. In particular, avoid profile proliferation such as
`aws-ecs-with-secrets-manager-and-cloudwatch`.

The mapping rules should be explicit:

1. A profile supplies defaults; it does not own its components.
2. A profile can omit capabilities it does not need to configure.
3. Explicit component configuration overrides the profile.
4. Selecting a vendor or runtime does not imply unrelated services.
5. Each implementation lives under the capability it implements.
6. Built-in aliases need only be unique within their capability.
7. Unsupported capabilities remain unset or use an explicit null
   implementation; they do not fabricate equivalent data.

### Discovery and registration

Initial discovery should be deterministic rather than based on filesystem
scanning or import side effects. Each capability can provide a small built-in
alias registry:

```python
BUILTIN_TASK_RUNNERS = {
    "kubernetes": KubernetesTaskRunner,
    "aws-ecs": AwsEcsTaskRunner,
}

BUILTIN_SECRET_VAULTS = {
    "orm": OrmSecretVault,
    "aws-secrets-manager": AwsSecretsManagerVault,
}
```

Application configuration can accept either a stable alias or an importable
class path:

```python
c.BeakerHub.task_runner = "aws-ecs"
c.BeakerHub.secret_vault = "aws-secrets-manager"
```

If external implementations become necessary, component-specific Python entry
point groups can extend the same registries:

```text
beakerhub.task_runners
beakerhub.dashboard_providers
beakerhub.secret_vaults
beakerhub.log_providers
```

Separate groups avoid global alias collisions and make it possible to list the
available implementations for one capability without importing every backend
component.

## Additional interchangeable components

### Secret vault

Secret storage is the strongest additional candidate for an independently
configured backend service. The current implementation combines secret
metadata, encrypted value storage, CRUD, context enablement, spawn-time
resolution, and runtime delivery.

Current ORM coupling includes:

- `src/beakerhub/orm.py:52-87`, where `EncryptedString` encrypts values with a
  process-wide Fernet key.
- `src/beakerhub/orm.py:248-292`, where `NodeSecret` stores the secret value,
  environment-variable name, description, policy overrides, and node-image
  scope.
- `src/beakerhub/orm.py:140-146`, where `beaker_context_secrets` associates
  context enablement with numeric `NodeSecret` IDs.
- `src/beakerhub/admin_handlers.py:696-865`, where handlers query and mutate
  `NodeSecret` records directly.
- `src/beakerhub/admin_handlers.py:868-955`, where context-specific enablement
  is managed through the ORM association table.
- The configured spawner's option processing, which queries these records to
  resolve effective values and policy overrides for a launch.

An AWS Secrets Manager implementation could take several forms:

- Store values and metadata entirely in AWS Secrets Manager.
- Keep scope, descriptions, policy overrides, and context relationships in the
  ORM while storing only secret values externally.
- Store external secret references in the ORM and let the runtime inject values
  directly without exposing plaintext to the hub.

The third form is materially different from replacing `EncryptedString`.
Vault persistence and secret delivery should therefore be separate contracts,
even if a default implementation provides both.

A vault service would likely own operations such as:

- List and retrieve secret metadata
- Create, update, and delete secrets
- Resolve stable secret references
- Retrieve values when the selected delivery mechanism requires plaintext
- Report capabilities, such as whether values can be read back through the
  administration API

The existing context associations require stable local identifiers. A fully
external vault still needs either local reference records or a replacement for
the numeric `node_secret_id` relationship.

### Secret resolution and delivery

The runtime currently receives plaintext secret values as environment
variables. Additional environment variables identify which values came from
the vault and carry per-secret policy overrides.

Potential delivery implementations include:

- Literal environment values
- Kubernetes `secretRef` entries
- ECS `secrets.valueFrom` references
- Mounted secret files
- Node-side lookup through workload identity

The delivery component must preserve the node-side policy protocol even when
the hub does not retrieve the value. This includes identifying vault-provided
variables and supplying the policy overrides consumed by
`BeakerhubSecretsManager`.

Secret delivery may live within each runtime backend because its output must
match the target workload specification. It should still consume a
runtime-neutral vault/reference model rather than query `NodeSecret` directly.

### Node launch-spec resolution

`NodeImages` currently represents a runnable node as an OCI image assembled
from registry, repository, and tag:

- `src/beakerhub/orm.py:186-217`
- `src/beakerhub/spawner/base.py:90-144`

Both notebook spawning and node-image import tasks consume that representation.
For Kubernetes, an image reference is nearly sufficient to build a Pod. ECS
normally also requires a task definition and associated launch configuration.

ECS resolution may need to:

- Select an existing task definition
- Register a task-definition revision for the chosen image
- Map CPU and memory settings to valid ECS combinations
- Configure roles, logging, volumes, ports, and health checks
- Apply runtime-specific secret references
- Manage any generated task-definition revisions

A shared `NodeSpecResolver`, `WorkloadSpecProvider`, or similarly focused
component could translate a `NodeImages` record and launch options into a
backend-specific workload specification. This would avoid duplicating the same
mapping in the spawner and task runner.

This boundary can also support digest-pinned images, prebuilt task definitions,
private registry authentication, or future artifact representations without
changing the catalog-facing `NodeImages` API immediately.

### Context catalog sources

Context discovery already has a useful runtime-neutral interchange format:

- `src/beakerhub/utils.py:149-156` defines `InterchangeDump`.
- `src/beakerhub/utils.py:579-581` deserializes the format.
- `src/beakerhub/utils.py:584-872` ingests it into the ORM.
- `src/beakerhub/scripts/seed_contexts.py` imports the older JSON format.

The current primary source executes a node image and inspects its installed
packages. Other potential sources include:

- A package or organizational context registry
- A static manifest repository
- S3 or another object store
- A Git repository
- OCI image metadata or attestations that do not require executing the image

A `ContextSource` or `CatalogSource` could produce `InterchangeDump` objects,
while the existing ingestion, deduplication, and curation logic remains shared.
This is a plausible future extension point rather than a requirement for the
first ECS implementation.

### Task result transport

The import-task callback protocol is already mostly independent from
Kubernetes. The shared workflow is:

1. Create a task record and callback credential.
2. Execute `beaker context dump` through the configured task runner.
3. Deliver an interchange dump to BeakerHub.
4. Authenticate and deserialize the result.
5. Ingest the dump and update task state.

The current implementation delivers the result through an HTTP callback from a
reporter container. Other implementations could use object storage, a queue,
an event, or output retrieved during polling.

The task runner should own workload submission, status inspection,
cancellation, and backend-specific diagnostics. Result authentication,
deserialization, and ingestion should remain shared. The mechanism that makes
the completed dump available can be independently configurable if a second
transport is needed.

## Component and capability summary

The backend-related component inventory is:

| Component | Responsibility | Configuration relationship |
| --- | --- | --- |
| Spawner | JupyterHub session lifecycle and reachable server address | Selected independently; backend profile supplies a default |
| Task runner | Submit, inspect, cancel, and diagnose background workloads | Selected independently; backend profile supplies a default |
| Dashboard provider/widgets | Runtime and infrastructure inspection | Selected or enabled independently by server configuration |
| Session log provider | Discover and retrieve logs for a session | Selected independently; backend profile supplies a default |
| Node launch-spec resolver | Translate node catalog records into runtime workload definitions | Shared by a backend's spawner and task runner where useful |
| Secret vault | Store secret metadata, references, and optionally values | Independent configured service |
| Secret delivery | Add values or references and policy metadata to workload specifications | Usually runtime-specific; consumes the configured vault |
| Context catalog source | Produce context interchange dumps | Independent optional source |
| Task result transport | Make completed task output available to shared ingestion | Part of the task subsystem and independently replaceable if needed |

Components should expose capabilities rather than requiring every backend to
implement equivalent Kubernetes concepts. Configuration and API responses need
to distinguish an unsupported capability from an empty result or a temporary
query failure.

The dashboard should also distinguish deployment information from runtime
information. A BeakerHub deployment can continue to run on Kubernetes while
its notebook sessions and import tasks run on ECS, so Kubernetes deployment
status and ECS runtime status can both be valid and useful at the same time.
