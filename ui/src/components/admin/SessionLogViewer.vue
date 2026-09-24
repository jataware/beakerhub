<template>
  <Dialog
    v-model:visible="dialogVisible"
    modal
    :header="`Logs: ${username} / ${serverName}`"
    :style="{ width: '900px', maxWidth: '95vw' }"
    :contentStyle="{ padding: 0 }"
    @show="onShow"
    @hide="onHide"
  >
    <div class="log-viewer">
      <div ref="logContainer" class="log-content" @scroll="onScroll">
        <div v-if="loadingMore" class="load-more-bar">
          <i class="pi pi-spin pi-spinner" /> Loading older logs...
        </div>
        <div v-else-if="truncated" class="load-more-bar">
          <Button label="Load older logs" text size="small" icon="pi pi-arrow-up" @click="loadMore" />
        </div>
        <div v-else-if="logs !== null && !error" class="load-more-bar load-more-complete">
          Beginning of logs
        </div>

        <div v-if="loading && !loadingMore" class="log-loading">
          <i class="pi pi-spin pi-spinner" style="font-size: 1.5rem;" />
          <span>Fetching logs...</span>
        </div>
        <div v-else-if="error" class="log-error">
          <i class="pi pi-exclamation-triangle" />
          <span>{{ error }}</span>
        </div>
        <pre v-else-if="logs !== null" class="log-text">{{ logs }}</pre>
        <div v-else class="log-empty">No logs available.</div>
      </div>

      <div class="log-footer">
        <span v-if="runtimeName" class="runtime-name" :title="runtimeName">
          <i class="pi pi-box" /> {{ runtimeName }}
        </span>
        <span v-if="timestamp" class="fetch-time">
          Fetched {{ formatTime(timestamp) }}
        </span>
        <Button
          label="Refresh"
          icon="pi pi-refresh"
          text
          size="small"
          @click="fetchLogs()"
          :loading="loading && !loadingMore"
        />
      </div>
    </div>
  </Dialog>
</template>

<script lang="ts" setup>
import { ref, watch } from 'vue';
import Dialog from 'primevue/dialog';
import Button from 'primevue/button';
import { useAdminStore } from '@/stores/admin';

const props = defineProps<{
  visible: boolean;
  username: string;
  serverName: string;
}>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
}>();

const adminStore = useAdminStore();

const dialogVisible = ref(props.visible);
watch(() => props.visible, (val) => { dialogVisible.value = val; });
watch(dialogVisible, (val) => { emit('update:visible', val); });

const loading = ref(false);
const loadingMore = ref(false);
const logs = ref<string | null>(null);
const error = ref<string | null>(null);
const runtimeName = ref<string | null>(null);
const timestamp = ref<string | null>(null);
const truncated = ref(false);
const currentTailLines = ref(5000);
const logContainer = ref<HTMLElement | null>(null);

function onShow() {
  currentTailLines.value = 5000;
  logs.value = null;
  error.value = null;
  runtimeName.value = null;
  timestamp.value = null;
  truncated.value = false;
  fetchLogs();
}

function onHide() {
  logs.value = null;
  error.value = null;
}

async function fetchLogs() {
  loading.value = true;
  error.value = null;
  try {
    const result = await adminStore.fetchSessionLogs(
      props.username,
      props.serverName,
      currentTailLines.value
    );
    logs.value = result.logs;
    runtimeName.value = result.runtime_name;
    timestamp.value = result.timestamp;
    truncated.value = result.truncated;
    requestAnimationFrame(() => {
      scrollToBottom();
    });
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to fetch logs';
  } finally {
    loading.value = false;
  }
}

async function loadMore() {
  if (!logContainer.value) return;

  const container = logContainer.value;
  const previousScrollHeight = container.scrollHeight;

  loadingMore.value = true;
  error.value = null;
  currentTailLines.value *= 2;

  try {
    const result = await adminStore.fetchSessionLogs(
      props.username,
      props.serverName,
      currentTailLines.value
    );
    logs.value = result.logs;
    runtimeName.value = result.runtime_name;
    timestamp.value = result.timestamp;
    truncated.value = result.truncated;
    requestAnimationFrame(() => {
      const newScrollHeight = container.scrollHeight;
      container.scrollTop = newScrollHeight - previousScrollHeight;
    });
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to fetch logs';
  } finally {
    loadingMore.value = false;
  }
}

function scrollToBottom() {
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight;
  }
}

function onScroll() {
  // No-op for now; load-more is triggered via the button above the log area
}

function formatTime(isoString: string): string {
  return new Date(isoString).toLocaleTimeString();
}
</script>

<style lang="scss" scoped>
.log-viewer {
  display: flex;
  flex-direction: column;
  height: 70vh;
  max-height: 700px;
}

.load-more-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.4rem;
  background: var(--p-surface-c);
  border-bottom: 1px solid var(--p-surface-border);
  font-size: 0.8rem;
  color: var(--p-text-secondary-color);
  gap: 0.4rem;
  flex-shrink: 0;
}

.load-more-complete {
  font-style: italic;
}

.log-content {
  flex: 1;
  overflow-y: auto;
  background: #1e1e1e;
  min-height: 0;
  border-top: 3px inset var(--p-surface-border);
}

.log-loading,
.log-error,
.log-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  height: 100%;
  color: #ccc;
  font-size: 0.9rem;
}

.log-error {
  color: #f87171;
}

.log-text {
  margin: 0;
  padding: 0.75rem 1rem;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 0.8rem;
  line-height: 1.5;
  color: #d4d4d4;
  white-space: pre-wrap;
  word-break: break-all;
}

.log-footer {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-top: 1px solid var(--p-surface-border, #dee2e6);
  background: var(--p-surface-a, #fff);
  flex-shrink: 0;
}

.runtime-name {
  font-family: monospace;
  font-size: 0.8rem;
  color: var(--p-text-secondary-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 300px;
}

.fetch-time {
  font-size: 0.8rem;
  color: var(--p-text-secondary-color);
  margin-left: auto;
}
</style>
