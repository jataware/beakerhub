<template>
  <div class="stage-edit-panel">
    <div class="panel-header">
      <h2>Edit Stage</h2>
      <Button icon="pi pi-times" text size="small" @click="$emit('close')" title="Close" />
    </div>

    <div v-if="loading" class="loading">
      <ProgressSpinner style="width: 50px; height: 50px;" />
    </div>

    <form v-else @submit.prevent="save" class="stage-form">
      <fieldset class="form-section">
        <legend>Stage Details</legend>
        <div class="form-row">
          <div class="form-field">
            <label for="stage-name">Name</label>
            <InputText id="stage-name" v-model="form.name" />
          </div>
          <div class="form-field" style="max-width: 8rem;">
            <label for="stage-order">Sort Order</label>
            <InputNumber id="stage-order" v-model="form.sort_order" :min="0" />
          </div>
        </div>
      </fieldset>

      <!-- Description (list of strings) -->
      <fieldset class="form-section">
        <legend>Description</legend>
        <div class="description-list">
          <div v-for="(item, index) in form.description" :key="index" class="description-item">
            <Textarea
              :modelValue="item"
              @update:modelValue="updateDescription(index, $event)"
              rows="2"
              autoResize
              class="description-input"
            />
            <Button
              icon="pi pi-times"
              text
              size="small"
              severity="danger"
              @click="removeDescription(index)"
              title="Remove"
            />
          </div>
          <Button
            label="Add Description"
            icon="pi pi-plus"
            size="small"
            severity="secondary"
            @click="addDescription"
          />
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
import InputNumber from 'primevue/inputnumber';
import Textarea from 'primevue/textarea';
import Message from 'primevue/message';
import ProgressSpinner from 'primevue/progressspinner';
import { useAdminStore } from '@/stores/admin';

const props = defineProps<{
  workflowId: number;
  stageId: number;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
}>();

const adminStore = useAdminStore();

const loading = ref(true);
const saving = ref(false);
const errorMessage = ref('');

const form = ref({
  name: '',
  sort_order: 0,
  description: [] as string[],
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

function updateDescription(index: number, value: string) {
  form.value.description[index] = value;
}

function removeDescription(index: number) {
  form.value.description.splice(index, 1);
}

function addDescription() {
  form.value.description.push('');
}

async function loadStage() {
  loading.value = true;
  const stage = await adminStore.fetchWorkflowStage(props.workflowId, props.stageId);
  if (stage) {
    form.value.name = stage.name;
    form.value.sort_order = stage.sort_order;
    form.value.description = [...(stage.description || [])];
    form.value.metadata = stage.metadata || {};
    metadataText.value = JSON.stringify(stage.metadata || {}, null, 2);
  } else {
    errorMessage.value = `Stage ${props.stageId} not found.`;
  }
  loading.value = false;
}

watch(() => props.stageId, loadStage);
onMounted(loadStage);

async function save() {
  if (metadataError.value) {
    errorMessage.value = 'Please fix the JSON in Metadata before saving.';
    return;
  }

  saving.value = true;
  errorMessage.value = '';

  try {
    await adminStore.updateWorkflowStage(props.workflowId, props.stageId, {
      name: form.value.name,
      sort_order: form.value.sort_order,
      description: form.value.description,
      metadata: form.value.metadata,
    });
  } catch (e: any) {
    errorMessage.value = e.message || 'Failed to save stage.';
  } finally {
    saving.value = false;
  }
}
</script>

<style lang="scss" scoped>
.stage-edit-panel {
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

.stage-form {
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

  label {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--p-text-color);
  }
}

.description-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.description-item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;

  .description-input {
    flex: 1;
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

.form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-bottom: 1rem;
}
</style>
