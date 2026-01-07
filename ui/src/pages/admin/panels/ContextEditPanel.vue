<template>
  <div v-if="collapsed" class="panel-peek">
    <!-- Collapsed state is handled by PanelStack overlay -->
  </div>
  <div v-else class="context-edit-panel">
    <div v-if="loading" class="loading">
      <ProgressSpinner style="width: 50px; height: 50px;" />
    </div>

    <form v-else @submit.prevent="save" class="context-form">
      <!-- Read-only source fields (edit mode only) -->
      <fieldset v-if="!isNew" class="form-section">
        <legend>Source Information</legend>
        <div class="form-row">
          <div class="form-field">
            <label>Source Key</label>
            <InputText :modelValue="form.source_key ?? '—'" disabled />
          </div>
          <div class="form-field">
            <label>Source Package</label>
            <InputText :modelValue="form.source_package ?? '—'" disabled />
          </div>
          <div class="form-field">
            <label>Version</label>
            <InputText :modelValue="form.version ?? '—'" disabled />
          </div>
        </div>
      </fieldset>

      <!-- Core fields -->
      <fieldset class="form-section">
        <legend>Basic Information</legend>
        <div class="form-row">
          <div class="form-field">
            <label for="slug">Slug <span class="required">*</span></label>
            <InputText id="slug" v-model="form.slug" :disabled="!isNew" required />
            <small v-if="isNew">URL-safe identifier. Cannot be changed after creation.</small>
          </div>
          <div class="form-field">
            <label for="display_name">Display Name <span class="required">*</span></label>
            <InputText id="display_name" v-model="form.display_name" required />
          </div>
        </div>
        <div class="form-row">
          <div class="form-field full-width">
            <label for="description">Description</label>
            <Textarea id="description" v-model="form.description" rows="3" autoResize />
          </div>
        </div>
      </fieldset>

      <!-- Display & configuration -->
      <fieldset class="form-section">
        <legend>Display &amp; Configuration</legend>
        <div class="form-row">
          <div class="form-field">
            <label for="theme">Theme</label>
            <Select id="theme" v-model="form.theme" :options="themeOptions" optionLabel="label" optionValue="value" />
          </div>
          <div class="form-field">
            <label for="icon">Icon</label>
            <InputText id="icon" v-model="form.icon" placeholder="vue://ComponentName or https://..." />
          </div>
        </div>
        <div class="form-row">
          <div class="form-field">
            <label for="weight">Weight</label>
            <InputNumber id="weight" v-model="form.weight" :min="0" :max="999" />
          </div>
          <div class="form-field">
            <label for="image">Node Image</label>
            <Select
              id="image"
              v-model="form.image_id"
              :options="adminStore.nodeImages"
              optionLabel="slug"
              optionValue="id"
              placeholder="Select image..."
              showClear
            />
          </div>
        </div>
        <div class="form-row">
          <div class="form-field inline-check">
            <Checkbox id="enabled" v-model="form.enabled" :binary="true" />
            <label for="enabled">Enabled</label>
          </div>
        </div>
      </fieldset>

      <!-- Default Payload (JSON) -->
      <fieldset class="form-section">
        <legend>Default Payload</legend>
        <div class="form-row">
          <div class="form-field full-width">
            <Textarea
              v-model="defaultPayloadText"
              rows="6"
              class="json-editor"
              :class="{ 'json-error': defaultPayloadError }"
              spellcheck="false"
            />
            <small v-if="defaultPayloadError" class="error-text">{{ defaultPayloadError }}</small>
          </div>
        </div>
      </fieldset>

      <!-- Relationships -->
      <fieldset class="form-section">
        <legend>Relationships</legend>

        <!-- Workflows -->
        <div class="form-row">
          <div class="form-field full-width">
            <label>Workflows</label>
            <Listbox
              v-model="form.workflow_ids"
              :options="filteredWorkflows"
              optionLabel="title"
              optionValue="id"
              multiple
              filter
              filterPlaceholder="Search workflows..."
              scrollHeight="20rem"
              :highlightOnSelect="false"
            >
              <template #header>
                <div class="entity-list-toggle">
                  <Checkbox v-model="hideUnassignedWorkflows" :binary="true" inputId="hide-unassigned-wf" />
                  <label for="hide-unassigned-wf">Hide unassigned</label>
                </div>
              </template>
              <template #option="{ option, selected }">
                <div class="entity-item">
                  <Checkbox :modelValue="selected" :binary="true" :tabindex="-1" />
                  <span class="entity-title">{{ option.title }}</span>
                  <span class="entity-meta">{{ option.stage_count ?? 0 }} stages</span>
                  <i class="pi pi-chevron-right entity-nav" @click.stop="$emit('open-workflow', option.id)" />
                </div>
              </template>
            </Listbox>
          </div>
        </div>

        <!-- Integrations -->
        <div class="form-row">
          <div class="form-field full-width">
            <label>Integrations</label>
            <Listbox
              v-model="form.integration_ids"
              :options="filteredIntegrations"
              optionLabel="name"
              optionValue="id"
              multiple
              filter
              filterPlaceholder="Search integrations..."
              scrollHeight="20rem"
              :highlightOnSelect="false"
            >
              <template #header>
                <div class="entity-list-toggle">
                  <Checkbox v-model="hideUnassignedIntegrations" :binary="true" inputId="hide-unassigned-int" />
                  <label for="hide-unassigned-int">Hide unassigned</label>
                </div>
              </template>
              <template #option="{ option, selected }">
                <div class="entity-item">
                  <Checkbox :modelValue="selected" :binary="true" :tabindex="-1" />
                  <span class="entity-title">{{ option.name }}</span>
                  <i class="pi pi-chevron-right entity-nav" @click.stop="$emit('open-integration', option.id)" />
                </div>
              </template>
            </Listbox>
          </div>
        </div>

        <!-- Languages -->
        <div class="form-row">
          <div class="form-field full-width">
            <label>Languages</label>
            <Listbox
              v-model="form.language_slugs"
              :options="initialLanguages"
              optionLabel="display_name"
              optionValue="slug"
              multiple
              filter
              filterPlaceholder="Search languages..."
              scrollHeight="20rem"
              :highlightOnSelect="false"
            >
              <template #option="{ option, selected }">
                <div class="entity-item">
                  <Checkbox :modelValue="selected" :binary="true" :tabindex="-1" />
                  <span class="entity-title">{{ option.display_name }}</span>
                </div>
              </template>
            </Listbox>
          </div>
        </div>

      </fieldset>

      <!-- Vault Secrets -->
      <fieldset class="form-section">
        <legend>Vault Secrets</legend>
        <p v-if="!form.image_id" class="no-image-message">
          Select a node image above to see available secrets.
        </p>
        <template v-else>
          <div v-if="contextSecretsLoading" class="loading-inline">
            <ProgressSpinner style="width: 30px; height: 30px;" />
          </div>
          <template v-else>
            <DataTable :value="contextSecrets" class="secrets-toggle-table">
              <Column header="" style="width: 3.5rem;">
                <template #body="{ data }">
                  <Checkbox :modelValue="data.enabled" :binary="true" @update:modelValue="toggleContextSecret(data)" />
                </template>
              </Column>
              <Column field="env_var" header="Environment Variable">
                <template #body="{ data }">
                  <code>{{ data.env_var }}</code>
                </template>
              </Column>
              <Column field="description" header="Description">
                <template #body="{ data }">
                  <span class="description-text">{{ data.description || '—' }}</span>
                </template>
              </Column>
              <Column header="Scope" style="width: 7rem;">
                <template #body="{ data }">
                  <Tag v-if="data.node_image_id === null" value="Global" severity="info" />
                  <Tag v-else value="Node" severity="secondary" />
                </template>
              </Column>
              <template #empty>
                <div class="empty-message">No secrets in the vault for this node image.</div>
              </template>
            </DataTable>
            <div class="vault-actions">
              <Button
                label="Edit Vault"
                icon="pi pi-lock"
                size="small"
                severity="secondary"
                @click="openVaultEditorDialog"
              />
            </div>
          </template>
        </template>
      </fieldset>

      <!-- API Keys -->
      <fieldset class="form-section">
        <legend>API Keys</legend>
        <DataTable :value="apiKeyRows" class="api-keys-table">
          <Column field="display_name" header="Name" />
          <Column field="env_var" header="Env Variable" />
          <Column header="Source" style="width: 8rem;">
            <template #body="{ data }">
              <Tag v-if="data.from_context" value="Context" severity="info" />
              <Tag v-else value="Manual" severity="secondary" />
            </template>
          </Column>
          <Column header="" style="width: 4rem;">
            <template #body="{ data }">
              <Button
                icon="pi pi-times"
                text
                size="small"
                severity="danger"
                @click="removeApiKey(data.id)"
                title="Remove"
              />
            </template>
          </Column>
        </DataTable>

        <div class="api-key-add">
          <Select
            v-model="selectedExistingApiKey"
            :options="availableApiKeys"
            optionLabel="display_name"
            optionValue="id"
            placeholder="Add existing key..."
            showClear
            class="api-key-select"
          />
          <Button label="Add" icon="pi pi-plus" size="small" :disabled="!selectedExistingApiKey" @click="addExistingApiKey" />
          <span class="separator">or</span>
          <Button label="Create New" icon="pi pi-plus-circle" size="small" severity="secondary" @click="showNewApiKeyDialog = true" />
        </div>
      </fieldset>

      <!-- Actions -->
      <div class="form-actions">
        <Button label="Cancel" severity="secondary" @click="$emit('close')" />
        <Button type="submit" :label="isNew ? 'Create' : 'Save'" :loading="saving" />
      </div>

      <Message v-if="errorMessage" severity="error" :closable="true" @close="errorMessage = ''">
        {{ errorMessage }}
      </Message>
    </form>

    <!-- New API Key Dialog -->
    <Dialog v-model:visible="showNewApiKeyDialog" header="Create New API Key" :modal="true" :style="{ width: '450px' }">
      <div class="new-api-key-form">
        <div class="form-field">
          <label for="new-ak-display-name">Display Name <span class="required">*</span></label>
          <InputText id="new-ak-display-name" v-model="newApiKey.display_name" />
        </div>
        <div class="form-field">
          <label for="new-ak-env-var">Environment Variable <span class="required">*</span></label>
          <InputText id="new-ak-env-var" v-model="newApiKey.env_var" placeholder="e.g. API_MY_SERVICE" />
        </div>
        <div class="form-field">
          <label for="new-ak-description">Description</label>
          <Textarea id="new-ak-description" v-model="newApiKey.description" rows="2" autoResize />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="showNewApiKeyDialog = false" />
        <Button label="Create & Add" @click="createAndAddApiKey" :disabled="!newApiKey.display_name || !newApiKey.env_var" />
      </template>
    </Dialog>

    <!-- Vault Editor Dialog -->
    <Dialog
      v-model:visible="vaultEditorDialogVisible"
      :header="`Vault: ${vaultEditorNodeSlug}`"
      :modal="true"
      :style="{ width: '800px' }"
    >
      <SecretVaultEditor
        v-if="form.image_id"
        :nodeImageId="form.image_id"
        @updated="loadContextSecrets"
      />
    </Dialog>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import Button from 'primevue/button';
import InputText from 'primevue/inputtext';
import InputNumber from 'primevue/inputnumber';
import Textarea from 'primevue/textarea';
import Select from 'primevue/select';
import Listbox from 'primevue/listbox';
import Checkbox from 'primevue/checkbox';
import Message from 'primevue/message';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Tag from 'primevue/tag';
import Dialog from 'primevue/dialog';
import ProgressSpinner from 'primevue/progressspinner';
import { useConfirm } from 'primevue/useconfirm';
import { useAdminStore } from '@/stores/admin';
import type { AdminLanguage, ContextSecretOverride } from '@/stores/admin';
import SecretVaultEditor from '@/components/SecretVaultEditor.vue';

const props = defineProps<{
  sourceKey: string;
  collapsed?: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'open-workflow', workflowId: number): void;
  (e: 'open-integration', integrationId: number): void;
}>();

const router = useRouter();
const adminStore = useAdminStore();
const confirm = useConfirm();

const isNew = computed(() => props.sourceKey === 'new');
const loading = ref(true);
const saving = ref(false);
const errorMessage = ref('');

const form = ref({
  slug: '',
  display_name: '',
  description: '',
  icon: null as string | null,
  theme: 'data-science',
  weight: 50,
  default_payload: {} as Record<string, any>,
  enabled: false,
  image_id: null as number | null,
  source_key: null as string | null,
  source_package: null as string | null,
  version: null as string | null,
  workflow_ids: [] as number[],
  integration_ids: [] as number[],
  language_slugs: [] as string[],
  api_key_ids: [] as number[],
});

// Relationship list state
const hideUnassignedWorkflows = ref(false);
const hideUnassignedIntegrations = ref(false);
const initialLanguages = ref<AdminLanguage[]>([]);

const filteredWorkflows = computed(() => {
  if (hideUnassignedWorkflows.value) {
    const assigned = new Set(form.value.workflow_ids);
    return adminStore.allWorkflows.filter(w => assigned.has(w.id));
  }
  return adminStore.allWorkflows;
});

const filteredIntegrations = computed(() => {
  if (hideUnassignedIntegrations.value) {
    const assigned = new Set(form.value.integration_ids);
    return adminStore.allIntegrations.filter(i => assigned.has(i.id));
  }
  return adminStore.allIntegrations;
});

// API Key management
interface ApiKeyRow {
  id: number;
  display_name: string;
  env_var: string;
  from_context: boolean;
}

const contextProvidedApiKeyIds = ref<Set<number>>(new Set());
const selectedExistingApiKey = ref<number | null>(null);
const showNewApiKeyDialog = ref(false);
const newApiKey = ref({ display_name: '', env_var: '', description: '' });

const apiKeyRows = computed<ApiKeyRow[]>(() => {
  return form.value.api_key_ids
    .map(id => {
      const ak = adminStore.allApiKeys.find(k => k.id === id);
      if (!ak) return null;
      return {
        id: ak.id,
        display_name: ak.display_name,
        env_var: ak.env_var,
        from_context: contextProvidedApiKeyIds.value.has(ak.id),
      };
    })
    .filter((row): row is ApiKeyRow => row !== null);
});

const availableApiKeys = computed(() => {
  const assigned = new Set(form.value.api_key_ids);
  return adminStore.allApiKeys.filter(ak => !assigned.has(ak.id));
});

function addExistingApiKey() {
  if (selectedExistingApiKey.value && !form.value.api_key_ids.includes(selectedExistingApiKey.value)) {
    form.value.api_key_ids.push(selectedExistingApiKey.value);
  }
  selectedExistingApiKey.value = null;
}

function removeApiKey(id: number) {
  form.value.api_key_ids = form.value.api_key_ids.filter(akId => akId !== id);
}

async function createAndAddApiKey() {
  try {
    const created = await adminStore.createApiKey(newApiKey.value);
    if (created) {
      form.value.api_key_ids.push(created.id);
      showNewApiKeyDialog.value = false;
      newApiKey.value = { display_name: '', env_var: '', description: '' };
    }
  } catch (e: any) {
    errorMessage.value = e.message || 'Failed to create API key.';
  }
}

// Vault secrets management
const contextSecrets = ref<ContextSecretOverride[]>([]);
const contextSecretsLoading = ref(false);
const vaultEditorDialogVisible = ref(false);

const vaultEditorNodeSlug = computed(() => {
  const img = adminStore.nodeImages.find(n => n.id === form.value.image_id);
  return img?.slug || 'Node';
});

async function loadContextSecrets() {
  if (!props.sourceKey || isNew.value) return;
  contextSecretsLoading.value = true;
  try {
    contextSecrets.value = await adminStore.fetchContextSecrets(props.sourceKey);
  } finally {
    contextSecretsLoading.value = false;
  }
}

async function toggleContextSecret(secret: ContextSecretOverride) {
  // Toggle locally
  secret.enabled = !secret.enabled;
  // Persist: send only the disabled ones as overrides
  const overrides = contextSecrets.value
    .filter(s => !s.enabled)
    .map(s => ({ node_secret_id: s.id, enabled: false }));
  try {
    await adminStore.updateContextSecrets(props.sourceKey, overrides);
  } catch (e: any) {
    // Revert on failure
    secret.enabled = !secret.enabled;
    errorMessage.value = e.message || 'Failed to update secret toggle.';
  }
}

function openVaultEditorDialog() {
  vaultEditorDialogVisible.value = true;
}

// Watch for image_id changes to reload applicable secrets
watch(() => form.value.image_id, () => {
  if (!isNew.value) {
    loadContextSecrets();
  }
});

const themeOptions = [
  { label: 'Data Science', value: 'data-science' },
  { label: 'Biomedical', value: 'biomedical' },
  { label: 'Weather', value: 'weather' },
  { label: 'Geospatial', value: 'geospatial' },
  { label: 'Wildfire', value: 'wildfire' },
];

// JSON editor for default_payload
const defaultPayloadText = ref('{}');
const defaultPayloadError = ref('');

watch(defaultPayloadText, (val) => {
  try {
    form.value.default_payload = JSON.parse(val);
    defaultPayloadError.value = '';
  } catch (e: any) {
    defaultPayloadError.value = e.message;
  }
});

onMounted(async () => {
  await adminStore.fetchAllSupportingEntities();

  if (!isNew.value) {
    const context = await adminStore.fetchContext(props.sourceKey);
    if (context) {
      form.value.slug = context.slug;
      form.value.display_name = context.display_name;
      form.value.description = context.description || '';
      form.value.icon = context.icon;
      form.value.theme = context.theme || 'data-science';
      form.value.weight = context.weight;
      form.value.default_payload = context.default_payload || {};
      form.value.enabled = context.enabled;
      form.value.source_key = context.source_key;
      form.value.source_package = context.source_package;
      form.value.version = context.version;

      const matchingImage = adminStore.nodeImages.find(n => n.slug === context.image);
      form.value.image_id = matchingImage?.id ?? null;

      form.value.workflow_ids = context.workflows.map(w => w.id);
      form.value.integration_ids = context.integrations.map(i => i.id);
      initialLanguages.value = context.languages;
      form.value.language_slugs = context.languages.map(l => l.slug);
      const matchedApiKeyIds = adminStore.allApiKeys
        .filter(ak => context.api_keys.some(cak => cak.env_var === ak.env_var))
        .map(ak => ak.id);
      form.value.api_key_ids = matchedApiKeyIds;
      contextProvidedApiKeyIds.value = new Set(matchedApiKeyIds);

      defaultPayloadText.value = JSON.stringify(context.default_payload || {}, null, 2);

      // Load vault secret overrides for this context
      await loadContextSecrets();
    } else {
      errorMessage.value = `Context "${props.sourceKey}" not found.`;
    }
  }

  loading.value = false;
});

async function save() {
  if (defaultPayloadError.value) {
    errorMessage.value = 'Please fix the JSON in Default Payload before saving.';
    return;
  }

  saving.value = true;
  errorMessage.value = '';

  const payload: Record<string, any> = {
    display_name: form.value.display_name,
    description: form.value.description,
    icon: form.value.icon,
    theme: form.value.theme,
    weight: form.value.weight,
    default_payload: form.value.default_payload,
    enabled: form.value.enabled,
    image_id: form.value.image_id,
    workflow_ids: form.value.workflow_ids,
    integration_ids: form.value.integration_ids,
    language_slugs: form.value.language_slugs,
    api_key_ids: form.value.api_key_ids,
  };

  if (isNew.value) {
    payload.slug = form.value.slug;
  }

  try {
    if (isNew.value) {
      await adminStore.createContext(payload);
    } else {
      await adminStore.updateContext(props.sourceKey, payload);
    }
    router.push({ name: 'admin-contexts' });
  } catch (e: any) {
    errorMessage.value = e.message || 'Failed to save context.';
  } finally {
    saving.value = false;
  }
}
</script>

<style lang="scss" scoped>
.context-edit-panel {
  padding: 1.25rem;

  h2 {
    margin: 0 0 0.5rem;
    font-size: 1.25rem;
  }
}

.loading {
  display: flex;
  justify-content: center;
  padding: 3rem;
}

.context-form {
  max-width: 900px;
}

.form-section {
  border: 1px solid var(--p-surface-border, #dee2e6);
  border-radius: 6px;
  padding: 1.25rem;
  margin-bottom: 1.5rem;

  legend {
    font-weight: 600;
    font-size: 0.95rem;
    padding: 0 0.5rem;
    color: var(--p-text-color);
  }
}

.form-row {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;

  &:last-child {
    margin-bottom: 0;
  }
}

.form-field {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;

  &.full-width {
    flex-basis: 100%;
  }

  &.inline-check {
    flex-direction: row;
    align-items: center;
    gap: 0.5rem;
  }

  label {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--p-text-color);
  }

  small {
    font-size: 0.8rem;
    color: var(--p-text-secondary-color);
  }
}

.required {
  color: var(--p-red-500, #ef4444);
}

.json-editor {
  font-family: monospace;
  font-size: 0.85rem;

  &.json-error {
    border-color: var(--p-red-500, #ef4444);
  }
}

.error-text {
  color: var(--p-red-500, #ef4444);
}

.entity-list-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;

  label {
    font-size: 0.8rem;
    color: var(--p-text-secondary-color);
    cursor: pointer;
  }
}

.entity-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;

  .entity-title {
    flex: 1;
    font-size: 0.9rem;
    font-weight: 500;
  }

  .entity-meta {
    font-size: 0.8rem;
    color: var(--p-text-secondary-color);
    margin-right: 0.25rem;
  }

  .entity-nav {
    color: var(--p-text-secondary-color);
    font-size: 0.75rem;
    cursor: pointer;
    padding: 0.25rem;
    min-width: 2rem;
    text-align: end;

    &:hover {
      color: var(--p-primary-color);
    }
  }
}

.api-keys-table {
  margin-bottom: 0.75rem;
}

.api-key-add {
  display: flex;
  align-items: center;
  gap: 0.5rem;

  .api-key-select {
    min-width: 250px;
  }

  .separator {
    color: var(--p-text-secondary-color);
    font-size: 0.85rem;
  }
}

.new-api-key-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.no-image-message {
  margin: 0;
  font-size: 0.85rem;
  color: var(--p-text-secondary-color);
  font-style: italic;
}

.loading-inline {
  display: flex;
  justify-content: center;
  padding: 1rem;
}

.secrets-toggle-table {
  margin-bottom: 0.75rem;
}

.description-text {
  font-size: 0.85rem;
  color: var(--p-text-secondary-color);
}

.empty-message {
  text-align: center;
  padding: 1rem;
  color: var(--p-text-secondary-color);
  font-size: 0.85rem;
}

.vault-actions {
  display: flex;
  gap: 0.5rem;
}

.form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-bottom: 1rem;
}
</style>
