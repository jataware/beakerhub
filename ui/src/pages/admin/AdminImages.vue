<template>
  <div class="admin-images">
    <div class="page-header">
      <div>
        <h1>Image Management</h1>
        <p>Manage Docker node images and their configurations.</p>
      </div>
      <div class="header-actions">
        <Button label="Refresh" icon="pi pi-refresh" text @click="adminStore.fetchNodeImages()" />
        <Button label="Add Image" icon="pi pi-plus" @click="openCreateDialog" />
      </div>
    </div>

    <DataTable
      :value="adminStore.nodeImages"
      :loading="adminStore.nodeImagesLoading"
      stripedRows
      sortField="slug"
      :sortOrder="1"
      class="images-table"
    >
      <Column field="slug" header="Slug" sortable>
        <template #body="{ data }">
          <a class="image-link" @click.prevent="openEditDialog(data)">{{ data.slug }}</a>
        </template>
      </Column>
      <Column field="default_registry" header="Registry" sortable />
      <Column field="repository" header="Repository" sortable />
      <Column field="default_tag" header="Tag" sortable />
      <Column field="created_at" header="Created" sortable>
        <template #body="{ data }">
          <span v-if="data.created_at" :title="data.created_at">{{ formatDate(data.created_at) }}</span>
          <span v-else class="no-contexts">—</span>
        </template>
      </Column>
      <Column header="Last Import" sortable :sortField="'last_import'">
        <template #body="{ data }">
          <template v-if="data.last_import">
            <span
              class="import-status"
              :class="data.last_import.status"
              :title="importTooltip(data.last_import)"
            >
              <i :class="importStatusIcon(data.last_import.status)" />
              {{ formatDate(data.last_import.updated_at || data.last_import.created_at) }}
            </span>
          </template>
          <span v-else class="no-contexts">—</span>
        </template>
      </Column>
      <Column header="Contexts" sortable :sortField="'contexts'">
        <template #body="{ data }">
          <div v-if="data.contexts?.length" class="context-chips">
            <router-link
              v-for="ctx in data.contexts"
              :key="ctx.source_key"
              :to="{ name: 'admin-context-edit', params: { sourceKey: ctx.source_key } }"
              class="context-chip"
              :class="{ disabled: !ctx.enabled }"
              :title="ctx.enabled ? ctx.display_name : `${ctx.display_name} (disabled)`"
            >
              {{ ctx.display_name }}
            </router-link>
          </div>
          <span v-else class="no-contexts">—</span>
        </template>
      </Column>
      <Column field="enabled" header="Enabled" sortable style="width: 8rem;">
        <template #body="{ data }">
          <InputSwitch :modelValue="data.enabled" @update:modelValue="toggleEnabled(data)" />
        </template>
      </Column>
      <Column header="Actions" style="width: 14rem;">
        <template #body="{ data }">
          <Button
            icon="pi pi-lock"
            text
            size="small"
            @click="openVaultDialog(data)"
            title="Vault Secrets"
          />
          <Button
            icon="pi pi-download"
            text
            size="small"
            @click="pullLatest(data)"
            title="Pull Latest"
            :loading="adminStore.importingImages[data.id]"
            :disabled="adminStore.importingImages[data.id]"
          />
          <Button
            icon="pi pi-pencil"
            text
            size="small"
            @click="openEditDialog(data)"
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

    <!-- Create/Edit Dialog -->
    <Dialog
      v-model:visible="dialogVisible"
      :header="editingImage ? 'Edit Node Image' : 'Import Node Image'"
      :modal="true"
      :closable="!dialogSaving"
      :closeOnEscape="!dialogSaving"
      :style="{ width: '550px' }"
    >
      <div class="image-form">
        <!-- Create mode: single image reference input -->
        <template v-if="!editingImage">
          <div class="form-field">
            <label for="img-ref">Image <span class="required">*</span></label>
            <InputText id="img-ref" v-model="imageRef" :disabled="dialogSaving" placeholder="e.g. localhost:5000/beakerhub/my-node:v1.0" />
            <small>Full image reference. Tag defaults to <code>latest</code> if omitted.</small>
          </div>
          <div v-if="parsedImage.repository" class="parsed-preview">
            <div class="preview-row" v-if="parsedImage.registry">
              <span class="preview-label">Registry</span>
              <span class="preview-value">{{ parsedImage.registry }}</span>
            </div>
            <div class="preview-row">
              <span class="preview-label">Repository</span>
              <span class="preview-value">{{ parsedImage.repository }}</span>
            </div>
            <div class="preview-row">
              <span class="preview-label">Tag</span>
              <span class="preview-value">{{ parsedImage.tag }}</span>
            </div>
            <div class="preview-row">
              <span class="preview-label">Slug</span>
              <span class="preview-value">{{ generatedSlug }}</span>
            </div>
          </div>
          <div class="form-field inline-check">
            <Checkbox id="img-enabled" v-model="dialogForm.enabled" :binary="true" />
            <label for="img-enabled">Enabled</label>
          </div>
        </template>

        <!-- Edit mode: individual fields -->
        <template v-else>
          <div class="form-field">
            <label for="img-slug">Slug</label>
            <InputText id="img-slug" v-model="dialogForm.slug" disabled />
          </div>
          <div class="form-field">
            <label for="img-registry">Default Registry</label>
            <InputText id="img-registry" v-model="dialogForm.default_registry" placeholder="e.g. ghcr.io" />
          </div>
          <div class="form-field">
            <label for="img-repository">Repository</label>
            <InputText id="img-repository" v-model="dialogForm.repository" />
          </div>
          <div class="form-field">
            <label for="img-tag">Default Tag</label>
            <InputText id="img-tag" v-model="dialogForm.default_tag" />
          </div>
          <div class="form-field">
            <label for="img-metadata">Metadata (JSON)</label>
            <Textarea
              id="img-metadata"
              v-model="metadataText"
              rows="4"
              class="json-editor"
              :class="{ 'json-error': metadataError }"
              spellcheck="false"
            />
            <small v-if="metadataError" class="error-text">{{ metadataError }}</small>
          </div>
          <div class="form-field inline-check">
            <Checkbox id="img-enabled" v-model="dialogForm.enabled" :binary="true" />
            <label for="img-enabled">Enabled</label>
          </div>
        </template>
      </div>
      <template #footer>
        <Message v-if="dialogError" severity="error" :closable="true" @close="dialogError = ''" class="dialog-error">
          {{ dialogError }}
        </Message>
        <Button label="Cancel" severity="secondary" :disabled="dialogSaving" @click="dialogVisible = false" />
        <Button
          :label="editingImage ? 'Save' : 'Import'"
          :loading="dialogSaving"
          :disabled="dialogSaving || (editingImage ? !dialogForm.repository : !parsedImage.repository)"
          @click="saveImage"
        />
      </template>
    </Dialog>
    <!-- Vault Secrets Dialog -->
    <Dialog
      v-model:visible="vaultDialogVisible"
      :header="vaultDialogNode ? `Vault: ${vaultDialogNode.slug}` : 'Vault'"
      :modal="true"
      :style="{ width: '800px' }"
    >
      <SecretVaultEditor
        v-if="vaultDialogNode"
        :nodeImageId="vaultDialogNode.id"
      />
    </Dialog>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, watch, onMounted } from 'vue';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Button from 'primevue/button';
import InputSwitch from 'primevue/inputswitch';
import InputText from 'primevue/inputtext';
import Textarea from 'primevue/textarea';
import Checkbox from 'primevue/checkbox';
import Dialog from 'primevue/dialog';
import Message from 'primevue/message';
import { useConfirm } from 'primevue/useconfirm';
import { useToast } from 'primevue/usetoast';
import { useAdminStore } from '@/stores/admin';
import type { AdminNodeImage, AdminNodeImageImport } from '@/stores/admin';
import SecretVaultEditor from '@/components/SecretVaultEditor.vue';

const adminStore = useAdminStore();
const confirm = useConfirm();
const toast = useToast();

// Watch for import completion/failure events from the store
watch(adminStore.importEvents, (events) => {
  if (!events.length) return;
  const consumed = adminStore.consumeImportEvents();
  for (const event of consumed) {
    if (event.status === 'completed') {
      let detail = `Import completed for "${event.slug}".`;
      if (event.result) {
        const parts: string[] = [];
        if (event.result.contexts_created) parts.push(`${event.result.contexts_created} context(s) created`);
        if (event.result.contexts_updated) parts.push(`${event.result.contexts_updated} context(s) updated`);
        if (event.result.workflows_created) parts.push(`${event.result.workflows_created} workflow(s) created`);
        if (event.result.workflows_updated) parts.push(`${event.result.workflows_updated} workflow(s) updated`);
        if (parts.length) detail += ' ' + parts.join(', ') + '.';
      }
      toast.add({ severity: 'success', summary: 'Import Completed', detail, life: 8000 });
    } else {
      toast.add({
        severity: 'error',
        summary: 'Import Failed',
        detail: event.error || `Import failed for "${event.slug}".`,
        life: 10000,
      });
    }
  }
});

// Vault dialog state
const vaultDialogVisible = ref(false);
const vaultDialogNode = ref<AdminNodeImage | null>(null);

function openVaultDialog(image: AdminNodeImage) {
  vaultDialogNode.value = image;
  vaultDialogVisible.value = true;
}

// Dialog state
const dialogVisible = ref(false);
const dialogSaving = ref(false);
const dialogError = ref('');
const editingImage = ref<AdminNodeImage | null>(null);

const dialogForm = ref({
  slug: '',
  default_registry: '',
  repository: '',
  default_tag: '',
  enabled: false,
  metadata: {} as Record<string, any>,
});

const metadataText = ref('{}');
const metadataError = ref('');

watch(metadataText, (val) => {
  try {
    dialogForm.value.metadata = JSON.parse(val);
    metadataError.value = '';
  } catch (e: any) {
    metadataError.value = e.message;
  }
});

// Create mode: single image reference input + parsing
const imageRef = ref('');

/**
 * Parse a Docker image reference into registry, repository, and tag.
 * If the first segment contains a '.' or ':' it's treated as a registry.
 */
const parsedImage = computed(() => {
  const raw = imageRef.value.trim();
  if (!raw) return { registry: '', repository: '', tag: 'latest' };

  let ref = raw;
  let tag = 'latest';

  // Split off tag
  const colonIdx = ref.lastIndexOf(':');
  const slashIdx = ref.lastIndexOf('/');
  if (colonIdx > slashIdx) {
    tag = ref.slice(colonIdx + 1);
    ref = ref.slice(0, colonIdx);
  }

  // Determine if first segment is a registry
  const parts = ref.split('/');
  let registry = '';
  let repository = ref;

  if (parts.length > 1 && (parts[0].includes('.') || parts[0].includes(':'))) {
    registry = parts[0];
    repository = parts.slice(1).join('/');
  }

  return { registry, repository, tag };
});

const generatedSlug = computed(() => {
  const repo = parsedImage.value.repository;
  if (!repo) return '';
  const lastSegment = repo.split('/').pop() || repo;
  const base = lastSegment.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const tag = parsedImage.value.tag;
  if (!tag || tag === 'latest') return base;
  const tagSuffix = tag.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  return tagSuffix ? `${base}-${tagSuffix}` : base;
});

onMounted(() => {
  adminStore.fetchNodeImages();
});

function openCreateDialog() {
  editingImage.value = null;
  imageRef.value = '';
  dialogForm.value = {
    slug: '',
    default_registry: '',
    repository: '',
    default_tag: '',
    enabled: true,
    metadata: {},
  };
  metadataText.value = '{}';
  metadataError.value = '';
  dialogError.value = '';
  dialogVisible.value = true;
}

function openEditDialog(image: AdminNodeImage) {
  editingImage.value = image;
  dialogForm.value = {
    slug: image.slug,
    default_registry: image.default_registry || '',
    repository: image.repository || '',
    default_tag: image.default_tag || '',
    enabled: image.enabled,
    metadata: image.metadata || {},
  };
  metadataText.value = JSON.stringify(image.metadata || {}, null, 2);
  metadataError.value = '';
  dialogError.value = '';
  dialogVisible.value = true;
}

async function saveImage() {
  if (metadataError.value) {
    dialogError.value = 'Please fix the JSON in Metadata before saving.';
    return;
  }

  dialogSaving.value = true;
  dialogError.value = '';

  try {
    if (editingImage.value) {
      const payload: Record<string, any> = {
        slug: dialogForm.value.slug,
        default_registry: dialogForm.value.default_registry,
        repository: dialogForm.value.repository,
        default_tag: dialogForm.value.default_tag,
        enabled: dialogForm.value.enabled,
        metadata: dialogForm.value.metadata,
      };
      await adminStore.updateNodeImage(editingImage.value.id, payload);
    } else {
      const parsed = parsedImage.value;
      const payload: Record<string, any> = {
        slug: generatedSlug.value,
        default_registry: parsed.registry,
        repository: parsed.repository,
        default_tag: parsed.tag,
        enabled: dialogForm.value.enabled,
      };
      await adminStore.createNodeImage(payload);
    }
    dialogVisible.value = false;
  } catch (e: any) {
    dialogError.value = e.message || 'Failed to save image.';
  } finally {
    dialogSaving.value = false;
  }
}

async function toggleEnabled(image: AdminNodeImage) {
  await adminStore.updateNodeImage(image.id, { enabled: !image.enabled });
}

function confirmDelete(image: AdminNodeImage) {
  confirm.require({
    message: `Delete node image "${image.slug}"? Contexts using this image will have their image unset.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      await adminStore.deleteNodeImage(image.id);
    },
  });
}

// Pull latest image
async function pullLatest(image: AdminNodeImage) {
  try {
    await adminStore.pullNodeImage(image.id);
    toast.add({
      severity: 'info',
      summary: 'Import Started',
      detail: `Pull and import started for "${image.slug}".`,
      life: 4000,
    });
  } catch (e: any) {
    toast.add({
      severity: 'error',
      summary: 'Import Failed',
      detail: e.message || 'Failed to start image pull.',
      life: 6000,
    });
  }
}

// Date formatting helpers
function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
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

function importTooltip(imp: AdminNodeImageImport): string {
  let tip = `Status: ${imp.status}`;
  if (imp.updated_at) {
    tip += `\nUpdated: ${new Date(imp.updated_at).toLocaleString()}`;
  }
  if (imp.error) {
    tip += `\nError: ${imp.error}`;
  }
  return tip;
}
</script>

<style lang="scss" scoped>
.admin-images {
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

.images-table {
  margin-top: 1rem;
}

.image-link {
  color: var(--p-primary-color);
  text-decoration: none;
  font-weight: 500;
  cursor: pointer;

  &:hover {
    text-decoration: underline;
  }
}

.context-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.context-chip {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.8rem;
  background: rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.1);
  color: var(--p-primary-color);
  text-decoration: none;
  transition: background 0.15s ease;

  &:hover {
    background: rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.2);
    text-decoration: none;
  }

  &.disabled {
    opacity: 0.5;
  }
}

.no-contexts {
  color: var(--p-text-secondary-color);
}

.import-status {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.85rem;

  &.completed {
    color: var(--p-green-500, #22c55e);
  }
  &.failed {
    color: var(--p-red-500, #ef4444);
  }
  &.running, &.pending {
    color: var(--p-yellow-600, #ca8a04);
  }
}

.image-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;

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

.parsed-preview {
  background: var(--p-surface-b, #f8f9fa);
  border: 1px solid var(--p-surface-border, #dee2e6);
  border-radius: 6px;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.preview-row {
  display: flex;
  gap: 0.75rem;
  font-size: 0.85rem;
}

.preview-label {
  color: var(--p-text-secondary-color);
  min-width: 5rem;
  font-weight: 500;
}

.preview-value {
  font-family: monospace;
  color: var(--p-text-color);
}

.dialog-error {
  margin-bottom: 0.5rem;
}
</style>
