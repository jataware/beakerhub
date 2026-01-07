import { defineStore } from 'pinia';
import { ref, computed, watch } from 'vue';
import { fetch } from '@/utils/fetch';
import { useSessionStore } from '@/stores/session';

export interface UserData {
  name: string;
  roles: string[];
  groups: string[];
  admin: boolean;
  servers: UserServerMap;
}

export interface UserServerData {
  name: string;
  ready: boolean;
  stopped: boolean;
  pending: "spawn" | "stop";
  url: string;
  progress_url: string;
  full_url?: string;
  full_progress_url?: string;
  started: string;
  last_activity: string;
  state: any;
  user_options: any;
}

export type UserServerMap = {[key: string]: UserServerData};

export const useUserStore = defineStore('user', () => {
  // State
  const username = ref<string | undefined>(undefined);
  const roles = ref<string[]>([]);
  const groups = ref<string[]>([]);
  const isAdmin = ref<boolean>(false);
  const initialized = ref<boolean>(false);
  const loading = ref<boolean>(false);
  const servers = ref<UserServerMap>({});
  const _refreshIntervalId = ref();

  // Getters
  const isLoggedIn = computed(() => Boolean(username.value !== undefined));
  const displayName = computed(() => username.value ?? '');

  // Actions
  async function refresh() {
    loading.value = true;
    try {
      const result = await fetch('/api/user');
      if (result.ok) {
        const data: UserData = await result.json();
        username.value = data.name;
        roles.value = data.roles;
        groups.value = data.groups;
        isAdmin.value = data.admin;
        servers.value = data.servers;

        // Push servers to session store
        const sessionStore = useSessionStore();
        sessionStore.setServersFromUserApi(data.servers);
      } else {
        // TODO: Check reason for failure and potentially do not reset all values to default.
        username.value = undefined;
        roles.value = [];
        groups.value = [];
        isAdmin.value = false;
        servers.value = {};

        // Clear servers in session store
        const sessionStore = useSessionStore();
        sessionStore.setServersFromUserApi(undefined);
      }
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  async function isSessionValid() {
    if (!username.value) {
      return false;
    }
    const result = await fetch(`/api/user?user=${encodeURIComponent(username.value)}`, {
      method: 'HEAD',
    });
    return result.ok;
  }

  async function prepareLogin() {
    try {
      const response = await fetch('/api/auth/login', { method: 'GET' });
      if (response.ok) {
        const data = await response.json();
        return { success: true, ...data };
      } else {
        const errorData = await response.json();
        return { success: false, error: errorData.message || 'signup failed' };
      }
    } catch (err) {
      console.error('Login error:', err);
      return { success: false, error: 'network error' };
    }
  }

  async function login(email: string, password: string): Promise<any> {
    loading.value = true;
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username: email, password }),
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data: UserData = await response.json();
        username.value = data.name;
        roles.value = data.roles;
        groups.value = data.groups;
        isAdmin.value = data.admin;
        servers.value = data.servers;

        // Push servers to session store
        const sessionStore = useSessionStore();
        sessionStore.setServersFromUserApi(data.servers);

        return { success: true, ...data };
      } else {
        const errorData = await response.json();
        return { success: false, error: errorData.message || 'signup failed' };
      }
    } catch (err) {
      console.error('Login error:', err);
      return { success: false, error: 'network error' };
    } finally {
      loading.value = false;
    }
  }

  async function signup(email: string, password: string, organization?: string): Promise<any> {
    try {
      const response = await fetch('/api/auth/signup', {
        method: 'POST',
        body: JSON.stringify({ username: email, password, organization }),
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        return { success: true, ...data };
      } else {
        const errorData = await response.json();
        return { success: false, error: errorData.message || 'signup failed' };
      }
    } catch (err) {
      console.error('signup error:', err);
      return { success: false, error: 'network error' };
    }
  }

  async function confirmSignup(email: string, code: string): Promise<any> {
    try {
      const response = await fetch('/api/auth/signup-confirmation', {
        method: 'POST',
        body: JSON.stringify({ username: email, code }),
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        return { success: true, ...data };
      } else {
        const errorData = await response.json();
        return { success: false, error: errorData.message || 'verification failed' };
      }
    } catch (err) {
      console.error('confirmation error:', err);
      return { success: false, error: 'network error' };
    }
  }

  async function logout(): Promise<void> {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
    } catch (err) {
      console.error('logout error:', err);
    }

    // Clear local user state
    username.value = undefined;
    roles.value = undefined;
    groups.value = undefined;
    isAdmin.value = undefined;
    servers.value = undefined;

    // Clear servers in session store
    const sessionStore = useSessionStore();
    sessionStore.setServersFromUserApi(undefined);
  }

  async function forgotPassword(email: string): Promise<any> {
    try {
      const response = await fetch('/api/auth/password-forgot', {
        method: 'POST',
        body: JSON.stringify({ username: email }),
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        return { success: true, ...data };
      } else {
        const errorData = await response.json();
        return { success: false, error: errorData.message || 'failed to send reset code' };
      }
    } catch (err) {
      console.error('forgot password error:', err);
      return { success: false, error: 'network error' };
    }
  }

  async function confirmPassword(email: string, code: string, newPassword: string): Promise<any> {
    try {
      const response = await fetch('/api/auth/password-confirm', {
        method: 'POST',
        body: JSON.stringify({ username: email, code, password: newPassword }),
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        return { success: true, ...data };
      } else {
        const errorData = await response.json();
        return { success: false, error: errorData.message || 'failed to reset password' };
      }
    } catch (err) {
      console.error('confirm password error:', err);
      return { success: false, error: 'network error' };
    }
  }

  // Helper function to wait for initialization
  function waitForInit(): Promise<void> {
    if (initialized.value) return Promise.resolve();
    return new Promise((resolve) => {
      const unwatch = watch(initialized, (val) => {
        if (val) {
          unwatch();
          resolve();
        }
      });
    });
  }

  // Initialize on store creation and set up to refresh every 15 seconds.
  refresh();
  _refreshIntervalId.value = setInterval(refresh, 15000);

  return {
    // State
    username,
    roles,
    groups,
    isAdmin,
    initialized,
    loading,
    servers,
    // Getters
    isLoggedIn,
    displayName,
    // Actions
    refresh,
    isSessionValid,
    prepareLogin,
    login,
    signup,
    confirmSignup,
    logout,
    forgotPassword,
    confirmPassword,
    waitForInit,
  };
});
