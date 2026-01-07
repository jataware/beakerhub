<template>
  <div class="workflow-edit-panel">
    <div class="panel-header">
      <h2>Edit Workflow</h2>
      <Button icon="pi pi-times" text size="small" @click="$emit('close')" title="Close" />
    </div>

    <div v-if="loading" class="loading">
      <ProgressSpinner style="width: 50px; height: 50px;" />
    </div>

    <form v-else @submit.prevent="save" class="workflow-form">
      <!-- Read-only source fields -->
      <fieldset class="form-section">
        <legend>Source Information</legend>
        <div class="form-row">
          <div class="form-field">
            <label>Source Package</label>
            <InputText :modelValue="workflow?.source_package ?? '—'" disabled />
          </div>
          <div class="form-field">
            <label>Source Path</label>
            <InputText :modelValue="workflow?.source_path ?? '—'" disabled />
          </div>
        </div>
      </fieldset>

      <!-- Editable fields -->
      <fieldset class="form-section">
        <legend>Workflow Details</legend>
        <div class="form-row">
          <div class="form-field full-width">
            <label for="wf-title">Title</label>
            <InputText id="wf-title" v-model="form.title" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-field full-width">
            <label for="wf-human-desc">Human Description</label>
            <Textarea id="wf-human-desc" v-model="form.human_description" rows="3" autoResize />
          </div>
        </div>
        <div class="form-row">
          <div class="form-field full-width">
            <label for="wf-agent-desc">Agent Description</label>
            <Textarea id="wf-agent-desc" v-model="form.agent_description" rows="3" autoResize />
          </div>
        </div>
        <div class="form-row">
          <div class="form-field full-width">
            <label for="wf-example">Example Prompt</label>
            <Textarea id="wf-example" v-model="form.example_prompt" rows="2" autoResize />
          </div>
        </div>
        <div class="form-row">
          <div class="form-field">
            <label for="wf-category">Category</label>
            <InputText id="wf-category" v-model="form.category_slug" placeholder="Category slug" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-field inline-check">
            <Checkbox id="wf-hidden" v-model="form.hidden" :binary="true" />
            <label for="wf-hidden">Hidden</label>
          </div>
          <div class="form-field inline-check">
            <Checkbox id="wf-enabled" v-model="form.enabled" :binary="true" />
            <label for="wf-enabled">Enabled</label>
          </div>
        </div>
      </fieldset>

      <!-- Metadata JSON -->
      <fieldset class="form-section">
        <legend>Metadata</legend>
        <div class="form-row">
          <div class="form-field full-width">
            <Textarea
              v-model="metadataText"
              rows="4"
              class="json-editor"
              :class="{ 'json-error': metadataError }"
              spellcheck="false"
            />
            <small v-if="metadataError" class="error-text">{{ metadataError }}</small>
          </div>
        </div>
      </fieldset>

      <!-- Stages list -->
      <fieldset class="form-section">
        <legend>Stages</legend>
        <DataTable :value="workflow?.stages ?? []" class="stages-table">
          <Column field="sort_order" header="#" style="width: 3rem;" />
          <Column field="name" header="Name">
            <template #body="{ data }">
              <a class="stage-link" @click.prevent="$emit('open-stage', data.id)">{{ data.name }}</a>
            </template>
          </Column>
          <Column header="Descriptions" style="width: 8rem;">
            <template #body="{ data }">
              {{ (data.description || []).length }} items
            </template>
          </Column>
        </DataTable>
      </fieldset>

      <!-- Actions -->
      <div class="form-actions">
        <Button label="Cancel" severity="secondary" @click="$emit('close')" />
        <Button type="submit" label="Save" :loading="saving" />
      </div>

      <Message v-if="errorMessage" severity="error" :closable="true" @close="errorMessage = ''">
        {{ errorMessage }}
      </Message>
    </form>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, watch } from 'vue';
import Button from 'primevue/button';
import InputText from 'primevue/inputtext';
import Textarea from 'primevue/textarea';
import Checkbox from 'primevue/checkbox';
import Message from 'primevue/message';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import ProgressSpinner from 'primevue/progressspinner';
import { useAdminStore } from '@/stores/admin';
import type { AdminWorkflowDetail } from '@/stores/admin';

const props = defineProps<{
  workflowId: number;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'open-stage', stageId: number): void;
}>();

const adminStore = useAdminStore();

const loading = ref(true);
const saving = ref(false);
const errorMessage = ref('');
const workflow = ref<AdminWorkflowDetail | null>(null);

const form = ref({
  title: '',
  human_description: '',
  agent_description: '',
  example_prompt: '',
  category_slug: '' as string | null,
  hidden: false,
  enabled: true,
  metadata: {} as Record<string, any>,
});

const metadataText = ref('{}');
const metadataError = ref('');

watch(metadataText, (val) => {
  try {
    form.value.metadata = JSON.parse(val);
    metadataError.value = '';
  } catch (e: any) {
    metadataError.value = e.message;
  }
});

async function loadWorkflow() {
  loading.value = true;
  const wf = await adminStore.fetchWorkflow(props.workflowId);
  if (wf) {
    workflow.value = wf;
    form.value.title = wf.title;
    form.value.human_description = wf.human_description || '';
    form.value.agent_description = wf.agent_description || '';
    form.value.example_prompt = wf.example_prompt || '';
    form.value.category_slug = wf.category?.slug ?? null;
    form.value.hidden = wf.hidden;
    form.value.enabled = wf.enabled;
    form.value.metadata = wf.metadata || {};
    metadataText.value = JSON.stringify(wf.metadata || {}, null, 2);
  } else {
    errorMessage.value = `Workflow ${props.workflowId} not found.`;
  }
  loading.value = false;
}

watch(() => props.workflowId, loadWorkflow);
onMounted(loadWorkflow);

async function save() {
  if (metadataError.value) {
    errorMessage.value = 'Please fix the JSON in Metadata before saving.';
    return;
  }

  saving.value = true;
  errorMessage.value = '';

  try {
    const result = await adminStore.updateWorkflow(props.workflowId, {
      title: form.value.title,
      human_description: form.value.human_description,
      agent_description: form.value.agent_description,
      example_prompt: form.value.example_prompt,
      category_slug: form.value.category_slug,
      hidden: form.value.hidden,
      enabled: form.value.enabled,
      metadata: form.value.metadata,
    });
    if (result) {
      workflow.value = result;
    }
  } catch (e: any) {
    errorMessage.value = e.message || 'Failed to save workflow.';
  } finally {
    saving.value = false;
  }
}
</script>

<style lang="scss" scoped>
.workflow-edit-panel {
  padding: 1.25rem;

  h2 {
    margin: 0;
    font-size: 1.25rem;
  }
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 3rem;
}

.workflow-form {
  max-width: 700px;
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

.stage-link {
  color: var(--p-primary-color);
  cursor: pointer;
  text-decoration: none;

  &:hover {
    text-decoration: underline;
  }
}

.form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-bottom: 1rem;
}
</style>
