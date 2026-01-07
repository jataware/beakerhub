<template>
    <div class="header-container" :class="{sticky: props.sticky}">
        <div class="header-icon">
            <router-link :to="{name: 'home'}" class="header-logo-link">
                <HeaderLogo :size="size"/>
            </router-link>
        </div>
        <div class="header-content">
        </div>
        <div class="header-buttons">
            <Button
                text
                size="small"
                @click="toggleDarkMode"
                :title="isDarkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'"
            >
                <i :class="isDarkMode ? 'pi pi-sun' : 'pi pi-moon'"></i>
            </Button>
            <UserMenuButton />
        </div>
    </div>
</template>


<script lang="ts" setup>
import { ref, computed } from 'vue';

import Button from 'primevue/button';

import HeaderLogo from '@/components/HeaderLogo.vue';
import UserMenuButton from './UserMenuButton.vue';
import { useUserStore } from '@/stores/user';

interface Props {
    size?: "minimal" | "small" | "large",
    loggedIn?: boolean,
    sticky?: boolean,
}

const props = withDefaults(defineProps<Props>(), {
    loggedIn: false,
    sticky: false,
});

const userStore = useUserStore();

const profileMenuVisible = ref(false);
const isDarkMode = ref<boolean>(localStorage.getItem('theme-lightmode') === "dark");

function toggleDarkMode() {
  isDarkMode.value = !isDarkMode.value;
  const htmlElement = document.documentElement;

  if (isDarkMode.value) {
    htmlElement.classList.add('beaker-dark');
  } else {
    htmlElement.classList.remove('beaker-dark');
  }

  // use same key as @jataware/beaker-vue theme plugin
  localStorage.setItem('theme-lightmode', isDarkMode.value ? 'dark' : 'light');
}


</script>

<style lang="scss" scoped>

.header-logo-link {
    display: flex;
    align-items: center;
    text-decoration: none;
}

// .header-content {
// display: flex;
// justify-content: space-between;
// align-items: center;
// padding: 1rem 2rem;

// &.size-small {
//     padding: 0rem 1rem;
// }

// &.size-large {
//     padding: 2rem 3rem;
// }

.header-container {
  display: flex;
  justify-content: space-between;
  align-items: center;

  margin: 0;
  padding: 0 2rem;

  &.sticky {
    position: sticky !important;
    top: 0 !important;
    z-index: 100 !important;
    background: transparent;
    backdrop-filter: blur(10px);
    border-bottom: 1px solid rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.1);
  }
}

.header-buttons {
    display: flex;
    gap: 1rem;
    align-items: center;

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

    .profile-menu {
    position: relative;

    .profile-dropdown {
        position: absolute;
        top: calc(100% + 8px);
        right: 0;
        background-color: var(--p-surface-b);
        border: 1px solid var(--p-surface-border);
        border-radius: 8px;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
        backdrop-filter: blur(10px);
        min-width: 160px;
        z-index: 1100;
        overflow: hidden;

        .profile-menu-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.75rem 1rem;
        color: var(--p-text-color);
        cursor: pointer;
        transition: all 0.2s ease;
        font-size: 0.875rem;

        &:hover {
            background: rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.1);
            color: var(--p-primary-color);
        }

        &:not(:last-child) {
            border-bottom: 1px solid var(--p-surface-border);
        }

        i {
            font-size: 1rem;
            opacity: 0.7;
        }

        span {
            font-weight: 500;
        }

        &.user-email-item {
            cursor: default;
            background: var(--p-surface-c);

            &:hover {
            background: var(--p-surface-c);
            color: var(--p-text-color);
            }

            .user-email {
            color: var(--p-text-secondary-color);
            font-weight: 400;
            font-size: 0.8125rem;
            }
        }
        }
    }
    }
}
// }

.header-buttons {
  display: flex;
  gap: 1rem;
  align-items: center;

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
}
</style>
