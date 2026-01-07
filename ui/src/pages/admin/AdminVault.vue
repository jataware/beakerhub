<template>
  <div class="admin-vault">
    <div class="page-header">
      <div>
        <h1>Secret Vault</h1>
        <p>Manage encrypted environment variables and API keys injected into spawned nodes.</p>
      </div>
    </div>

    <!-- Global / Default secrets -->
    <fieldset class="vault-section">
      <legend>
        <i class="pi pi-globe" />
        Default (Global)
      </legend>
      <p class="section-description">Secrets available to all nodes and contexts unless explicitly disabled.</p>
      <SecretVaultEditor :nodeImageId="null" />
    </fieldset>

    <!-- Per-node sections -->
    <div v-if="adminStore.nodeImagesLoading" class="loading">
      <ProgressSpinner style="width: 40px; height: 40px;" />
    </div>
    <template v-else>
      <fieldset v-for="node in adminStore.nodeImages" :key="node.id" class="vault-section">
        <legend>
          <i class="pi pi-image" />
          {{ node.slug }}
          <Tag v-if="!node.enabled" value="disabled" severity="warn" class="node-status-tag" />
        </legend>
        <p class="section-description">
          Secrets specific to <code>{{ node.repository || node.slug }}</code>. Override globals with the same env var name.
        </p>
        <SecretVaultEditor :nodeImageId="node.id" />
      </fieldset>
    </template>
  </div>
</template>

<script lang="ts" setup>
import { onMounted } from 'vue';
import Tag from 'primevue/tag';
import ProgressSpinner from 'primevue/progressspinner';
import { useAdminStore } from '@/stores/admin';
import SecretVaultEditor from '@/components/SecretVaultEditor.vue';

const adminStore = useAdminStore();

onMounted(() => {
  adminStore.fetchNodeImages();
});
</script>

<style lang="scss" scoped>
.admin-vault {
  h1 {
    margin: 0 0 0.5rem;
    font-size: 1.5rem;
  }

  > p {
    margin: 0;
    color: var(--p-text-secondary-color);
  }
}

.page-header {
  margin-bottom: 1.5rem;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 2rem;
}

.vault-section {
  border: 1px solid var(--p-surface-border, #dee2e6);
  border-radius: 6px;
  padding: 1.25rem;
  margin-bottom: 1.5rem;

  legend {
    font-weight: 600;
    font-size: 0.95rem;
    padding: 0 0.5rem;
    color: var(--p-text-color);
    display: flex;
    align-items: center;
    gap: 0.5rem;

    i {
      font-size: 0.9rem;
    }
  }
}

.section-description {
  margin: 0 0 0.75rem;
  font-size: 0.85rem;
  color: var(--p-text-secondary-color);

  code {
    background: var(--p-surface-b, #f8f9fa);
    padding: 0.1rem 0.35rem;
    border-radius: 3px;
    font-size: 0.8rem;
  }
}

.node-status-tag {
  font-size: 0.7rem;
}
</style>
