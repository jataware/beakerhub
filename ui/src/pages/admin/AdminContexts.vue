<template>
  <div class="admin-contexts">
    <div class="page-header">
      <div>
        <h1>Context Management</h1>
        <p>Manage Beaker contexts, their configurations, and associated workflows.</p>
      </div>
      <div class="header-actions">
        <Button label="Refresh" icon="pi pi-refresh" text @click="adminStore.fetchContexts()" />
        <Button label="Add Context" icon="pi pi-plus" @click="router.push({ name: 'admin-context-edit', params: { sourceKey: 'new' } })" />
      </div>
    </div>

    <DataTable
      :value="adminStore.contexts"
      :loading="adminStore.contextsLoading"
      stripedRows
      sortField="weight"
      :sortOrder="1"
      class="contexts-table"
    >
      <Column field="display_name" header="Name" sortable>
        <template #body="{ data }">
          <router-link :to="{ name: 'admin-context-edit', params: { sourceKey: data.source_key } }" class="context-link">
            {{ data.display_name }}
          </router-link>
        </template>
      </Column>
      <Column field="slug" header="Slug" sortable />
      <Column field="theme" header="Theme" sortable />
      <Column field="image" header="Image" sortable>
        <template #body="{ data }">
          <span v-if="!data.image">—</span>
          <span v-else-if="data.image_enabled === false" class="image-disabled" title="Image is disabled — context will not appear to users">
            {{ data.image }}
            <i class="pi pi-exclamation-triangle" />
          </span>
          <span v-else>{{ data.image }}</span>
        </template>
      </Column>
      <Column field="weight" header="Weight" sortable style="width: 6rem; text-align: center;" />
      <Column header="Enabled" sortable :sortField="'enabled'" style="width: 10rem;">
        <template #body="{ data }">
          <div class="enabled-cell">
            <InputSwitch :modelValue="data.enabled" @update:modelValue="toggleEnabled(data)" />
            <Tag v-if="data.enabled && data.image_enabled === false" value="Image off" severity="warn" />
          </div>
        </template>
      </Column>
      <Column header="Actions" style="width: 8rem;">
        <template #body="{ data }">
          <Button
            icon="pi pi-pencil"
            text
            size="small"
            @click="router.push({ name: 'admin-context-edit', params: { sourceKey: data.source_key } })"
            title="Edit"
          />
          <Button
            icon="pi pi-trash"
            text
            size="small"
            severity="danger"
            @click="confirmDelete(data)"
            title="Delete"
          />
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<script lang="ts" setup>
import { onMounted } from 'vue';
import { useRouter } from 'vue-router';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Button from 'primevue/button';
import InputSwitch from 'primevue/inputswitch';
import Tag from 'primevue/tag';
import { useConfirm } from 'primevue/useconfirm';
import { useAdminStore } from '@/stores/admin';
import type { AdminContext } from '@/stores/admin';

const router = useRouter();
const adminStore = useAdminStore();
const confirm = useConfirm();

onMounted(() => {
  adminStore.fetchContexts();
});

async function toggleEnabled(context: AdminContext) {
  await adminStore.updateContext(context.source_key, { enabled: !context.enabled });
}

function confirmDelete(context: AdminContext) {
  confirm.require({
    message: `Permanently delete context "${context.display_name}"? This will remove all associated workflow links, integration links, and language assignments.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      await adminStore.deleteContext(context.source_key);
    },
  });
}
</script>

<style lang="scss" scoped>
.admin-contexts {
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.contexts-table {
  margin-top: 1rem;
}

.context-link {
  color: var(--p-primary-color);
  text-decoration: none;
  font-weight: 500;

  &:hover {
    text-decoration: underline;
  }
}

.image-disabled {
  color: var(--p-orange-500, #f59e0b);

  .pi {
    margin-left: 0.35rem;
    font-size: 0.85rem;
  }
}

.enabled-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
</style>
