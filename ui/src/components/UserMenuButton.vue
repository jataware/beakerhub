<template>
  <div class="profile-menu">
      <Button
      text
      size="small"
      @click="userMenu.toggle($event);"
      :title="'User Menu'"
      >
      <i class="pi pi-user"></i>
      </Button>
      <Menu ref="userMenu" :model="userMenuItems" :popup="true">
        <template #item="{ item, props: itemProps }">
          <router-link v-if="item.route" :to="item.route" custom v-slot="{ href, navigate }">
            <a :href="href" v-bind="itemProps.action" @click="navigate">
              <span v-bind="itemProps.icon" />
              <span v-bind="itemProps.label">{{ item.label }}</span>
            </a>
          </router-link>
          <a v-else v-bind="itemProps.action" :class="{ 'p-disabled': item.disabled }">
            <span v-bind="itemProps.icon" />
            <span v-bind="itemProps.label">{{ item.label }}</span>
          </a>
        </template>
      </Menu>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';

import Button from 'primevue/button';
import Menu from 'primevue/menu';
import type { MenuItem } from 'primevue/menuitem';

import { useUserStore } from '@/stores/user';

const router = useRouter();
const userStore = useUserStore();

const userMenu = ref();

const userMenuItems = computed(() => {
  let menu: Array<MenuItem>;
  if (userStore.isLoggedIn) {
    menu = [
        {
            label: userStore.username,
            disabled: true,
        },
        {
            label: "Logout",
            command: async () => {
              router.push({name: "logout", force: true});
            }
        }
    ];
    if (userStore.isAdmin) {
        menu.splice(1, 0, {
            label: "Admin",
            route: { name: "admin-dashboard" },
        });
    }
  }
  else {
    menu = [
      {
        label: "Login",
        route: { name: "login" },
      },
      {
        label: "Sign up",
        route: { name: "signup" },
      },
    ];
  }
  return menu;
});

</script>

<style lang="scss" scoped>
  button {
    backdrop-filter: blur(8px);
    border: 1px solid rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.2);
    transition: all 0.3s ease;

    &:hover {
      background: rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.1);
      border-color: var(--p-primary-color);
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.3);
    }
  }
</style>
