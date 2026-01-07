<template>
  <div class="integration-edit-panel">
    <div class="panel-header">
      <h2>Edit Integration</h2>
      <Button icon="pi pi-times" text size="small" @click="$emit('close')" title="Close" />
    </div>

    <div v-if="loading" class="loading">
      <ProgressSpinner style="width: 50px; height: 50px;" />
    </div>

    <form v-else @submit.prevent="save" class="integration-form">
      <!-- Cross-context warning -->
      <Message v-if="otherContexts.length > 0" severity="warn" :closable="false">
        This integration is also used by:
        <strong>{{ otherContexts.map(c => c.display_name).join(', ') }}</strong>.
        Changes here will affect all contexts.
      </Message>

      <!-- Read-only source fields -->
      <fieldset class="form-section">
        <legend>Source Information</legend>
        <div class="form-row">
          <div class="form-field">
            <label>Slug</label>
            <InputText :modelValue="integration?.slug ?? '—'" disabled />
          </div>
          <div class="form-field">
            <label>Source Package</label>
            <InputText :modelValue="integration?.source_package ?? '—'" disabled />
          </div>
          <div class="form-field">
            <label>Source UUID</label>
            <InputText :modelValue="integration?.source_uuid ?? '—'" disabled />
          </div>
        </div>
      </fieldset>

      <!-- Editable fields -->
      <fieldset class="form-section">
        <legend>Integration Details</legend>
        <div class="form-row">
          <div class="form-field full-width">
            <label for="int-name">Name</label>
            <InputText id="int-name" v-model="form.name" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-field full-width">
            <label for="int-description">Description</label>
            <Textarea id="int-description" v-model="form.description" rows="3" autoResize />
          </div>
        </div>
        <div class="form-row">
          <div class="form-field inline-check">
            <Checkbox id="int-enabled" v-model="form.enabled" :binary="true" />
            <label for="int-enabled">Enabled</label>
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
import { ref, computed, onMounted, watch } from 'vue';
import Button from 'primevue/button';
import InputText from 'primevue/inputtext';
import Textarea from 'primevue/textarea';
import Checkbox from 'primevue/checkbox';
import Message from 'primevue/message';
import ProgressSpinner from 'primevue/progressspinner';
import { useAdminStore } from '@/stores/admin';
import type { AdminIntegrationDetail } from '@/stores/admin';

const props = defineProps<{
  integrationId: number;
  currentContextSourceKey?: string;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
}>();

const adminStore = useAdminStore();

const loading = ref(true);
const saving = ref(false);
const errorMessage = ref('');
const integration = ref<AdminIntegrationDetail | null>(null);

const form = ref({
  name: '',
  description: '',
  enabled: true,
});

const otherContexts = computed(() => {
  if (!integration.value?.contexts) return [];
  return integration.value.contexts.filter(c => c.source_key !== props.currentContextSourceKey);
});

async function loadIntegration() {
  loading.value = true;
  const integ = await adminStore.fetchIntegration(props.integrationId);
  if (integ) {
    integration.value = integ;
    form.value.name = integ.name;
    form.value.description = integ.description || '';
    form.value.enabled = integ.enabled;
  } else {
    errorMessage.value = `Integration ${props.integrationId} not found.`;
  }
  loading.value = false;
}

watch(() => props.integrationId, loadIntegration);
onMounted(loadIntegration);

async function save() {
  saving.value = true;
  errorMessage.value = '';

  try {
    const result = await adminStore.updateIntegration(props.integrationId, {
      name: form.value.name,
      description: form.value.description,
      enabled: form.value.enabled,
    });
    if (result) {
      integration.value = result;
    }
  } catch (e: any) {
    errorMessage.value = e.message || 'Failed to save integration.';
  } finally {
    saving.value = false;
  }
}
</script>

<style lang="scss" scoped>
.integration-edit-panel {
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

.integration-form {
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

.form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-bottom: 1rem;
}
</style>
