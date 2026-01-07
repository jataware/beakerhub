<template>
  <div class="admin-users">
    <div class="page-header">
      <div>
        <h1>User Management</h1>
        <p>View and manage users, assign roles.</p>
      </div>
      <Button label="Refresh" icon="pi pi-refresh" text @click="adminStore.fetchUsers()" />
    </div>

    <DataTable
      :value="adminStore.users"
      :loading="adminStore.usersLoading"
      stripedRows
      sortField="name"
      :sortOrder="1"
      class="users-table"
    >
      <Column field="name" header="Username" sortable />
      <Column field="admin" header="Admin" sortable style="width: 6rem;">
        <template #body="{ data }">
          <InputSwitch :modelValue="data.admin" @update:modelValue="toggleAdmin(data)" />
        </template>
      </Column>
      <Column field="roles" header="Roles" sortable>
        <template #body="{ data }">
          <div class="roles-cell">
            <Tag v-for="role in data.roles" :key="role" :value="role" severity="info" class="role-tag" />
            <Button icon="pi pi-pencil" text size="small" @click="openRoleDialog(data)" title="Edit roles" />
          </div>
        </template>
      </Column>
      <Column field="created" header="Created" sortable>
        <template #body="{ data }">
          {{ formatDate(data.created) }}
        </template>
      </Column>
      <Column field="last_activity" header="Last Activity" sortable>
        <template #body="{ data }">
          {{ formatDate(data.last_activity) }}
        </template>
      </Column>
    </DataTable>

    <!-- Role editing dialog -->
    <Dialog v-model:visible="roleDialogVisible" header="Edit Roles" :modal="true" :style="{ width: '400px' }">
      <div v-if="editingUser" class="role-dialog-content">
        <p>Editing roles for <strong>{{ editingUser.name }}</strong></p>
        <div class="role-checkboxes">
          <div v-for="role in availableRoles" :key="role" class="role-checkbox-row">
            <Checkbox
              :inputId="`role-${role}`"
              :modelValue="editingRoles.includes(role)"
              :binary="true"
              @update:modelValue="(checked: boolean) => toggleRole(role, checked)"
            />
            <label :for="`role-${role}`">{{ role }}</label>
          </div>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="roleDialogVisible = false" />
        <Button label="Save" @click="saveRoles" :loading="savingRoles" />
      </template>
    </Dialog>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted } from 'vue';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Button from 'primevue/button';
import InputSwitch from 'primevue/inputswitch';
import Tag from 'primevue/tag';
import Dialog from 'primevue/dialog';
import Checkbox from 'primevue/checkbox';
import { useAdminStore } from '@/stores/admin';
import type { JupyterHubUser } from '@/stores/admin';

const adminStore = useAdminStore();

const roleDialogVisible = ref(false);
const editingUser = ref<JupyterHubUser | null>(null);
const editingRoles = ref<string[]>([]);
const savingRoles = ref(false);

// Collect available roles from all users
const availableRoles = computed(() => {
  const roleSet = new Set<string>();
  for (const user of adminStore.users) {
    for (const role of user.roles) {
      roleSet.add(role);
    }
  }
  return Array.from(roleSet).sort();
});

onMounted(() => {
  adminStore.fetchUsers();
});

function formatDate(isoString: string | null): string {
  if (!isoString) return '—';
  const date = new Date(isoString);
  return date.toLocaleString();
}

async function toggleAdmin(user: JupyterHubUser) {
  await adminStore.updateUser(user.name, { admin: !user.admin });
}

function openRoleDialog(user: JupyterHubUser) {
  editingUser.value = user;
  editingRoles.value = [...user.roles];
  roleDialogVisible.value = true;
}

function toggleRole(role: string, checked: boolean) {
  if (checked && !editingRoles.value.includes(role)) {
    editingRoles.value.push(role);
  } else if (!checked) {
    editingRoles.value = editingRoles.value.filter(r => r !== role);
  }
}

async function saveRoles() {
  if (!editingUser.value) return;
  savingRoles.value = true;
  try {
    await adminStore.updateUser(editingUser.value.name, { roles: editingRoles.value });
    roleDialogVisible.value = false;
  } finally {
    savingRoles.value = false;
  }
}
</script>

<style lang="scss" scoped>
.admin-users {
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

.users-table {
  margin-top: 1rem;
}

.roles-cell {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.role-tag {
  font-size: 0.8rem;
}

.role-dialog-content {
  p {
    margin: 0 0 1rem;
  }
}

.role-checkboxes {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.role-checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
</style>
