<template>
  <div class="admin-context-edit">

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
            <small v-if="selectedImageDisabled" class="image-disabled-warning">
              <i class="pi pi-exclamation-triangle" />
              Selected image is disabled — this context will not appear to users regardless of its enabled state.
            </small>
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

        <div class="form-row">
          <div class="form-field full-width">
            <label>Workflows</label>
            <MultiSelect
              v-model="form.workflow_ids"
              :options="adminStore.allWorkflows"
              optionLabel="title"
              optionValue="id"
              placeholder="Select workflows..."
              display="chip"
              filter
            />
          </div>
        </div>

        <div class="form-row">
          <div class="form-field full-width">
            <label>Integrations</label>
            <MultiSelect
              v-model="form.integration_ids"
              :options="adminStore.allIntegrations"
              optionLabel="name"
              optionValue="id"
              placeholder="Select integrations..."
              display="chip"
              filter
            />
          </div>
        </div>

        <div class="form-row">
          <div class="form-field full-width">
            <label>Languages</label>
            <MultiSelect
              v-model="form.language_slugs"
              :options="adminStore.allLanguages"
              optionLabel="display_name"
              optionValue="slug"
              placeholder="Select languages..."
              display="chip"
              filter
            />
          </div>
        </div>

      </fieldset>

      <!-- Role-Based Visibility -->
      <fieldset class="form-section">
        <legend>Role-Based Visibility</legend>
        <div class="form-row">
          <div class="form-field full-width">
            <label for="visible_to_roles">Restrict to Roles</label>
            <Chips
              id="visible_to_roles"
              v-model="form.visible_to_roles"
              placeholder="Type a role name and press Enter..."
              separator=","
            />
            <small v-if="form.visible_to_roles.length === 0">
              No restrictions — this context is visible to all authenticated users.
            </small>
            <small v-else>
              Only users with at least one of these roles will see this context.
            </small>
          </div>
        </div>
      </fieldset>

      <!-- API Keys -->
      <fieldset class="form-section">
        <legend>API Keys</legend>
        <DataTable :value="apiKeyRows" class="api-keys-table">
          <Column field="display_name" header="Name" />
          <Column field="env_var" header="Env Variable" />
          <Column header="Value" style="width: 10rem;">
            <template #body>
              <Tag value="Not configured" severity="warn" />
            </template>
          </Column>
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
        <Button label="Cancel" severity="secondary" @click="router.push({ name: 'admin-contexts' })" />
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
import MultiSelect from 'primevue/multiselect';
import Checkbox from 'primevue/checkbox';
import Chips from 'primevue/chips';
import Message from 'primevue/message';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Tag from 'primevue/tag';
import Dialog from 'primevue/dialog';
import ProgressSpinner from 'primevue/progressspinner';
import { useAdminStore } from '@/stores/admin';
import type { AdminApiKey } from '@/stores/admin';

const props = defineProps<{
  slug: string;
}>();

const router = useRouter();
const adminStore = useAdminStore();

const isNew = computed(() => props.slug === 'new');
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
  // Role visibility
  visible_to_roles: [] as string[],
  // Relationship IDs
  workflow_ids: [] as number[],
  integration_ids: [] as number[],
  language_slugs: [] as string[],
  api_key_ids: [] as number[],
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

const selectedImageDisabled = computed(() => {
  if (form.value.image_id == null) return false;
  const image = adminStore.nodeImages.find(n => n.id === form.value.image_id);
  return image ? !image.enabled : false;
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
  // Load supporting entities for dropdowns
  await adminStore.fetchAllSupportingEntities();

  if (!isNew.value) {
    const context = await adminStore.fetchContext(props.slug);
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

      // Find matching node image ID (context.image is the image slug)
      const matchingImage = adminStore.nodeImages.find(n => n.slug === context.image);
      form.value.image_id = matchingImage?.id ?? null;

      // Role visibility
      form.value.visible_to_roles = context.visible_to_roles || [];

      // Populate relationship IDs from the loaded context
      form.value.workflow_ids = context.workflows.map(w => w.id);
      form.value.integration_ids = context.integrations.map(i => i.id);
      form.value.language_slugs = context.languages.map(l => l.slug);
      const matchedApiKeyIds = adminStore.allApiKeys
        .filter(ak => context.api_keys.some(cak => cak.env_var === ak.env_var))
        .map(ak => ak.id);
      form.value.api_key_ids = matchedApiKeyIds;
      contextProvidedApiKeyIds.value = new Set(matchedApiKeyIds);

      defaultPayloadText.value = JSON.stringify(context.default_payload || {}, null, 2);
    } else {
      errorMessage.value = `Context "${props.slug}" not found.`;
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
    visible_to_roles: form.value.visible_to_roles,
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
      await adminStore.updateContext(props.slug, payload);
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
.admin-context-edit {
  h1 {
    margin: 0 0 0.5rem;
    font-size: 1.5rem;
  }
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
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

.image-disabled-warning {
  color: var(--p-orange-500, #f59e0b);
  font-weight: 500;

  .pi {
    margin-right: 0.25rem;
    font-size: 0.8rem;
  }
}

:deep(.p-multiselect-chip-item) {
  flex-wrap: wrap;
}

:deep(.p-multiselect-label) {
  flex-wrap: wrap;
  overflow-y: auto;
  max-height: 8rem;
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

.form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-bottom: 1rem;
}
</style>
