import { defineStore } from 'pinia';
import { ref, computed, watch } from 'vue';
import { fetch } from '@/utils/fetch';

import { useUserStore } from '@/stores/user';
import type { UserServerData, UserServerMap } from '@/stores/user';


export type ServerStatus = "pending" | "launching" | "ready" | "failed";
export type SessionStatus = "active" | "pending" | "unknown" | "suspended" | "missing";


export interface SessionData {
  id: string;
  status: string;
  serverInfo?: UserServerData;
  sessionConfig?: SessionConfig;
}

export interface SessionConfig {
  nodeSlug: string;
  contextSlug: string;
  contextOptions: {[key: string]: any};
  shared?: boolean;
}

export interface SessionServerData extends UserServerData {
  provisioning?: {
    percentage?: number;
    logs?: string[];
  }
}

export type SessionServerMap = {[key: string]: SessionServerData};

export const useSessionStore = defineStore('session', () => {
  // State
  const initialized = ref<boolean>(false);
  const sessions = ref<SessionData[]>([]);
  const servers = ref<SessionServerMap>({});

  const serverApiUrlBase = computed(() => {
    const userStore = useUserStore();
    return `/api/users/${userStore.username}/servers/`;
  });

  // Actions

  // Called by UserStore when it fetches/updates user data
  function setServersFromUserApi(serverData: UserServerMap | undefined) {
    if (serverData === undefined) {
      // User is not logged in so we should clear the contents.
      servers.value = {};
    }
    else {
      // Update existing entries and add new ones without overwriting local-only data.
      Object.entries(serverData).forEach(([serverName, serverData]) => {
        if (servers.value[serverName]) {
          Object.assign(servers.value[serverName], serverData);
        } else {
          servers.value[serverName] = {
            provisioning: {
              logs: [],
              percentage: 0,
            },
            ...serverData,
          };
        }
      });
      // Remove servers that are no longer present in the API response.
      for (const key of Object.keys(servers.value)) {
        if (!(key in serverData)) {
          delete servers.value[key];
        }
      }
    }
    initialized.value = true;
  }

  async function refresh() {
    // For now, trigger user store refresh which will push servers back to us
    const userStore = useUserStore();
    await userStore.refresh();
  }

  async function isSessionActive(sessionId: string): Promise<boolean> {
    // TODO: Implement session status check
    return false;
  }

  async function checkServer(sessionId: string): Promise<UserServerData | undefined> {
    // TODO: Implement server status check
    return servers.value?.[sessionId];
  }

  async function spawnServer(sessionId: string | null | undefined, sessionConfig: SessionConfig): Promise<SessionServerData> {
    const url = (sessionId ? `${serverApiUrlBase.value}${sessionId}` : serverApiUrlBase.value);
    const spawnRequest = await fetch(url, {
      method: "POST",
      body: JSON.stringify(sessionConfig),
      headers: {
        "Content-Type": "application/json"
      }
    });
    if (!spawnRequest.ok) {
      throw new Error(`Spawn request failed: ${spawnRequest.status} ${spawnRequest.statusText}`);
    }
    const data = await spawnRequest.json();
    const serverData: SessionServerData = {
      name: data.name,
      ready: data.ready,
      stopped: data.stopped,
      pending: data.pending,
      url: data.url,
      progress_url: data.progress_url,
      full_url: data.full_url,
      full_progress_url: data.full_progress_url,
      started: data.started,
      last_activity: data.last_activity,
      state: data.state,
      user_options: data.user_options,
      provisioning: {
        percentage: 0,
        logs: [],
      }
    };
    servers.value[serverData.name] = serverData;
    return serverData;
  }

  async function deleteServer(serverName: string): Promise<boolean> {
    const userStore = useUserStore();
    const username = userStore.username;

    if (!username) return false;
    try {
      const response = await fetch(`/api/users/${username}/servers/${serverName}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        // Remove the spawner record as well as stopping the server. Without
        // this the record persists and the session reappears as stopped.
        body: JSON.stringify({ remove: true }),
      });
      if (response.ok || response.status === 204) {
        // Refresh user store to resync server data
        await userStore.refresh();
        return true;
      }
      return false;
    } catch (err) {
      console.error('Failed to delete server:', err);
      return false;
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

  return {
    // State
    initialized,
    sessions,
    servers,
    // Getters
    serverApiUrlBase,
    // Actions
    setServersFromUserApi,
    refresh,
    isSessionActive,
    checkServer,
    spawnServer,
    deleteServer,
    waitForInit,
  };
});
