<template>
  <div class="admin-sessions">
    <div class="page-header">
      <div>
        <h1>Session Management</h1>
        <p>View and manage active sessions across all users.</p>
      </div>
      <Button label="Refresh" icon="pi pi-refresh" text @click="refresh()" />
    </div>

    <DataTable
      :value="serverList"
      :loading="adminStore.usersLoading"
      stripedRows
      sortField="started"
      :sortOrder="-1"
      class="sessions-table"
    >
      <Column field="user" header="User" sortable />
      <Column field="name" header="Server Name" sortable />
      <Column header="Context" sortable sortField="contextName">
        <template #body="{ data }">
          {{ data.contextName }}
        </template>
      </Column>
      <Column field="ready" header="Status" sortable style="width: 8rem;">
        <template #body="{ data }">
          <Tag v-if="data.ready" value="Ready" severity="success" />
          <Tag v-else-if="data.pending" :value="data.pending" severity="warn" />
          <Tag v-else value="Stopped" severity="danger" />
        </template>
      </Column>
      <Column field="started" header="Started" sortable>
        <template #body="{ data }">
          {{ formatDate(data.started) }}
        </template>
      </Column>
      <Column field="last_activity" header="Last Activity" sortable>
        <template #body="{ data }">
          {{ formatDate(data.last_activity) }}
        </template>
      </Column>
      <Column header="Actions" style="width: 12rem;">
        <template #body="{ data }">
          <Button
            icon="pi pi-list"
            label="Logs"
            text
            size="small"
            @click="openLogs(data)"
            :disabled="!data.ready"
          />
          <Button
            icon="pi pi-stop-circle"
            label="Stop"
            text
            size="small"
            severity="danger"
            @click="confirmStop(data)"
            :disabled="!data.ready && !data.pending"
          />
        </template>
      </Column>
    </DataTable>

    <p v-if="!adminStore.usersLoading && serverList.length === 0" class="empty-message">
      No active sessions found.
    </p>

    <PodLogViewer
      v-model:visible="logsDialogVisible"
      :username="logsTarget.user"
      :serverName="logsTarget.name"
    />
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted } from 'vue';
import { useConfirm } from 'primevue/useconfirm';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Button from 'primevue/button';
import Tag from 'primevue/tag';
import { useAdminStore } from '@/stores/admin';
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
const logsDialogVisible = ref(false);
const logsTarget = ref<{ user: string; name: string }>({ user: '', name: '' });

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
  refresh();
});

function refresh() {
  adminStore.fetchUsers();
}

function formatDate(isoString: string | null): string {
  if (!isoString) return '—';
  const date = new Date(isoString);
  return date.toLocaleString();
}

function getContextName(slug: string | undefined): string {
  if (!slug) return 'Unknown';
  const context = contextStore.contexts?.find(c => c.slug === slug);
  return context?.display_name ?? slug;
}

function openLogs(server: ServerRow) {
  logsTarget.value = { user: server.user, name: server.name };
  logsDialogVisible.value = true;
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
</script>

<style lang="scss" scoped>
.admin-sessions {
  h1 {
    margin: 0 0 0.5rem;
    font-size: 1.5rem;
  }

  p {
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

.sessions-table {
  margin-top: 1rem;
}

.empty-message {
  text-align: center;
  padding: 2rem;
  color: var(--p-text-secondary-color);
}
</style>
