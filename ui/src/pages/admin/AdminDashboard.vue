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
              <Tag v-else-if="data.pending" :value="pendingStatus(data.pending)" severity="warn" />
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

    <!-- Runtime Information -->
    <div class="panel cluster-panel" v-if="clusterInfo">
      <div class="panel-header">
        <div>
          <h2>Cluster Information</h2>
          <span v-if="clusterInfo.runtime" class="runtime-detail">
            {{ clusterInfo.runtime.provider }} &middot; {{ clusterInfo.runtime.scope }}
          </span>
        </div>
      </div>

      <div v-if="!clusterInfo.available" class="cluster-unavailable">
        <i class="pi pi-info-circle" />
        <span>Runtime information is unavailable. {{ clusterInfo.error || 'The service did not return status information.' }}</span>
      </div>

      <template v-else>
        <div v-if="clusterInfo.summary?.length" class="runtime-summary">
          <div v-for="item in clusterInfo.summary" :key="item.label" class="runtime-stat">
            <span class="stat-label">{{ item.label }}</span>
            <span class="stat-value">{{ item.value }}</span>
            <span v-if="item.detail" class="stat-detail">{{ item.detail }}</span>
          </div>
        </div>

        <div class="cluster-grid cluster-grid-2col">
          <div class="cluster-section">
            <h3>Services and Workloads</h3>
            <div v-if="!clusterInfo.workloads?.length" class="text-muted">No workloads found.</div>
            <div v-else class="runtime-list">
              <div v-for="workload in clusterInfo.workloads" :key="`${workload.kind}-${workload.name}`" class="runtime-workload">
                <div class="runtime-row">
                  <div>
                    <span class="runtime-name">{{ workload.name }}</span>
                    <span class="runtime-kind">{{ workload.kind }}</span>
                    <span v-for="session in workload.sessions" :key="`${session.user}-${session.name}`" class="runtime-session">
                      <i class="pi pi-user" /> {{ session.user }} / {{ session.name }}
                    </span>
                  </div>
                  <div class="runtime-status">
                    <span v-if="workload.detail" :title="workload.detail">{{ workload.detail }}</span>
                    <Tag :value="workload.status" :severity="statusSeverity(workload.status)" />
                  </div>
                </div>
                <div v-if="workload.children?.length" class="runtime-children">
                  <div v-for="task in workload.children" :key="task.name" class="runtime-row runtime-child">
                    <div>
                      <span class="runtime-name">{{ task.name }}</span>
                      <span class="runtime-kind">{{ task.kind }}</span>
                      <span v-for="session in task.sessions" :key="`${session.user}-${session.name}`" class="runtime-session">
                        <i class="pi pi-user" /> {{ session.user }} / {{ session.name }}
                      </span>
                    </div>
                    <div class="runtime-status">
                      <span v-if="task.detail" :title="task.detail">{{ task.detail }}</span>
                      <Tag :value="task.status" :severity="statusSeverity(task.status)" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="cluster-section">
            <h3>Resources</h3>
            <div v-if="!clusterInfo.resources?.length" class="text-muted">
              {{ clusterInfo.resources_empty_message || 'No resource information available.' }}
            </div>
            <div v-else class="resource-list">
              <div v-for="resource in clusterInfo.resources" :key="resource.name" class="resource-card">
                <div class="node-header">
                  <span class="node-name">{{ resource.name }}</span>
                  <Tag :value="resource.status" :severity="statusSeverity(resource.status)" />
                </div>
                <div v-for="detail in resource.details" :key="detail.label" class="node-detail-row">
                  <span class="detail-label">{{ detail.label }}</span>
                  <span class="detail-value">{{ detail.value }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="events-section" v-if="clusterInfo.alerts?.length">
          <h3>Recent Warnings</h3>
          <DataTable :value="clusterInfo.alerts" stripedRows class="compact-table events-table">
            <Column field="reason" header="Reason" style="width: 10rem;" />
            <Column field="object" header="Object" style="width: 12rem;" />
            <Column field="message" header="Message">
              <template #body="{ data }"><span :title="data.message">{{ truncate(data.message, 100) }}</span></template>
            </Column>
            <Column field="timestamp" header="Time" style="width: 10rem;">
              <template #body="{ data }">{{ formatRelative(data.timestamp) }}</template>
            </Column>
          </DataTable>
        </div>
      </template>
    </div>

    <SessionLogViewer
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
import type { DashboardCounts, DashboardImport, ClusterInfo } from '@/stores/admin';
import { useContextStore } from '@/stores/context';
import SessionLogViewer from '@/components/admin/SessionLogViewer.vue';

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

function pendingStatus(status: string): string {
  return status === 'stop' ? 'Shutting Down' : status;
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

function statusSeverity(status: string): "success" | "info" | "warn" | "danger" | "secondary" {
  switch (status.toLowerCase()) {
    case 'running':
    case 'ready':
    case 'active':
    case 'bound':
      return 'success';
    case 'pending':
    case 'provisioning':
      return 'warn';
    case 'failed':
    case 'unavailable':
    case 'stopped':
      return 'danger';
    default:
      return 'secondary';
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

.cluster-unavailable {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  border-radius: 6px;
  background: var(--p-surface-b, #f8f9fa);
  color: var(--p-text-secondary-color);
  font-size: 0.9rem;
}

.cluster-grid {
  display: grid;
  gap: 1.5rem;
}

.cluster-grid-2col {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.cluster-section h3 {
  margin: 0 0 0.75rem;
  font-size: 0.95rem;
  font-weight: 600;
}

.stat-label, .detail-label {
  color: var(--p-text-secondary-color);
}

.stat-value {
  font-size: 1.25rem;
  font-weight: 600;
}

.node-header, .node-detail-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.node-header {
  margin-bottom: 0.5rem;
}

.node-name, .detail-value {
  font-family: monospace;
  font-size: 0.8rem;
}

@media (max-width: 900px) {
  .cluster-grid-2col {
    grid-template-columns: 1fr;
  }
}

.runtime-detail {
  display: block;
  margin-top: 0.2rem;
  color: var(--p-text-secondary-color);
  font-size: 0.8rem;
}

.runtime-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.runtime-stat {
  display: grid;
  gap: 0.2rem;
  padding: 0.75rem;
  border-radius: 6px;
  background: var(--p-surface-b, #f8f9fa);
}

.stat-detail, .runtime-kind, .runtime-status, .runtime-session {
  color: var(--p-text-secondary-color);
  font-size: 0.8rem;
}

.runtime-session {
  display: block;
  margin-top: 0.2rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.runtime-list, .resource-list, .runtime-children {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.runtime-children {
  margin: -0.2rem 0 0 1rem;
  padding-left: 0.75rem;
  border-left: 2px solid var(--p-surface-border, #eee);
}

.runtime-child {
  background: var(--p-surface-b, #f8f9fa);
}

.runtime-row, .resource-card {
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--p-surface-border, #eee);
  border-radius: 6px;
}

.runtime-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: stretch;
  gap: 0.75rem;
}

.runtime-row > div,
.runtime-status > span {
  min-width: 0;
}

.runtime-row > div:first-child {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.runtime-status {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
}

.runtime-status > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.runtime-status :deep(.p-tag) {
  flex: 0 0 auto;
}

.runtime-name {
  display: block;
  overflow-wrap: anywhere;
  font-family: monospace;
  font-size: 0.85rem;
  font-weight: 600;
}

.runtime-status {
  text-align: right;
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
