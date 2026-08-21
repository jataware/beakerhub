import { defineStore } from 'pinia';
import { ref, reactive } from 'vue';
import { fetch } from '@/utils/fetch';
import type { SecretPolicies } from '@/utils/secretPolicies';

// ============================================
// Types
// ============================================

export interface AdminContext {
  id: number;
  slug: string;
  display_name: string;
  description: string;
  icon: string | null;
  theme: string;
  image: string | null;
  image_enabled: boolean | null;
  weight: number;
  enabled: boolean;
  default_payload: Record<string, any>;
  source_package: string | null;
  source_key: string | null;
  version: string | null;
  visible_to_roles: string[];
  languages: AdminLanguage[];
  integrations: AdminIntegration[];
  workflows: AdminWorkflow[];
  api_keys: AdminApiKeyRequirement[];
}

export interface AdminWorkflow {
  id: number;
  title: string;
  human_description: string;
  agent_description: string;
  example_prompt: string;
  category: { slug: string; display_name: string; description: string; sort_order: number } | null;
  hidden: boolean;
  enabled: boolean;
  is_context_default: boolean;
  source_package: string;
  source_path: string;
  stage_count?: number;
}

export interface AdminIntegration {
  id: number;
  slug: string;
  name: string;
  description: string;
  enabled: boolean;
  source_package: string;
  source_uuid: string;
}

export interface AdminLanguage {
  slug: string;
  subkernel: string;
  display_name: string;
}

export interface AdminIntegrationDetail extends AdminIntegration {
  contexts: { slug: string; source_key: string | null; display_name: string }[];
}

export interface AdminApiKeyRequirement {
  env_var: string;
  display_name: string;
  required: boolean;
}

export interface AdminApiKey {
  id: number;
  env_var: string;
  display_name: string;
  description: string;
  required: boolean;
}

export interface AdminWorkflowDetail {
  id: number;
  title: string;
  human_description: string;
  agent_description: string;
  example_prompt: string;
  category: { slug: string; display_name: string; description: string; sort_order: number } | null;
  hidden: boolean;
  enabled: boolean;
  is_context_default: boolean;
  source_package: string;
  source_path: string;
  metadata: Record<string, any>;
  stages: AdminWorkflowStage[];
}

export interface AdminWorkflowStage {
  id: number;
  name: string;
  sort_order: number;
  description: string[];
  metadata: Record<string, any>;
}

export interface AdminNodeImageContext {
  slug: string;
  source_key: string | null;
  display_name: string;
  enabled: boolean;
}

export interface AdminNodeImageImport {
  task_id: number;
  status: string;
  job_name: string | null;
  created_at: string | null;
  updated_at: string | null;
  error: string | null;
}

export interface ImportEvent {
  imageId: number;
  slug: string;
  status: 'completed' | 'failed';
  error?: string;
  result?: Record<string, number>;
}

export interface AdminRegistryImage {
  repository: string;
  tag: string;
}

export interface AdminNodeImage {
  id: number;
  slug: string;
  default_registry: string;
  repository: string;
  default_tag: string;
  metadata: Record<string, any>;
  enabled: boolean;
  created_at: string | null;
  updated_at: string | null;
  contexts?: AdminNodeImageContext[];
  last_import?: AdminNodeImageImport | null;
}

export interface VaultSecret {
  id: number;
  node_image_id: number | null;
  env_var: string;
  description: string | null;
  /** Sparse policy overrides; an absent axis uses the system-secret default. */
  policies: SecretPolicies;
  created_at: string | null;
  updated_at: string | null;
}

export interface VaultSecretWithValue extends VaultSecret {
  value: string;
}

export interface ContextSecretOverride {
  id: number;
  node_image_id: number | null;
  env_var: string;
  description: string | null;
  policies: SecretPolicies;
  enabled: boolean;
}

export interface JupyterHubUser {
  name: string;
  admin: boolean;
  roles: string[];
  groups: string[];
  created: string;
  last_activity: string;
  servers: Record<string, JupyterHubServer>;
}

export interface JupyterHubServer {
  name: string;
  ready: boolean;
  stopped: boolean;
  pending: string | null;
  url: string;
  started: string;
  last_activity: string;
  state: any;
  user_options: any;
}

// ============================================
// Dashboard Types
// ============================================

export interface DashboardCounts {
  images: { total: number; enabled: number };
  contexts: { total: number; enabled: number };
  workflows: { total: number; enabled: number };
  integrations: { total: number; enabled: number };
  languages: { total: number };
  secrets: { total: number; global: number; per_node: number };
  users: { total: number; admin: number };
  sessions: { active_servers: number; beaker_sessions_total: number };
}

export interface DashboardImport {
  task_id: number;
  node_image_slug: string | null;
  task_type: string;
  status: string;
  job_name: string | null;
  created_at: string | null;
  updated_at: string | null;
  error: string | null;
  result: Record<string, number> | null;
}

export interface DashboardSummary {
  app_version: string;
  counts: DashboardCounts;
  recent_imports: DashboardImport[];
}

export interface PodLogsResponse {
  pod_name: string;
  container: string;
  logs: string;
  tail_lines: number;
  truncated: boolean;
  timestamp: string;
}

export interface ClusterPodComponent {
  count: number;
  phases: Record<string, number>;
}

export interface ClusterPVC {
  name: string;
  capacity: string | null;
  phase: string;
  storage_class: string | null;
}

export interface ClusterEvent {
  type: string;
  reason: string;
  message: string;
  involved_object: string | null;
  last_timestamp: string | null;
  count: number;
}

export interface ClusterNode {
  name: string;
  ready: boolean;
  conditions: string[];
  instance_type: string;
  os: string;
  arch: string;
  kubelet_version: string | null;
  container_runtime: string | null;
  capacity: { cpu: string | null; memory: string | null; pods: string | null };
  allocatable: { cpu: string | null; memory: string | null; pods: string | null };
  allocated: { cpu: string | null; memory: string | null; pods: string | null };
  error?: string;
}

export interface HelmRelease {
  name: string;
  status: string;
  version: number;
  updated: string | null;
  error?: string;
}

export interface ClusterInfo {
  available: boolean;
  error?: string;
  namespace?: string;
  pods?: {
    total: number;
    by_phase: Record<string, number>;
    by_component: Record<string, ClusterPodComponent>;
  };
  pvcs?: ClusterPVC[];
  jobs?: {
    total: number;
    active: number;
    succeeded: number;
    failed: number;
  };
  events?: ClusterEvent[];
  nodes?: ClusterNode[];
  helm_releases?: HelmRelease[];
}

// ============================================
// Store
// ============================================

export const useAdminStore = defineStore('admin', () => {
  // State
  const contexts = ref<AdminContext[]>([]);
  const contextsLoading = ref(false);

  const users = ref<JupyterHubUser[]>([]);
  const usersLoading = ref(false);

  // Dashboard state
  const dashboardSummary = ref<DashboardSummary | null>(null);
  const dashboardSummaryLoading = ref(false);
  const clusterInfo = ref<ClusterInfo | null>(null);
  const clusterInfoLoading = ref(false);

  // Supporting entities for context form
  const nodeImages = ref<AdminNodeImage[]>([]);
  const registryName = ref('');
  const registryImages = ref<AdminRegistryImage[]>([]);
  const registryImagesLoading = ref(false);
  const registryImagesError = ref('');
  let registryImagesEtag = '';
  const allWorkflows = ref<AdminWorkflow[]>([]);
  const allIntegrations = ref<AdminIntegration[]>([]);
  const allLanguages = ref<AdminLanguage[]>([]);
  const allApiKeys = ref<AdminApiKey[]>([]);

  // ============================================
  // Context Admin API
  // ============================================

  async function fetchContexts(): Promise<void> {
    contextsLoading.value = true;
    try {
      const response = await fetch('/api/beakerhub/admin/contexts');
      if (response.ok) {
        const data = await response.json();
        contexts.value = data.contexts;
      }
    } finally {
      contextsLoading.value = false;
    }
  }

  async function fetchContext(sourceKey: string): Promise<AdminContext | null> {
    const response = await fetch(`/api/beakerhub/admin/contexts/${encodeURIComponent(sourceKey)}`);
    if (response.ok) {
      return await response.json();
    }
    return null;
  }

  async function createContext(payload: Record<string, any>): Promise<AdminContext | null> {
    const response = await fetch('/api/beakerhub/admin/contexts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (response.ok) {
      const context = await response.json();
      await fetchContexts();
      return context;
    }
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || 'Failed to create context');
  }

  async function updateContext(sourceKey: string, payload: Record<string, any>): Promise<AdminContext | null> {
    const response = await fetch(`/api/beakerhub/admin/contexts/${encodeURIComponent(sourceKey)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (response.ok) {
      const context = await response.json();
      await fetchContexts();
      return context;
    }
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || 'Failed to update context');
  }

  async function deleteContext(sourceKey: string): Promise<boolean> {
    const response = await fetch(`/api/beakerhub/admin/contexts/${encodeURIComponent(sourceKey)}`, {
      method: 'DELETE',
    });
    if (response.ok || response.status === 204) {
      await fetchContexts();
      return true;
    }
    return false;
  }

  // ============================================
  // Supporting Entity Lists
  // ============================================

  const nodeImagesLoading = ref(false);

  async function fetchRegistryImages(): Promise<void> {
    registryImagesLoading.value = true;
    registryImagesError.value = '';
    try {
      const response = await fetch('/api/beakerhub/admin/registry-images', {
        headers: registryImagesEtag ? { 'If-None-Match': registryImagesEtag } : {},
      });
      if (response.status === 304) {
        return;
      }
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.message || data.error || response.statusText || 'Failed to load registry images');
      }
      registryName.value = (data.registry || '').replace(/^https?:\/\//, '');
      registryImages.value = data.images || [];
      registryImagesEtag = response.headers.get('ETag') || '';
    } catch (error: any) {
      registryImagesError.value = error.message || 'Failed to load registry images.';
    } finally {
      registryImagesLoading.value = false;
    }
  }

  async function fetchNodeImages(): Promise<void> {
    nodeImagesLoading.value = true;
    try {
      const response = await fetch('/api/beakerhub/admin/node-images');
      if (response.ok) {
        const data = await response.json();
        nodeImages.value = data.node_images;
        resumeImportPolls();
      }
    } finally {
      nodeImagesLoading.value = false;
    }
  }

  async function createNodeImage(payload: Record<string, any>): Promise<AdminNodeImage | null> {
    const response = await fetch('/api/beakerhub/admin/node-images', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (response.ok) {
      const created = await response.json();
      await fetchNodeImages();
      return created;
    }
    const errorBody = await response.json().catch(() => null);
    const message = errorBody?.message || errorBody?.error || response.statusText || 'Failed to create node image';
    throw new Error(message);
  }

  async function updateNodeImage(id: number, payload: Record<string, any>): Promise<AdminNodeImage | null> {
    const response = await fetch(`/api/beakerhub/admin/node-images/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (response.ok) {
      const updated = await response.json();
      await fetchNodeImages();
      return updated;
    }
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || 'Failed to update node image');
  }

  async function deleteNodeImage(id: number): Promise<boolean> {
    const response = await fetch(`/api/beakerhub/admin/node-images/${id}`, {
      method: 'DELETE',
    });
    if (response.ok || response.status === 204) {
      await fetchNodeImages();
      return true;
    }
    return false;
  }

  async function pullNodeImage(id: number): Promise<{ task_id: number; job_name: string; status: string }> {
    const response = await fetch(`/api/beakerhub/admin/node-images/${id}/import`, {
      method: 'POST',
    });
    if (response.ok) {
      const result = await response.json();
      await fetchNodeImages();
      startImportPoll(id);
      return result;
    }
    const errorBody = await response.json().catch(() => null);
    const message = errorBody?.message || errorBody?.error || response.statusText || 'Failed to pull image';
    throw new Error(message);
  }

  // ============================================
  // Import Task Polling
  // ============================================

  const IMPORT_POLL_INTERVAL_MS = 5000;

  /** Reactive flag per image ID — true while an import is in progress. */
  const importingImages = reactive<Record<number, boolean>>({});

  /** Queue of completed/failed import events for UI consumption. */
  const importEvents = ref<ImportEvent[]>([]);

  // Internal timer tracking — not reactive, no need.
  const _importPolls = new Map<number, ReturnType<typeof setTimeout>>();

  function _resolveSlug(imageId: number): string {
    const img = nodeImages.value.find((i) => i.id === imageId);
    return img?.slug ?? `#${imageId}`;
  }

  async function _importPollTick(imageId: number) {
    try {
      const response = await fetch(`/api/beakerhub/admin/node-images/${imageId}/import-status`, {
        headers: { 'Cache-Control': 'no-cache' },
      });
      if (!response.ok) {
        _scheduleImportPoll(imageId);
        return;
      }
      const data = await response.json();

      if (data.status === 'completed' || data.status === 'failed') {
        stopImportPoll(imageId);
        await fetchNodeImages();
        importEvents.value.push({
          imageId,
          slug: _resolveSlug(imageId),
          status: data.status,
          error: data.error,
          result: data.result,
        });
        return;
      }
    } catch {
      // Transient error — keep polling
    }
    _scheduleImportPoll(imageId);
  }

  function _scheduleImportPoll(imageId: number) {
    const timer = setTimeout(() => _importPollTick(imageId), IMPORT_POLL_INTERVAL_MS);
    _importPolls.set(imageId, timer);
  }

  function startImportPoll(imageId: number) {
    if (_importPolls.has(imageId)) {
      return;
    }
    importingImages[imageId] = true;
    _scheduleImportPoll(imageId);
  }

  function stopImportPoll(imageId: number) {
    const timer = _importPolls.get(imageId);
    if (timer !== undefined) {
      clearTimeout(timer);
      _importPolls.delete(imageId);
    }
    delete importingImages[imageId];
  }

  /** Consume and clear all pending import events. */
  function consumeImportEvents(): ImportEvent[] {
    const events = importEvents.value.splice(0);
    return events;
  }

  /**
   * Scan the current nodeImages list and start polling for any that have
   * a pending/running import. Call after fetchNodeImages to pick up
   * imports started before the current page load.
   */
  function resumeImportPolls() {
    for (const image of nodeImages.value) {
      const status = image.last_import?.status;
      if ((status === 'pending' || status === 'running') && !_importPolls.has(image.id)) {
        startImportPoll(image.id);
      }
    }
  }

  async function fetchAllWorkflows(): Promise<void> {
    const response = await fetch('/api/beakerhub/admin/workflows');
    if (response.ok) {
      const data = await response.json();
      allWorkflows.value = data.workflows;
    }
  }

  async function fetchAllIntegrations(): Promise<void> {
    const response = await fetch('/api/beakerhub/admin/integrations');
    if (response.ok) {
      const data = await response.json();
      allIntegrations.value = data.integrations;
    }
  }

  async function fetchAllLanguages(): Promise<void> {
    const response = await fetch('/api/beakerhub/admin/languages');
    if (response.ok) {
      const data = await response.json();
      allLanguages.value = data.languages;
    }
  }

  async function fetchAllApiKeys(): Promise<void> {
    const response = await fetch('/api/beakerhub/admin/api-keys');
    if (response.ok) {
      const data = await response.json();
      allApiKeys.value = data.api_keys;
    }
  }

  async function createApiKey(payload: { display_name: string; env_var: string; description?: string }): Promise<AdminApiKey | null> {
    const response = await fetch('/api/beakerhub/admin/api-keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (response.ok) {
      const created = await response.json();
      await fetchAllApiKeys();
      return created;
    }
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || 'Failed to create API key');
  }

  // ============================================
  // Secret Vault API
  // ============================================

  async function fetchSecrets(nodeImageId?: number | 'global'): Promise<VaultSecret[]> {
    let url = '/api/beakerhub/admin/secrets';
    if (nodeImageId !== undefined) {
      url += `?node_image_id=${nodeImageId}`;
    }
    const response = await fetch(url);
    if (response.ok) {
      const data = await response.json();
      // Normalize the policy overrides so callers can rely on the key existing.
      return (data.secrets as VaultSecret[]).map(secret => ({
        ...secret,
        policies: secret.policies || {},
      }));
    }
    return [];
  }

  async function fetchSecret(id: number): Promise<VaultSecretWithValue | null> {
    const response = await fetch(`/api/beakerhub/admin/secrets/${id}`);
    if (response.ok) {
      return await response.json();
    }
    return null;
  }

  async function upsertSecret(payload: {
    node_image_id: number | null;
    env_var: string;
    value: string;
    description?: string;
    policies?: SecretPolicies;
  }): Promise<VaultSecret> {
    const response = await fetch('/api/beakerhub/admin/secrets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (response.ok) {
      return await response.json();
    }
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || 'Failed to save secret');
  }

  async function updateSecret(id: number, payload: Record<string, any>): Promise<VaultSecret> {
    const response = await fetch(`/api/beakerhub/admin/secrets/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (response.ok) {
      return await response.json();
    }
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || 'Failed to update secret');
  }

  async function deleteSecret(id: number): Promise<boolean> {
    const response = await fetch(`/api/beakerhub/admin/secrets/${id}`, {
      method: 'DELETE',
    });
    return response.ok || response.status === 204;
  }

  async function fetchContextSecrets(sourceKey: string): Promise<ContextSecretOverride[]> {
    const response = await fetch(`/api/beakerhub/admin/contexts/${encodeURIComponent(sourceKey)}/secrets`);
    if (response.ok) {
      const data = await response.json();
      return (data.secrets as ContextSecretOverride[]).map(secret => ({
        ...secret,
        policies: secret.policies || {},
      }));
    }
    return [];
  }

  async function updateContextSecrets(
    sourceKey: string,
    overrides: { node_secret_id: number; enabled: boolean }[],
  ): Promise<void> {
    const response = await fetch(`/api/beakerhub/admin/contexts/${encodeURIComponent(sourceKey)}/secrets`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ overrides }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: response.statusText }));
      throw new Error(error.message || 'Failed to update context secrets');
    }
  }

  async function fetchAllSupportingEntities(): Promise<void> {
    await Promise.all([
      fetchNodeImages(),
      fetchAllWorkflows(),
      fetchAllIntegrations(),
      fetchAllLanguages(),
      fetchAllApiKeys(),
    ]);
  }

  // ============================================
  // Integration Detail API
  // ============================================

  async function fetchIntegration(id: number): Promise<AdminIntegrationDetail | null> {
    const response = await fetch(`/api/beakerhub/admin/integrations/${id}`);
    if (response.ok) {
      return await response.json();
    }
    return null;
  }

  async function updateIntegration(id: number, payload: Record<string, any>): Promise<AdminIntegrationDetail | null> {
    const response = await fetch(`/api/beakerhub/admin/integrations/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (response.ok) {
      return await response.json();
    }
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || 'Failed to update integration');
  }

  // ============================================
  // Workflow & Stage Detail API
  // ============================================

  async function fetchWorkflow(id: number): Promise<AdminWorkflowDetail | null> {
    const response = await fetch(`/api/beakerhub/admin/workflows/${id}`);
    if (response.ok) {
      return await response.json();
    }
    return null;
  }

  async function updateWorkflow(id: number, payload: Record<string, any>): Promise<AdminWorkflowDetail | null> {
    const response = await fetch(`/api/beakerhub/admin/workflows/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (response.ok) {
      return await response.json();
    }
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || 'Failed to update workflow');
  }

  async function fetchWorkflowStage(workflowId: number, stageId: number): Promise<AdminWorkflowStage | null> {
    const response = await fetch(`/api/beakerhub/admin/workflows/${workflowId}/stages/${stageId}`);
    if (response.ok) {
      return await response.json();
    }
    return null;
  }

  async function updateWorkflowStage(
    workflowId: number,
    stageId: number,
    payload: Record<string, any>,
  ): Promise<AdminWorkflowStage | null> {
    const response = await fetch(`/api/beakerhub/admin/workflows/${workflowId}/stages/${stageId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (response.ok) {
      return await response.json();
    }
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || 'Failed to update stage');
  }

  // ============================================
  // User Management (JupyterHub API)
  // ============================================

  async function fetchUsers(): Promise<void> {
    usersLoading.value = true;
    try {
      const response = await fetch('/api/users', {
        headers: { 'Accept': 'application/jupyterhub-pagination+json' },
      });
      if (response.ok) {
        const data = await response.json();
        users.value = data.items;
      }
    } finally {
      usersLoading.value = false;
    }
  }

  async function updateUser(username: string, payload: Record<string, any>): Promise<boolean> {
    const response = await fetch(`/api/users/${encodeURIComponent(username)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (response.ok) {
      await fetchUsers();
      return true;
    }
    return false;
  }

  // ============================================
  // Server Management (JupyterHub API)
  // ============================================

  async function stopServer(username: string, serverName: string): Promise<boolean> {
    const response = await fetch(
      `/api/users/${encodeURIComponent(username)}/servers/${encodeURIComponent(serverName)}`,
      {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        // Remove the spawner record as well as stopping the server. Without
        // this the record persists and the session reappears as stopped.
        body: JSON.stringify({ remove: true }),
      },
    );
    if (response.ok || response.status === 204) {
      await fetchUsers();
      return true;
    }
    return false;
  }

  // ============================================
  // Dashboard API
  // ============================================

  async function fetchDashboardSummary(): Promise<void> {
    dashboardSummaryLoading.value = true;
    try {
      const response = await fetch('/api/beakerhub/admin/dashboard/summary');
      if (response.ok) {
        dashboardSummary.value = await response.json();
      }
    } finally {
      dashboardSummaryLoading.value = false;
    }
  }

  async function fetchClusterInfo(): Promise<void> {
    clusterInfoLoading.value = true;
    try {
      const response = await fetch('/api/beakerhub/admin/dashboard/cluster');
      if (response.ok) {
        clusterInfo.value = await response.json();
      }
    } finally {
      clusterInfoLoading.value = false;
    }
  }

  async function fetchPodLogs(
    username: string,
    serverName: string,
    tailLines: number = 5000
  ): Promise<PodLogsResponse> {
    const params = new URLSearchParams({
      container: 'notebook',
      tail_lines: String(tailLines),
    });
    const response = await fetch(
      `/api/beakerhub/admin/dashboard/pod-logs/${encodeURIComponent(username)}/${encodeURIComponent(serverName)}?${params}`
    );
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || response.statusText);
    }
    return await response.json();
  }

  return {
    // State
    contexts,
    contextsLoading,
    users,
    usersLoading,
    dashboardSummary,
    dashboardSummaryLoading,
    clusterInfo,
    clusterInfoLoading,
    nodeImages,
    nodeImagesLoading,
    registryName,
    registryImages,
    registryImagesLoading,
    registryImagesError,
    allWorkflows,
    allIntegrations,
    allLanguages,
    allApiKeys,

    // Context actions
    fetchContexts,
    fetchContext,
    createContext,
    updateContext,
    deleteContext,

    // Node image actions
    fetchNodeImages,
    fetchRegistryImages,
    createNodeImage,
    updateNodeImage,
    deleteNodeImage,
    pullNodeImage,

    // Import polling
    importingImages,
    importEvents,
    startImportPoll,
    stopImportPoll,
    consumeImportEvents,
    resumeImportPolls,

    // Supporting entity actions
    fetchAllWorkflows,
    fetchAllIntegrations,
    fetchAllLanguages,
    fetchAllApiKeys,
    createApiKey,
    fetchAllSupportingEntities,

    // Integration detail actions
    fetchIntegration,
    updateIntegration,

    // Workflow & stage detail actions
    fetchWorkflow,
    updateWorkflow,
    fetchWorkflowStage,
    updateWorkflowStage,

    // User actions
    fetchUsers,
    updateUser,

    // Server actions
    stopServer,

    // Vault actions
    fetchSecrets,
    fetchSecret,
    upsertSecret,
    updateSecret,
    deleteSecret,
    fetchContextSecrets,
    updateContextSecrets,

    // Dashboard actions
    fetchDashboardSummary,
    fetchClusterInfo,
    fetchPodLogs,
  };
});
