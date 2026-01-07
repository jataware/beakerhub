<template>
  <Dialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    :header="header"
    :modal="true"
    :style="{ width: '640px' }"
    class="secret-policy-dialog"
  >
    <p class="dialog-intro">
      Each axis keeps its default — the option marked <em>(Default)</em> — until you choose something
      else. Overrides are stored with the secret and applied when a server is spawned.
    </p>

    <div class="policy-axes">
      <div v-for="axis in SECRET_POLICY_AXES" :key="axis.key" class="policy-axis">
        <div class="axis-header">
          <label :for="`policy-${axis.key}`" class="axis-label">{{ axis.label }}</label>
          <Tag
            v-if="isOverridden(axis.key)"
            value="overridden"
            severity="info"
            class="axis-tag"
          />
          <Tag v-else value="default" severity="secondary" class="axis-tag" />
        </div>
        <p class="axis-description">{{ axis.description }}</p>
        <p v-if="axis.note" class="axis-note">
          <i class="pi pi-info-circle" />
          {{ axis.note }}
        </p>
        <Select
          :inputId="`policy-${axis.key}`"
          :modelValue="selectionFor(axis.key)"
          @update:modelValue="setPolicy(axis, $event)"
          :options="optionsFor(axis)"
          optionLabel="label"
          optionValue="value"
          class="axis-select"
        >
          <template #option="{ option }">
            <div class="option-row">
              <span class="option-label">{{ option.label }}</span>
              <span class="option-description">{{ option.description }}</span>
            </div>
          </template>
        </Select>
      </div>
    </div>

    <template #footer>
      <Button
        label="Reset all to defaults"
        severity="secondary"
        text
        :disabled="overrideCount(working) === 0"
        @click="resetAll"
      />
      <Button label="Cancel" severity="secondary" @click="$emit('update:visible', false)" />
      <Button label="Save" :loading="saving" @click="$emit('save', pruneDefaults(working))" />
    </template>
  </Dialog>
</template>

<script lang="ts" setup>
import { ref, computed, watch } from 'vue';
import Dialog from 'primevue/dialog';
import Select from 'primevue/select';
import Button from 'primevue/button';
import Tag from 'primevue/tag';
import {
  SECRET_POLICY_AXES,
  effectivePolicy,
  overrideCount,
  pruneDefaults,
  type SecretPolicies,
  type SecretPolicyAxis,
  type SecretPolicyAxisDefinition,
  type SecretPolicyOption,
  type SecretPolicyType,
} from '@/utils/secretPolicies';

const props = defineProps<{
  visible: boolean;
  /** Env var name, shown in the dialog header. */
  envVar?: string;
  policies?: SecretPolicies | null;
  saving?: boolean;
}>();

defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'save', policies: SecretPolicies): void;
}>();

/** Working copy so Cancel discards cleanly. */
const working = ref<SecretPolicies>({});

watch(
  () => [props.visible, props.policies] as const,
  ([isVisible]) => {
    if (isVisible) {
      working.value = { ...(props.policies || {}) };
    }
  },
  { immediate: true },
);

const header = computed(() =>
  props.envVar ? `Policies — ${props.envVar}` : 'Secret policies',
);

function isOverridden(key: SecretPolicyAxis): boolean {
  const value = working.value[key];
  const axis = SECRET_POLICY_AXES.find(a => a.key === key);
  return value !== undefined && value !== axis?.defaultValue;
}

/** The select's current value: the policy in force, default or overridden. */
function selectionFor(key: SecretPolicyAxis): SecretPolicyType {
  return effectivePolicy(working.value, key);
}

/**
 * Options for an axis, with the default hoisted to the top and marked as such.
 * The default is not offered a second time as a separate "inherit" entry — picking it
 * *is* inheriting, and listing it twice made two identical-looking choices.
 */
function optionsFor(axis: SecretPolicyAxisDefinition): SecretPolicyOption[] {
  const isDefault = (option: SecretPolicyOption) => option.value === axis.defaultValue;
  const defaultOption = axis.options.find(isDefault);
  const rest = axis.options.filter(option => !isDefault(option));
  if (!defaultOption) {
    return rest;
  }
  return [
    { ...defaultOption, label: `${defaultOption.label} (Default)` },
    ...rest,
  ];
}

function setPolicy(axis: SecretPolicyAxisDefinition, value: string) {
  const next = { ...working.value };
  if (value === axis.defaultValue) {
    // Choosing the default means inheriting it, so drop the key entirely.
    delete next[axis.key];
  } else {
    next[axis.key] = value as SecretPolicyType;
  }
  working.value = next;
}

function resetAll() {
  working.value = {};
}
</script>

<style lang="scss" scoped>
.dialog-intro {
  margin: 0 0 1rem;
  font-size: 0.85rem;
  color: var(--p-text-secondary-color);
}

.policy-axes {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.policy-axis {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.axis-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.axis-label {
  font-weight: 600;
  font-size: 0.9rem;
}

.axis-tag {
  font-size: 0.65rem;
}

.axis-description {
  margin: 0;
  font-size: 0.8rem;
  color: var(--p-text-secondary-color);
}

.axis-note {
  margin: 0;
  font-size: 0.78rem;
  color: var(--p-text-secondary-color);
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-style: italic;

  i {
    font-size: 0.75rem;
  }
}

.axis-select {
  margin-top: 0.15rem;
  width: 100%;
}

.option-row {
  display: flex;
  flex-direction: column;
}

.option-label {
  font-size: 0.85rem;
}

.option-description {
  font-size: 0.75rem;
  color: var(--p-text-secondary-color);
}
</style>
