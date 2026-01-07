<template>
  <div class="edit-header" >
    <div class="panel-header">
      <h2>{{ isNew ? 'Create Context' : `Edit Context: ${sourceKey}` }}</h2>
      <Button label="Back to Contexts" icon="pi pi-arrow-left" text size="small" @click="$emit('close')" />
    </div>
    <div class="warning-container">
      <div class="warning"><span style="font-weight: bold;">Warning:</span> Edits to contexts only affect how they are displayed in the interface and do not affect actual running of workflows, integrations, etc.</div>
    </div>
  </div>

  <PanelStack :layouts="layouts" @panel-click="onPanelClick">
    <template #context="{ layout }">
      <ContextEditPanel
        :sourceKey="sourceKey"
        :collapsed="layout.collapsed"
        @close="navigateToContexts"
        @open-workflow="openWorkflow"
        @open-integration="openIntegration"
      />
    </template>
    <template v-if="workflowId" #workflow>
      <WorkflowEditPanel
        :workflowId="workflowId"
        @close="closeWorkflow"
        @open-stage="openStage"
      />
    </template>
    <template v-if="stageId && workflowId" #stage>
      <StageEditPanel
        :workflowId="workflowId"
        :stageId="stageId"
        @close="closeStage"
      />
    </template>
    <template v-if="integrationId" #integration>
      <IntegrationEditPanel
        :integrationId="integrationId"
        :currentContextSourceKey="sourceKey"
        @close="closeIntegration"
      />
    </template>
  </PanelStack>
</template>

<script lang="ts" setup>
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import Button from 'primevue/button';
import PanelStack from '@/components/panels/PanelStack.vue';
import { usePanelStack, type PanelDef } from '@/composables/usePanelStack';
import ContextEditPanel from './panels/ContextEditPanel.vue';
import WorkflowEditPanel from './panels/WorkflowEditPanel.vue';
import StageEditPanel from './panels/StageEditPanel.vue';
import IntegrationEditPanel from './panels/IntegrationEditPanel.vue';

const route = useRoute();
const router = useRouter();

const sourceKey = computed(() => route.params.sourceKey as string);
const isNew = computed(() => sourceKey.value === 'new');
const workflowId = computed(() => {
  const id = route.params.workflowId as string | undefined;
  return id ? parseInt(id, 10) : null;
});
const stageId = computed(() => {
  const id = route.params.stageId as string | undefined;
  return id ? parseInt(id, 10) : null;
});
const integrationId = computed(() => {
  const id = route.params.integrationId as string | undefined;
  return id ? parseInt(id, 10) : null;
});

const panels = computed<PanelDef[]>(() => {
  const result: PanelDef[] = [
    { key: 'context', label: sourceKey.value, component: 'ContextEditPanel' },
  ];
  if (workflowId.value) {
    result.push({ key: 'workflow', label: `Workflow #${workflowId.value}`, component: 'WorkflowEditPanel' });
  }
  if (stageId.value && workflowId.value) {
    result.push({ key: 'stage', label: `Stage #${stageId.value}`, component: 'StageEditPanel' });
  }
  if (integrationId.value) {
    result.push({ key: 'integration', label: `Integration #${integrationId.value}`, component: 'IntegrationEditPanel' });
  }
  return result;
});

const { layouts } = usePanelStack(panels);

function navigateToContexts() {
  router.push({ name: 'admin-contexts' });
}

function openWorkflow(id: number) {
  router.push({
    name: 'admin-context-workflow',
    params: { sourceKey: sourceKey.value, workflowId: String(id) },
  });
}

function closeWorkflow() {
  router.push({
    name: 'admin-context-edit',
    params: { sourceKey: sourceKey.value },
  });
}

function openIntegration(id: number) {
  router.push({
    name: 'admin-context-integration',
    params: { sourceKey: sourceKey.value, integrationId: String(id) },
  });
}

function closeIntegration() {
  router.push({
    name: 'admin-context-edit',
    params: { sourceKey: sourceKey.value },
  });
}

function openStage(id: number) {
  if (!workflowId.value) return;
  router.push({
    name: 'admin-context-workflow-stage',
    params: {
      sourceKey: sourceKey.value,
      workflowId: String(workflowId.value),
      stageId: String(id),
    },
  });
}

function closeStage() {
  if (!workflowId.value) return;
  router.push({
    name: 'admin-context-workflow',
    params: { sourceKey: sourceKey.value, workflowId: String(workflowId.value) },
  });
}

function onPanelClick(key: string) {
  if (key === 'context') {
    // Clicking collapsed context panel returns to context-only view
    router.push({
      name: 'admin-context-edit',
      params: { sourceKey: sourceKey.value },
    });
  } else if (key === 'workflow' && workflowId.value) {
    // Clicking collapsed workflow panel returns to workflow view
    router.push({
      name: 'admin-context-workflow',
      params: { sourceKey: sourceKey.value, workflowId: String(workflowId.value) },
    });
  } else if (key === 'integration' && integrationId.value) {
    // Clicking collapsed integration panel returns to integration view
    router.push({
      name: 'admin-context-integration',
      params: { sourceKey: sourceKey.value, integrationId: String(integrationId.value) },
    });
  }
}
</script>

<style lang="scss" scoped>
/* Host fills its parent fully — no extra padding needed */
.edit-header {
  padding: 0 2rem;

}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.warning-container {
  text-align: center;
  margin-top: 0.5rem;
  margin-bottom: 1.25rem;
  font-size: large;
}

.warning {
  color: var(--p-red-500);
}

</style>
