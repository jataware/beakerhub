<template>
  <div class="admin-layout">
    <nav class="admin-sidebar">
      <h2 class="admin-title">Admin</h2>
      <ul class="admin-nav">
        <li>
          <router-link :to="{ name: 'admin-dashboard' }" class="nav-link" active-class="active">
            <i class="pi pi-th-large"></i>
            <span>Dashboard</span>
          </router-link>
        </li>
        <li>
          <router-link :to="{ name: 'admin-images' }" class="nav-link" active-class="active">
            <i class="pi pi-image"></i>
            <span>Images</span>
          </router-link>
        </li>
        <li>
          <router-link :to="{ name: 'admin-vault' }" class="nav-link" active-class="active">
            <i class="pi pi-lock"></i>
            <span>Vault</span>
          </router-link>
        </li>
        <li>
          <router-link :to="{ name: 'admin-contexts' }" class="nav-link" active-class="active">
            <i class="pi pi-box"></i>
            <span>Contexts</span>
          </router-link>
        </li>
        <li>
          <router-link :to="{ name: 'admin-users' }" class="nav-link" active-class="active">
            <i class="pi pi-users"></i>
            <span>Users</span>
          </router-link>
        </li>
        <li>
          <router-link :to="{ name: 'admin-sessions' }" class="nav-link" active-class="active">
            <i class="pi pi-server"></i>
            <span>Sessions</span>
          </router-link>
        </li>
      </ul>
    </nav>
    <main class="admin-content" :class="{ 'no-padding': isPanelHost }">
      <router-view />
    </main>
    <ConfirmDialog />
    <Toast />
  </div>
</template>

<script lang="ts" setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import ConfirmDialog from 'primevue/confirmdialog';
import Toast from 'primevue/toast';

const route = useRoute();
const isPanelHost = computed(() => !!route.meta?.panelHost);
</script>

<style lang="scss" scoped>
.admin-layout {
  display: grid;
  grid-template-columns: minmax(12rem, max-content) 1fr;
  grid-template-rows: 1fr;
  min-height: 0;
  height: 100%;
}

.admin-sidebar {
  background: var(--p-surface-b, #f8f9fa);
  border-top: 1px solid var(--p-surface-border, #dee2e6);
  border-right: 1px solid var(--p-surface-border, #dee2e6);
  border-bottom: 1px solid var(--p-surface-border, #dee2e6);
  border-top-right-radius: var(--p-surface-border-radius);
  border-bottom-right-radius: var(--p-surface-border-radius);
  padding: 1.5rem 0;
}

.admin-title {
  padding: 0 1.25rem 1rem;
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--p-text-color);
  border-bottom: 1px solid var(--p-surface-border, #dee2e6);
}

.admin-nav {
  list-style: none;
  margin: 0;
  padding: 0.5rem 0;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1.25rem;
  color: var(--p-text-color);
  text-decoration: none;
  font-size: 0.9rem;
  transition: background 0.2s ease;

  &:hover {
    background: rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.08);
  }

  &.active {
    background: rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.12);
    color: var(--p-primary-color);
    font-weight: 500;
  }

  i {
    font-size: 1rem;
    width: 1.25rem;
    text-align: center;
  }
}

.admin-content {
  padding: 1.5rem 2rem;
  height: 100%;
  overflow-x: hidden;
  overflow-y: auto;

  &.no-padding {
    padding: 0;
  }
}
</style>
