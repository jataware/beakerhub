<template>
  <div class="admin-dashboard">
    <div class="page-header">
      <div>
        <h1>Dashboard</h1>
        <p>System overview and quick actions.</p>
      </div>
      <div class="header-actions">
        <span v-if="autoRefreshActive" class="auto-refresh-badge" title="Auto-refreshing every 30 seconds">
          <i class="pi pi-sync pi-spin" /> Auto
        </span>
        <Button label="Refresh" icon="pi pi-refresh" text @click="refreshAll()" :loading="refreshing" />
      </div>
    </div>

    <!-- Summary Cards -->
    <div class="summary-cards">
      <router-link :to="{ name: 'admin-sessions' }" class="summary-card card-sessions">
        <div class="card-icon"><i class="pi pi-server" /></div>
        <div class="card-body">
          <div class="card-value">{{ counts?.sessions.active_servers ?? '...' }}</div>
          <div class="card-label">Active Sessions</div>
        </div>
      </router-link>

      <router-link :to="{ name: 'admin-users' }" class="summary-card card-users">
        <div class="card-icon"><i class="pi pi-users" /></div>
        <div class="card-body">
          <div class="card-value">{{ counts?.users.total ?? '...' }}</div>
          <div class="card-label">Users</div>
          <div class="card-detail" v-if="counts">{{ counts.users.admin }} admin</div>
        </div>
      </router-link>

      <router-link :to="{ name: 'admin-contexts' }" class="summary-card card-contexts">
        <div class="card-icon"><i class="pi pi-box" /></div>
        <div class="card-body">
          <div class="card-value">{{ counts?.contexts.total ?? '...' }}</div>
          <div class="card-label">Contexts</div>
          <div class="card-detail" v-if="counts">{{ counts.contexts.enabled }} enabled</div>
        </div>
      </router-link>

      <router-link :to="{ name: 'admin-images' }" class="summary-card card-images">
        <div class="card-icon"><i class="pi pi-image" /></div>
        <div class="card-body">
          <div class="card-value">{{ counts?.images.total ?? '...' }}</div>
          <div class="card-label">Images</div>
          <div class="card-detail" v-if="counts">{{ counts.images.enabled }} enabled</div>
        </div>
      </router-link>

      <div class="summary-card card-workflows">
        <div class="card-icon"><i class="pi pi-sitemap" /></div>
        <div class="card-body">
          <div class="card-value">{{ counts?.workflows.total ?? '...' }}</div>
          <div class="card-label">Workflows</div>
          <div class="card-detail" v-if="counts">{{ counts.workflows.enabled }} enabled</div>
        </div>
      </div>

      <div class="summary-card card-integrations">
        <div class="card-icon"><i class="pi pi-link" /></div>
        <div class="card-body">
          <div class="card-value">{{ counts?.integrations.total ?? '...' }}</div>
          <div class="card-label">Integrations</div>
          <div class="card-detail" v-if="counts">{{ counts.integrations.enabled }} enabled</div>
        </div>
      </div>

      <router-link :to="{ name: 'admin-vault' }" class="summary-card card-secrets">
        <div class="card-icon"><i class="pi pi-lock" /></div>
        <div class="card-body">
          <div class="card-value">{{ counts?.secrets.total ?? '...' }}</div>
          <div class="card-label">Secrets</div>
          <div class="card-detail" v-if="counts">{{ counts.secrets.global }} global</div>
        </div>
      </router-link>

      <div class="summary-card card-languages">
        <div class="card-icon"><i class="pi pi-code" /></div>
        <div class="card-body">
          <div class="card-value">{{ counts?.languages.total ?? '...' }}</div>
          <div class="card-label">Languages</div>
        </div>
      </div>
    </div>

    <!-- Main content: two-column layout -->
    <div class="dashboard-panels">
      <!-- Sessions Panel -->
      <div class="panel">
        <div class="panel-header">
          <h2>Active Sessions</h2>
          <router-link :to="{ name: 'admin-sessions' }" class="panel-link">View all</router-link>
        </div>
        <DataTable
          :value="serverList"
          :loading="adminStore.usersLoading"
          stripedRows
          sortField="started"
          :sortOrder="-1"
          :rows="10"
          :paginator="serverList.length > 10"
          class="compact-table"
        >
          <template #empty>
            <div class="empty-message">No active sessions.</div>
          </template>
          <Column field="user" header="User" sortable />
          <Column field="name" header="Server" sortable />
          <Column header="Context" sortable sortField="contextName">
            <template #body="{ data }">
              {{ data.contextName }}
            </template>
          </Column>
          <Column field="ready" header="Status" sortable style="width: 7rem;">
            <template #body="{ data }">
              <Tag v-if="data.ready" value="Ready" severity="success" />
              <Tag v-else-if="data.pending" :value="data.pending" severity="warn" />
              <Tag v-else value="Stopped" severity="danger" />
            </template>
          </Column>
          <Column field="last_activity" header="Last Activity" sortable>
            <template #body="{ data }">
              {{ formatRelative(data.last_activity) }}
            </template>
          </Column>
          <Column header="" style="width: 7rem;">
            <template #body="{ data }">
              <Button
                icon="pi pi-list"
                text
                size="small"
                @click="openLogs(data)"
                :disabled="!data.ready"
                title="View logs"
              />
              <Button
                icon="pi pi-stop-circle"
                text
                size="small"
                severity="danger"
                @click="confirmStop(data)"
                :disabled="!data.ready && !data.pending"
                title="Stop session"
              />
            </template>
          </Column>
        </DataTable>
      </div>

      <!-- Recent Imports Panel -->
      <div class="panel">
        <div class="panel-header">
          <h2>Recent Imports</h2>
          <router-link :to="{ name: 'admin-images' }" class="panel-link">Images</router-link>
        </div>
        <DataTable
          :value="recentImports"
          :loading="adminStore.dashboardSummaryLoading"
          stripedRows
          class="compact-table"
        >
          <template #empty>
            <div class="empty-message">No import tasks found.</div>
          </template>
          <Column field="node_image_slug" header="Image" sortable />
          <Column field="status" header="Status" style="width: 8rem;">
            <template #body="{ data }">
              <span class="import-status" :class="data.status">
                <i :class="importStatusIcon(data.status)" />
                {{ data.status }}
              </span>
            </template>
          </Column>
          <Column field="updated_at" header="Updated">
            <template #body="{ data }">
              {{ formatRelative(data.updated_at || data.created_at) }}
            </template>
          </Column>
          <Column field="error" header="Details">
            <template #body="{ data }">
              <span v-if="data.error" class="import-error" :title="data.error">
                {{ truncate(data.error, 60) }}
              </span>
              <span v-else-if="data.result" class="import-result">
                {{ formatImportResult(data.result) }}
              </span>
              <span v-else class="text-muted">—</span>
            </template>
          </Column>
        </DataTable>
      </div>
    </div>

    <!-- Kubernetes Cluster Info -->
    <div class="panel cluster-panel" v-if="clusterInfo">
      <div class="panel-header">
        <h2>Kubernetes Cluster</h2>
        <span v-if="clusterInfo.namespace" class="namespace-badge">{{ clusterInfo.namespace }}</span>
      </div>

      <div v-if="!clusterInfo.available" class="cluster-unavailable">
        <i class="pi pi-info-circle" />
        <span>Cluster information is unavailable. {{ clusterInfo.error || 'Insufficient permissions or not running in-cluster.' }}</span>
      </div>

      <template v-else>
        <div class="cluster-grid">
          <!-- Pod Summary -->
          <div class="cluster-section">
            <h3>Pods</h3>
            <div class="cluster-stat-row">
              <span class="stat-label">Total</span>
              <span class="stat-value">{{ clusterInfo.pods?.total ?? 0 }}</span>
            </div>
            <div class="cluster-stat-row" v-for="(count, phase) in clusterInfo.pods?.by_phase" :key="phase">
              <span class="stat-label">{{ phase }}</span>
              <Tag :value="String(count)" :severity="phaseSeverity(String(phase))" />
            </div>
            <div class="component-breakdown" v-if="clusterInfo.pods?.by_component">
              <div class="component-row" v-for="(info, name) in clusterInfo.pods.by_component" :key="name">
                <span class="component-name">{{ name }}</span>
                <span class="component-count">{{ info.count }}</span>
              </div>
            </div>
          </div>

          <!-- PVCs -->
          <div class="cluster-section">
            <h3>Storage</h3>
            <div v-for="pvc in clusterInfo.pvcs" :key="pvc.name" class="pvc-row">
              <span class="pvc-name">{{ pvc.name }}</span>
              <span class="pvc-detail">
                {{ pvc.capacity || '?' }} &middot;
                <Tag :value="pvc.phase" :severity="pvc.phase === 'Bound' ? 'success' : 'warn'" />
              </span>
            </div>
            <div v-if="!clusterInfo.pvcs?.length" class="text-muted">No PVCs found.</div>
          </div>

          <!-- Jobs -->
          <div class="cluster-section">
            <h3>Import Jobs</h3>
            <div class="cluster-stat-row">
              <span class="stat-label">Total</span>
              <span class="stat-value">{{ clusterInfo.jobs?.total ?? 0 }}</span>
            </div>
            <div class="cluster-stat-row">
              <span class="stat-label">Active</span>
              <Tag :value="String(clusterInfo.jobs?.active ?? 0)" :severity="(clusterInfo.jobs?.active ?? 0) > 0 ? 'info' : 'secondary'" />
            </div>
            <div class="cluster-stat-row">
              <span class="stat-label">Succeeded</span>
              <Tag :value="String(clusterInfo.jobs?.succeeded ?? 0)" severity="success" />
            </div>
            <div class="cluster-stat-row">
              <span class="stat-label">Failed</span>
              <Tag :value="String(clusterInfo.jobs?.failed ?? 0)" :severity="(clusterInfo.jobs?.failed ?? 0) > 0 ? 'danger' : 'secondary'" />
            </div>
          </div>
        </div>

        <!-- Nodes & Helm Releases row -->
        <div class="cluster-grid cluster-grid-2col">
          <!-- Nodes -->
          <div class="cluster-section">
            <h3>Nodes</h3>
            <div v-if="clusterNodes.length === 0" class="text-muted">No node info available.</div>
            <div v-else-if="clusterNodes[0]?.error" class="text-muted">
              Node info unavailable (requires ClusterRole).
            </div>
            <div v-else class="node-list">
              <div v-for="node in clusterNodes" :key="node.name" class="node-card">
                <div class="node-header">
                  <span class="node-name">{{ node.name }}</span>
                  <Tag :value="node.ready ? 'Ready' : 'NotReady'" :severity="node.ready ? 'success' : 'danger'" />
                </div>
                <div class="node-details">
                  <div class="node-detail-row" v-if="node.instance_type">
                    <span class="detail-label">Instance</span>
                    <span class="detail-value">{{ node.instance_type }}</span>
                  </div>
                  <div class="node-detail-row">
                    <span class="detail-label">CPU</span>
                    <span class="detail-value resource-bar-cell">
                      <span class="resource-text">{{ node.allocated?.cpu ?? '0' }} / {{ node.allocatable?.cpu ?? '?' }}</span>
                      <div class="resource-bar" :title="`${node.allocated?.cpu ?? '0'} allocated of ${node.allocatable?.cpu ?? '?'} allocatable`">
                        <div class="resource-bar-fill" :class="utilizationClass(node.allocated?.cpu, node.allocatable?.cpu)" :style="{ width: utilizationPct(node.allocated?.cpu, node.allocatable?.cpu) + '%' }"></div>
                      </div>
                    </span>
                  </div>
                  <div class="node-detail-row">
                    <span class="detail-label">Memory</span>
                    <span class="detail-value resource-bar-cell">
                      <span class="resource-text">{{ formatMemory(node.allocated?.memory) }} / {{ formatMemory(node.allocatable?.memory) }}</span>
                      <div class="resource-bar" :title="`${formatMemory(node.allocated?.memory)} allocated of ${formatMemory(node.allocatable?.memory)} allocatable`">
                        <div class="resource-bar-fill" :class="utilizationClass(node.allocated?.memory, node.allocatable?.memory)" :style="{ width: utilizationPct(node.allocated?.memory, node.allocatable?.memory) + '%' }"></div>
                      </div>
                    </span>
                  </div>
                  <div class="node-detail-row">
                    <span class="detail-label">Pods</span>
                    <span class="detail-value resource-bar-cell">
                      <span class="resource-text">{{ node.allocated?.pods ?? '0' }} / {{ node.allocatable?.pods ?? '?' }}</span>
                      <div class="resource-bar" :title="`${node.allocated?.pods ?? '0'} allocated of ${node.allocatable?.pods ?? '?'} allocatable`">
                        <div class="resource-bar-fill" :class="utilizationClass(node.allocated?.pods, node.allocatable?.pods)" :style="{ width: utilizationPct(node.allocated?.pods, node.allocatable?.pods) + '%' }"></div>
                      </div>
                    </span>
                  </div>
                  <div class="node-detail-row" v-if="node.kubelet_version">
                    <span class="detail-label">Kubelet</span>
                    <span class="detail-value">{{ node.kubelet_version }}</span>
                  </div>
                  <div class="node-detail-row" v-if="node.container_runtime">
                    <span class="detail-label">Runtime</span>
                    <span class="detail-value">{{ node.container_runtime }}</span>
                  </div>
                  <div class="node-detail-row" v-if="node.os || node.arch">
                    <span class="detail-label">Platform</span>
                    <span class="detail-value">{{ [node.os, node.arch].filter(Boolean).join('/') }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Helm Releases -->
          <div class="cluster-section">
            <h3>Helm Releases</h3>
            <div v-if="helmReleases.length === 0" class="text-muted">No Helm releases found.</div>
            <div v-else-if="helmReleases[0]?.error" class="text-muted">
              Cannot read Helm release info.
            </div>
            <div v-else class="helm-list">
              <div v-for="rel in helmReleases" :key="rel.name" class="helm-row">
                <div class="helm-name">{{ rel.name }}</div>
                <div class="helm-meta">
                  <Tag :value="rel.status" :severity="rel.status === 'deployed' ? 'success' : 'warn'" />
                  <span class="helm-version">rev {{ rel.version }}</span>
                  <span v-if="rel.updated" class="helm-updated">{{ formatRelative(rel.updated) }}</span>
                </div>
              </div>
            </div>
            <!-- App version from summary -->
            <div class="app-version-info" v-if="counts">
              <div class="version-row">
                <span class="detail-label">BeakerHub</span>
                <span class="detail-value version-value">v{{ appVersion }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Recent Events -->
        <div class="events-section" v-if="clusterInfo.events?.length">
          <h3>Recent Warnings</h3>
          <DataTable :value="clusterInfo.events" stripedRows class="compact-table events-table">
            <Column field="reason" header="Reason" style="width: 10rem;" />
            <Column field="involved_object" header="Object" style="width: 12rem;" />
            <Column field="message" header="Message">
              <template #body="{ data }">
                <span :title="data.message">{{ truncate(data.message, 100) }}</span>
              </template>
            </Column>
            <Column field="last_timestamp" header="Time" style="width: 10rem;">
              <template #body="{ data }">
                {{ formatRelative(data.last_timestamp) }}
              </template>
            </Column>
            <Column field="count" header="Count" style="width: 5rem;" />
          </DataTable>
        </div>
      </template>
    </div>

    <PodLogViewer
      v-model:visible="logsDialogVisible"
      :username="logsTarget.user"
      :serverName="logsTarget.name"
    />
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useConfirm } from 'primevue/useconfirm';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Button from 'primevue/button';
import Tag from 'primevue/tag';
import { useAdminStore } from '@/stores/admin';
import type { DashboardCounts, DashboardImport, ClusterInfo, ClusterNode, HelmRelease } from '@/stores/admin';
import { useContextStore } from '@/stores/context';
import PodLogViewer from '@/components/admin/PodLogViewer.vue';

interface ServerRow {
  user: string;
  name: string;
  ready: boolean;
  pending: string | null;
  url: string;
  started: string;
  last_activity: string;
  contextName: string;
}

const adminStore = useAdminStore();
const contextStore = useContextStore();
const confirm = useConfirm();
const refreshing = ref(false);
let refreshTimer: ReturnType<typeof setInterval> | null = null;
const autoRefreshActive = ref(false);
const logsDialogVisible = ref(false);
const logsTarget = ref<{ user: string; name: string }>({ user: '', name: '' });

const counts = computed<DashboardCounts | null>(() => adminStore.dashboardSummary?.counts ?? null);
const recentImports = computed<DashboardImport[]>(() => adminStore.dashboardSummary?.recent_imports ?? []);
const clusterInfo = computed<ClusterInfo | null>(() => adminStore.clusterInfo);
const clusterNodes = computed<ClusterNode[]>(() => adminStore.clusterInfo?.nodes ?? []);
const helmReleases = computed<HelmRelease[]>(() => adminStore.clusterInfo?.helm_releases ?? []);
const appVersion = computed(() => adminStore.dashboardSummary?.app_version ?? '...');

const serverList = computed<ServerRow[]>(() => {
  const rows: ServerRow[] = [];
  for (const user of adminStore.users) {
    if (!user.servers) continue;
    for (const [serverName, server] of Object.entries(user.servers)) {
      const contextSlug = server.user_options?.contextSlug;
      rows.push({
        user: user.name,
        name: serverName,
        ready: server.ready,
        pending: server.pending,
        url: server.url,
        started: server.started,
        last_activity: server.last_activity,
        contextName: getContextName(contextSlug),
      });
    }
  }
  return rows;
});

onMounted(() => {
  contextStore.ensureContextsLoaded();
  refreshAll();
  // Auto-refresh every 30 seconds
  refreshTimer = setInterval(() => {
    refreshAll(true);
  }, 30_000);
  autoRefreshActive.value = true;
});

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
  autoRefreshActive.value = false;
});

async function refreshAll(silent = false) {
  if (!silent) refreshing.value = true;
  try {
    await Promise.all([
      adminStore.fetchDashboardSummary(),
      adminStore.fetchUsers(),
      adminStore.fetchClusterInfo(),
    ]);
  } finally {
    refreshing.value = false;
  }
}

function openLogs(server: ServerRow) {
  logsTarget.value = { user: server.user, name: server.name };
  logsDialogVisible.value = true;
}

function getContextName(slug: string | undefined): string {
  if (!slug) return 'Unknown';
  const context = contextStore.contexts?.find(c => c.slug === slug);
  return context?.display_name ?? slug;
}

function confirmStop(server: ServerRow) {
  confirm.require({
    message: `Stop server "${server.name}" for user "${server.user}"?`,
    header: 'Confirm Stop',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      await adminStore.stopServer(server.user, server.name);
    },
  });
}

function formatRelative(isoString: string | null): string {
  if (!isoString) return '—';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 60) return 'just now';
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`;
  return date.toLocaleDateString();
}

function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen - 3) + '...';
}

function importStatusIcon(status: string): string {
  switch (status) {
    case 'completed': return 'pi pi-check-circle';
    case 'failed': return 'pi pi-times-circle';
    case 'running': return 'pi pi-spin pi-spinner';
    case 'pending': return 'pi pi-clock';
    default: return 'pi pi-question-circle';
  }
}

function formatImportResult(result: Record<string, number>): string {
  const parts: string[] = [];
  if (result.contexts_created) parts.push(`${result.contexts_created} ctx created`);
  if (result.contexts_updated) parts.push(`${result.contexts_updated} ctx updated`);
  if (result.workflows_created) parts.push(`${result.workflows_created} wf created`);
  if (result.workflows_updated) parts.push(`${result.workflows_updated} wf updated`);
  if (result.integrations_created) parts.push(`${result.integrations_created} int created`);
  if (!parts.length) return 'No changes';
  return parts.join(', ');
}

function parseCpuToMillicores(value: string | null | undefined): number {
  if (!value || value === '?') return 0;
  if (value.endsWith('m')) return parseInt(value.slice(0, -1), 10) || 0;
  return (parseFloat(value) || 0) * 1000;
}

function parseMemoryToKi(value: string | null | undefined): number {
  if (!value || value === '?') return 0;
  const match = value.match(/^([\d.]+)(Ki|Mi|Gi|Ti)?$/);
  if (!match) return 0;
  const num = parseFloat(match[1]);
  switch (match[2]) {
    case 'Ti': return num * 1024 * 1024 * 1024;
    case 'Gi': return num * 1024 * 1024;
    case 'Mi': return num * 1024;
    case 'Ki': return num;
    default: return num / 1024;
  }
}

function utilizationPct(allocated: string | null | undefined, allocatable: string | null | undefined): number {
  if (!allocated || !allocatable || allocatable === '?' || allocated === '?') return 0;
  let used: number;
  let total: number;
  // Memory values have Ki/Mi/Gi/Ti suffixes
  if (allocated.match(/[KMGTi]i?$/) || allocatable.match(/[KMGTi]i?$/)) {
    used = parseMemoryToKi(allocated);
    total = parseMemoryToKi(allocatable);
  } else {
    // CPU (e.g. '500m', '2') or plain numbers (pods)
    used = parseCpuToMillicores(allocated);
    total = parseCpuToMillicores(allocatable);
  }
  if (total === 0) return 0;
  return Math.min(Math.round((used / total) * 100), 100);
}

function utilizationClass(allocated: string | null | undefined, allocatable: string | null | undefined): string {
  const pct = utilizationPct(allocated, allocatable);
  if (pct >= 90) return 'bar-danger';
  if (pct >= 70) return 'bar-warn';
  return 'bar-ok';
}

function formatMemory(value: string | null | undefined): string {
  if (!value) return '?';
  // K8s memory is typically in Ki (kibibytes)
  const match = value.match(/^(\d+)(Ki|Mi|Gi|Ti)?$/);
  if (!match) return value;
  const num = parseInt(match[1], 10);
  const unit = match[2] || '';
  if (unit === 'Ki') {
    if (num >= 1048576) return `${(num / 1048576).toFixed(1)}Ti`;
    if (num >= 1024) return `${(num / 1024).toFixed(1)}Gi`;
    return `${num}Ki`;
  }
  if (unit === 'Mi') {
    if (num >= 1024) return `${(num / 1024).toFixed(1)}Gi`;
    return `${num}Mi`;
  }
  return value;
}

function phaseSeverity(phase: string): "success" | "info" | "warn" | "danger" | "secondary" {
  switch (phase) {
    case 'Running': return 'success';
    case 'Succeeded': return 'info';
    case 'Pending': return 'warn';
    case 'Failed': return 'danger';
    default: return 'secondary';
  }
}
</script>

<style lang="scss" scoped>
.admin-dashboard {
  h1 {
    margin: 0 0 0.5rem;
    font-size: 1.5rem;
  }

  > p {
    margin: 0;
    color: var(--p-text-secondary-color);
  }
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.auto-refresh-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
  color: var(--p-text-secondary-color);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  background: var(--p-surface-b, #f8f9fa);
}

/* Summary Cards */
.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.summary-card {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 1rem 1.15rem;
  border: 1px solid var(--p-surface-border, #dee2e6);
  border-radius: 8px;
  background: var(--p-surface-a, #fff);
  text-decoration: none;
  color: inherit;
  transition: box-shadow 0.15s ease, border-color 0.15s ease;

  &:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    border-color: var(--p-primary-color);
  }
}

a.summary-card {
  cursor: pointer;
}

.card-icon {
  font-size: 1.5rem;
  opacity: 0.7;
}

.card-sessions .card-icon { color: var(--p-green-500, #22c55e); }
.card-users .card-icon { color: var(--p-blue-500, #3b82f6); }
.card-contexts .card-icon { color: var(--p-purple-500, #a855f7); }
.card-images .card-icon { color: var(--p-orange-500, #f97316); }
.card-workflows .card-icon { color: var(--p-cyan-500, #06b6d4); }
.card-integrations .card-icon { color: var(--p-teal-500, #14b8a6); }
.card-secrets .card-icon { color: var(--p-red-500, #ef4444); }
.card-languages .card-icon { color: var(--p-indigo-500, #6366f1); }

.card-body {
  min-width: 0;
}

.card-value {
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1.2;
}

.card-label {
  font-size: 0.85rem;
  color: var(--p-text-secondary-color);
  font-weight: 500;
}

.card-detail {
  font-size: 0.75rem;
  color: var(--p-text-secondary-color);
  opacity: 0.8;
}

/* Panels */
.dashboard-panels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-bottom: 1.5rem;
}

@media (max-width: 1100px) {
  .dashboard-panels {
    grid-template-columns: 1fr;
  }
}

.panel {
  border: 1px solid var(--p-surface-border, #dee2e6);
  border-radius: 8px;
  background: var(--p-surface-a, #fff);
  padding: 1.25rem;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;

  h2 {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
  }
}

.panel-link {
  font-size: 0.85rem;
  color: var(--p-primary-color);
  text-decoration: none;

  &:hover {
    text-decoration: underline;
  }
}

.compact-table {
  font-size: 0.875rem;
}

.empty-message {
  text-align: center;
  padding: 1.5rem;
  color: var(--p-text-secondary-color);
}

/* Import status */
.import-status {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.85rem;

  &.completed { color: var(--p-green-500, #22c55e); }
  &.failed { color: var(--p-red-500, #ef4444); }
  &.running, &.pending { color: var(--p-yellow-600, #ca8a04); }
}

.import-error {
  font-size: 0.8rem;
  color: var(--p-red-500, #ef4444);
}

.import-result {
  font-size: 0.8rem;
  color: var(--p-text-secondary-color);
}

.text-muted {
  color: var(--p-text-secondary-color);
}

/* Cluster Panel */
.cluster-panel {
  margin-bottom: 1.5rem;
}

.namespace-badge {
  font-size: 0.8rem;
  font-family: monospace;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  background: var(--p-surface-b, #f0f0f0);
  color: var(--p-text-secondary-color);
}

.cluster-unavailable {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  border-radius: 6px;
  background: var(--p-surface-b, #f8f9fa);
  color: var(--p-text-secondary-color);
  font-size: 0.9rem;

  i { font-size: 1.1rem; }
}

.cluster-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
  margin-bottom: 1rem;
}

@media (max-width: 900px) {
  .cluster-grid {
    grid-template-columns: 1fr;
  }
}

.cluster-section {
  h3 {
    margin: 0 0 0.75rem;
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--p-text-color);
  }
}

.cluster-stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.3rem 0;
  font-size: 0.875rem;
}

.stat-label {
  color: var(--p-text-secondary-color);
}

.stat-value {
  font-weight: 600;
}

.component-breakdown {
  margin-top: 0.75rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--p-surface-border, #eee);
}

.component-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.2rem 0;
  font-size: 0.825rem;
}

.component-name {
  color: var(--p-text-secondary-color);
  text-transform: capitalize;
}

.component-count {
  font-weight: 500;
}

.pvc-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.35rem 0;
  font-size: 0.875rem;
}

.pvc-name {
  font-family: monospace;
  font-size: 0.8rem;
}

.pvc-detail {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.825rem;
}

/* Nodes & Helm Releases */
.cluster-grid-2col {
  grid-template-columns: 1fr 1fr;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--p-surface-border, #eee);
}

@media (max-width: 900px) {
  .cluster-grid-2col {
    grid-template-columns: 1fr;
  }
}

.node-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.node-card {
  border: 1px solid var(--p-surface-border, #eee);
  border-radius: 6px;
  padding: 0.75rem;
}

.node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.node-name {
  font-family: monospace;
  font-size: 0.85rem;
  font-weight: 600;
}

.node-details {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.node-detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.825rem;
}

.detail-label {
  color: var(--p-text-secondary-color);
  min-width: 5rem;
}

.detail-value {
  font-family: monospace;
  font-size: 0.8rem;
}

.resource-bar-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.2rem;
  min-width: 10rem;
}

.resource-text {
  white-space: nowrap;
}

.resource-bar {
  width: 100%;
  height: 6px;
  background: var(--p-surface-200, #e5e7eb);
  border-radius: 3px;
  overflow: hidden;
}

.resource-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.bar-ok {
  background-color: var(--p-green-500, #22c55e);
}

.bar-warn {
  background-color: var(--p-orange-500, #f97316);
}

.bar-danger {
  background-color: var(--p-red-500, #ef4444);
}

.helm-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.helm-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--p-surface-border, #eee);
  border-radius: 6px;
}

.helm-name {
  font-family: monospace;
  font-size: 0.85rem;
  font-weight: 600;
}

.helm-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.825rem;
}

.helm-version {
  color: var(--p-text-secondary-color);
}

.helm-updated {
  color: var(--p-text-secondary-color);
  font-size: 0.8rem;
}

.app-version-info {
  margin-top: 1rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--p-surface-border, #eee);
}

.version-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.875rem;
}

.version-value {
  font-weight: 600;
  color: var(--p-primary-color);
}

.events-section {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--p-surface-border, #eee);

  h3 {
    margin: 0 0 0.75rem;
    font-size: 0.95rem;
    font-weight: 600;
  }
}

.events-table {
  font-size: 0.8rem;
}
</style>
