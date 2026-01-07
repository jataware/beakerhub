<template>
  <div class="secret-vault-editor">
    <div v-if="loading" class="loading">
      <ProgressSpinner style="width: 40px; height: 40px;" />
    </div>
    <template v-else>
      <DataTable :value="secrets" class="secrets-table" :scrollable="true" scrollHeight="400px">
        <Column field="env_var" header="Environment Variable" sortable style="min-width: 14rem;">
          <template #body="{ data }">
            <code>{{ data.env_var }}</code>
          </template>
        </Column>
        <Column header="Value" style="min-width: 14rem;">
          <template #body="{ data }">
            <div class="value-cell">
              <template v-if="editingId === data.id">
                <InputText v-model="editValue" class="value-input" :type="showValue ? 'text' : 'password'" />
                <Button icon="pi pi-eye" text size="small" @click="showValue = !showValue" :title="showValue ? 'Hide' : 'Show'" />
              </template>
              <template v-else>
                <span class="masked-value">{{ data._loaded ? '********' : '(encrypted)' }}</span>
              </template>
            </div>
          </template>
        </Column>
        <Column field="description" header="Description" style="min-width: 10rem;">
          <template #body="{ data }">
            <template v-if="editingId === data.id">
              <InputText v-model="editDescription" class="desc-input" placeholder="Optional description" />
            </template>
            <template v-else>
              <span class="description-text">{{ data.description || '—' }}</span>
            </template>
          </template>
        </Column>
        <Column header="Policies" style="min-width: 9rem;">
          <template #body="{ data }">
            <Button
              icon="pi pi-lock"
              text
              size="small"
              :severity="overrideCount(data.policies) ? undefined : 'secondary'"
              :label="policySummary(data.policies)"
              class="policy-button"
              :title="policyTitle(data.policies)"
              @click="openPolicies(data)"
            />
          </template>
        </Column>
        <Column header="" style="width: 10rem;">
          <template #body="{ data }">
            <div class="action-buttons">
              <template v-if="editingId === data.id">
                <Button icon="pi pi-check" text size="small" @click="saveEdit(data)" :loading="savingId === data.id" title="Save" />
                <Button icon="pi pi-times" text size="small" severity="secondary" @click="cancelEdit" title="Cancel" />
              </template>
              <template v-else>
                <Button icon="pi pi-pencil" text size="small" @click="startEdit(data)" title="Edit" />
                <Button icon="pi pi-trash" text size="small" severity="danger" @click="confirmDelete(data)" title="Delete" />
              </template>
            </div>
          </template>
        </Column>
        <template #empty>
          <div class="empty-message">No secrets configured.</div>
        </template>
      </DataTable>

      <!-- Add new secret -->
      <div class="add-secret-row">
        <InputText v-model="newEnvVar" placeholder="ENV_VAR_NAME" class="new-env-input" />
        <InputText v-model="newValue" placeholder="Value" type="password" class="new-value-input" />
        <InputText v-model="newDescription" placeholder="Description (optional)" class="new-desc-input" />
        <Button
          icon="pi pi-lock"
          size="small"
          outlined
          :severity="overrideCount(newPolicies) ? undefined : 'secondary'"
          :label="policySummary(newPolicies)"
          :title="policyTitle(newPolicies)"
          @click="openNewPolicies"
        />
        <Button
          icon="pi pi-plus"
          label="Add"
          size="small"
          :disabled="!newEnvVar || !newValue"
          :loading="adding"
          @click="addSecret"
        />
      </div>

      <Message v-if="errorMessage" severity="error" :closable="true" @close="errorMessage = ''" class="vault-error">
        {{ errorMessage }}
      </Message>
    </template>

    <SecretPolicyDialog
      v-model:visible="policyDialogVisible"
      :envVar="policyTarget?.env_var"
      :policies="policyDialogPolicies"
      :saving="policySaving"
      @save="savePolicies"
    />
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, watch } from 'vue';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Button from 'primevue/button';
import InputText from 'primevue/inputtext';
import Message from 'primevue/message';
import ProgressSpinner from 'primevue/progressspinner';
import { useConfirm } from 'primevue/useconfirm';
import { useAdminStore } from '@/stores/admin';
import type { VaultSecret } from '@/stores/admin';
import SecretPolicyDialog from '@/components/SecretPolicyDialog.vue';
import { overrideCount, type SecretPolicies } from '@/utils/secretPolicies';

const props = defineProps<{
  nodeImageId: number | null;  // null = global
}>();

const emit = defineEmits<{
  (e: 'updated'): void;
}>();

const adminStore = useAdminStore();
const confirm = useConfirm();

const loading = ref(true);
const secrets = ref<(VaultSecret & { _loaded?: boolean })[]>([]);
const errorMessage = ref('');

// Edit state
const editingId = ref<number | null>(null);
const editValue = ref('');
const editDescription = ref('');
const showValue = ref(false);
const savingId = ref<number | null>(null);

// Add state
const newEnvVar = ref('');
const newValue = ref('');
const newDescription = ref('');
const newPolicies = ref<SecretPolicies>({});
const adding = ref(false);

// Policy dialog state. A null target means the dialog is editing the pending new secret.
const policyDialogVisible = ref(false);
const policyTarget = ref<VaultSecret | null>(null);
const policyDialogPolicies = ref<SecretPolicies>({});
const policySaving = ref(false);

/** Short label for the lock button: how many axes deviate from the defaults. */
function policySummary(policies: SecretPolicies | null | undefined): string {
  const count = overrideCount(policies);
  return count ? `${count} override${count === 1 ? '' : 's'}` : 'Defaults';
}

function policyTitle(policies: SecretPolicies | null | undefined): string {
  return overrideCount(policies)
    ? 'Edit secret policies (customized)'
    : 'Edit secret policies (all defaults)';
}

function openPolicies(secret: VaultSecret) {
  policyTarget.value = secret;
  policyDialogPolicies.value = { ...(secret.policies || {}) };
  policyDialogVisible.value = true;
}

function openNewPolicies() {
  policyTarget.value = null;
  policyDialogPolicies.value = { ...newPolicies.value };
  policyDialogVisible.value = true;
}

async function savePolicies(policies: SecretPolicies) {
  // Policies for a not-yet-created secret are staged until Add is clicked.
  if (policyTarget.value === null) {
    newPolicies.value = policies;
    policyDialogVisible.value = false;
    return;
  }
  policySaving.value = true;
  errorMessage.value = '';
  try {
    await adminStore.updateSecret(policyTarget.value.id, { policies });
    policyDialogVisible.value = false;
    await loadSecrets();
    emit('updated');
  } catch (e: any) {
    errorMessage.value = e.message || 'Failed to save secret policies.';
  } finally {
    policySaving.value = false;
  }
}

async function loadSecrets() {
  loading.value = true;
  try {
    const scope = props.nodeImageId === null ? 'global' as const : props.nodeImageId;
    secrets.value = (await adminStore.fetchSecrets(scope)).map(s => ({ ...s, _loaded: true }));
  } finally {
    loading.value = false;
  }
}

watch(() => props.nodeImageId, () => {
  loadSecrets();
});

onMounted(() => {
  loadSecrets();
});

async function startEdit(secret: VaultSecret & { _loaded?: boolean }) {
  // Fetch the actual value
  const full = await adminStore.fetchSecret(secret.id);
  if (full) {
    editingId.value = secret.id;
    editValue.value = full.value;
    editDescription.value = full.description || '';
    showValue.value = false;
  }
}

function cancelEdit() {
  editingId.value = null;
  editValue.value = '';
  editDescription.value = '';
  showValue.value = false;
}

async function saveEdit(secret: VaultSecret) {
  savingId.value = secret.id;
  errorMessage.value = '';
  try {
    await adminStore.updateSecret(secret.id, {
      value: editValue.value,
      description: editDescription.value || null,
    });
    cancelEdit();
    await loadSecrets();
    emit('updated');
  } catch (e: any) {
    errorMessage.value = e.message || 'Failed to save secret.';
  } finally {
    savingId.value = null;
  }
}

async function addSecret() {
  adding.value = true;
  errorMessage.value = '';
  try {
    await adminStore.upsertSecret({
      node_image_id: props.nodeImageId,
      env_var: newEnvVar.value,
      value: newValue.value,
      description: newDescription.value || undefined,
      policies: newPolicies.value,
    });
    newEnvVar.value = '';
    newValue.value = '';
    newDescription.value = '';
    newPolicies.value = {};
    await loadSecrets();
    emit('updated');
  } catch (e: any) {
    errorMessage.value = e.message || 'Failed to add secret.';
  } finally {
    adding.value = false;
  }
}

function confirmDelete(secret: VaultSecret) {
  confirm.require({
    message: `Delete secret "${secret.env_var}"? This cannot be undone.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      await adminStore.deleteSecret(secret.id);
      await loadSecrets();
      emit('updated');
    },
  });
}

defineExpose({ loadSecrets });
</script>

<style lang="scss" scoped>
.secret-vault-editor {
  min-width: 0;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 2rem;
}

.value-cell {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.value-input,
.desc-input {
  width: 100%;
  font-size: 0.85rem;
}

.masked-value {
  color: var(--p-text-secondary-color);
  font-size: 0.85rem;
  font-family: monospace;
}

.description-text {
  font-size: 0.85rem;
  color: var(--p-text-secondary-color);
}

.action-buttons {
  display: flex;
  gap: 0.1rem;
}

.policy-button {
  font-size: 0.8rem;
  white-space: nowrap;
}

.empty-message {
  text-align: center;
  padding: 1.5rem;
  color: var(--p-text-secondary-color);
  font-size: 0.9rem;
}

.add-secret-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.75rem;

  .new-env-input {
    flex: 0 0 14rem;
    font-family: monospace;
    font-size: 0.85rem;
  }

  .new-value-input {
    flex: 1;
    font-size: 0.85rem;
  }

  .new-desc-input {
    flex: 1;
    font-size: 0.85rem;
  }
}

.vault-error {
  margin-top: 0.75rem;
}
</style>
