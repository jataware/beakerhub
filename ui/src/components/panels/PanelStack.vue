<template>
  <div class="panel-stack">
    <div
      v-for="layout in layouts"
      :key="layout.key"
      class="panel-slot"
      :class="{ collapsed: layout.collapsed }"
      :style="{ width: layout.width }"
    >
      <div
        v-if="layout.collapsed"
        class="panel-collapsed-overlay"
        @click="$emit('panel-click', layout.key)"
      >
        <span class="panel-collapsed-label">{{ layout.label }}</span>
      </div>
      <div v-show="!layout.collapsed" class="panel-content">
        <slot :name="layout.key" :layout="layout" />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { PanelLayout } from '@/composables/usePanelStack';

defineProps<{
  layouts: PanelLayout[];
}>();

defineEmits<{
  (e: 'panel-click', key: string): void;
}>();
</script>

<style lang="scss" scoped>
.panel-stack {
  display: flex;
  overflow: hidden;
}

.panel-slot {
  overflow: hidden;
  transition: width 0.3s ease;
  position: relative;
  border-right: 1px solid var(--p-surface-border, #dee2e6);
  display: flex;
  flex-direction: column;

  &:last-child {
    border-right: none;
  }
}

.panel-collapsed-overlay {
  position: absolute;
  inset: 0;
  background: var(--p-surface-b, #f8f9fa);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s ease;

  &:hover {
    background: rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.08);
  }
}

.panel-collapsed-label {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  transform: rotate(180deg);
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--p-text-secondary-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-height: calc(100% - 2rem);
}
</style>
