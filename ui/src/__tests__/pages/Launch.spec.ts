import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import { reactive } from 'vue';
import Launch from '@/pages/Launch.vue';

// Mock @jupyterlab/coreutils
vi.mock('@jupyterlab/coreutils', () => ({
  URLExt: {
    normalize: (url: string) => url,
  },
}));

// Mock vue-router
const mockReplace = vi.fn();
const mockRoute: any = {
  params: { context: 'weather', session: '' },
  name: 'launch',
  fullPath: '/launch/weather/',
};
vi.mock('vue-router', () => ({
  useRouter: () => ({
    replace: mockReplace,
    resolve: (to: any) => ({ href: `/session/${to.params?.session || ''}` }),
    currentRoute: { value: mockRoute },
  }),
  useRoute: () => mockRoute,
}));

// Mock fetch utility
const mockFetch = vi.fn();
vi.mock('@/utils/fetch', () => ({
  fetch: (...args: any[]) => mockFetch(...args),
}));

// Mock PrimeVue components
vi.mock('primevue/button', () => ({
  default: {
    name: 'Button',
    template: '<button :id="id" :disabled="disabled" @click="$emit(\'click\', $event)"><slot />{{ label }}</button>',
    props: ['label', 'disabled', 'severity', 'id'],
  },
}));

vi.mock('primevue/progressbar', () => ({
  default: {
    name: 'ProgressBar',
    template: '<div class="mock-progress-bar" :data-value="value"></div>',
    props: ['value', 'id'],
  },
}));

vi.mock('primevue/checkbox', () => ({
  default: {
    name: 'Checkbox',
    template: '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
    props: ['modelValue', 'inputId', 'binary'],
  },
}));

// Mock auth store
const mockUserStore = {
  username: 'testuser',
  refresh: vi.fn(),
};

vi.mock('@/stores/user', () => ({
  useUserStore: () => mockUserStore,
}));

// Mock context store
const mockContextStore = {
  contexts: [
    {
      id: 1,
      slug: 'weather',
      display_name: 'Weather Analysis',
      description: 'Weather analysis tools',
      icon: 'vue://components/icons/WeatherIcon.vue',
      theme: 'weather',
      image: 'weather-image',
      weight: 50,
      enabled: true,
      default_payload: {},
      languages: [],
      integrations: [],
      workflows: [],
      api_keys: [],
    },
    {
      id: 2,
      slug: 'geospatial',
      display_name: 'Geospatial',
      description: 'Geospatial analysis tools',
      icon: 'vue://components/icons/GeospatialIcon.vue',
      theme: 'geospatial',
      image: 'geo-image',
      weight: 60,
      enabled: true,
      default_payload: {},
      languages: [],
      integrations: [],
      workflows: [],
      api_keys: [],
    },
  ],
  nodeImages: {
    'weather-image': {
      id: 1,
      slug: 'weather-image',
      default_registry: 'registry.example.com',
      repository: 'beakerhub/weather-node',
      default_tag: 'latest',
      metadata: {},
      enabled: true,
    },
    'geo-image': {
      id: 2,
      slug: 'geo-image',
      default_registry: 'registry.example.com',
      repository: 'beakerhub/geo-node',
      default_tag: 'latest',
      metadata: {},
      enabled: true,
    },
  },
  ensureContextsLoaded: vi.fn().mockResolvedValue(undefined),
};

vi.mock('@/stores/context', () => ({
  useContextStore: () => mockContextStore,
}));

// Mock session store with reactive servers object
const mockServers = reactive<Record<string, any>>({});
const mockSessionStore = {
  servers: mockServers,
  spawnServer: vi.fn(),
  serverApiUrlBase: '/api/users/testuser/servers/',
};

vi.mock('@/stores/session', () => ({
  useSessionStore: () => mockSessionStore,
}));

function setupSpawnMock(serverName = 'test-session-123', ready = false) {
  mockSessionStore.spawnServer.mockImplementation(async () => {
    const serverData = {
      name: serverName,
      ready,
      stopped: false,
      pending: ready ? null : 'spawn',
      url: `/user/testuser/${serverName}/`,
      progress_url: `/api/users/testuser/servers/${serverName}/progress`,
      started: null,
      last_activity: null,
      state: null,
      user_options: {},
      provisioning: {
        percentage: 0,
        logs: [],
      },
    };
    mockServers[serverName] = serverData;
    return serverData;
  });
}

describe('Launch', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();

    // Reset route params
    mockRoute.params = { context: 'weather', session: '' };
    mockRoute.fullPath = '/launch/weather/';

    // Clear reactive servers
    Object.keys(mockServers).forEach(k => delete mockServers[k]);

    // Setup default spawn mock
    setupSpawnMock();

    // Default mock for fetch - progress stream that ends immediately
    mockFetch.mockResolvedValue({
      ok: true,
      body: {
        getReader: () => ({
          read: vi.fn().mockResolvedValue({ done: true, value: undefined }),
        }),
      },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Rendering', () => {
    it('should render the context display name', async () => {
      const wrapper = mount(Launch);
      await flushPromises();

      expect(wrapper.text()).toContain('Weather Analysis');
    });

    it('should show progress bar', async () => {
      const wrapper = mount(Launch);
      await flushPromises();

      expect(wrapper.find('.mock-progress-bar').exists()).toBe(true);
    });

    it('should show auto-connect checkbox', async () => {
      const wrapper = mount(Launch);
      await flushPromises();

      expect(wrapper.find('input[type="checkbox"]').exists()).toBe(true);
    });
  });

  describe('Spawn Request', () => {
    it('should call ensureContextsLoaded on mount', async () => {
      mount(Launch);
      await flushPromises();

      expect(mockContextStore.ensureContextsLoaded).toHaveBeenCalled();
    });

    it('should call sessionStore.spawnServer with correct config', async () => {
      mount(Launch);
      await flushPromises();

      expect(mockSessionStore.spawnServer).toHaveBeenCalledWith(
        undefined,
        expect.objectContaining({
          contextSlug: 'weather',
          nodeSlug: 'weather-image',
        })
      );
    });

    it('should update route with session ID after spawn', async () => {
      mount(Launch);
      await flushPromises();

      expect(mockReplace).toHaveBeenCalledWith(
        expect.objectContaining({
          params: expect.objectContaining({
            session: 'test-session-123',
          }),
        })
      );
    });
  });

  describe('Message Handling', () => {
    it('should parse and display progress messages', async () => {
      const wrapper = mount(Launch);
      await flushPromises();

      const vm = wrapper.vm as any;
      vm.onMessage(JSON.stringify({ message: 'Starting server...' }));
      await wrapper.vm.$nextTick();

      expect(wrapper.text()).toContain('Starting server...');
    });

    it('should update progress value from message', async () => {
      const wrapper = mount(Launch);
      await flushPromises();

      const vm = wrapper.vm as any;
      vm.onMessage(JSON.stringify({ progress: 50 }));
      await wrapper.vm.$nextTick();

      // Progress is stored on server.provisioning.percentage
      expect(vm.server.provisioning.percentage).toBe(50);
    });

    it('should set server state to ready when message indicates ready', async () => {
      const wrapper = mount(Launch);
      await flushPromises();

      const vm = wrapper.vm as any;
      // Disable auto-connect to prevent navigation side effects
      vm.autoConnect = false;
      vm.onMessage(JSON.stringify({ ready: true, session_id: 'test-session-123' }));
      await wrapper.vm.$nextTick();

      expect(vm.serverState).toBe('ready');
    });

    it('should handle html_message in payload', async () => {
      const wrapper = mount(Launch);
      await flushPromises();

      const vm = wrapper.vm as any;
      vm.onMessage(JSON.stringify({ html_message: '<strong>Progress</strong>' }));
      await wrapper.vm.$nextTick();

      // Messages are stored in server.provisioning.logs via the messages computed
      expect(vm.messages).toContain('<strong>Progress</strong>');
    });
  });

  describe('Computed Properties', () => {
    it('should compute busy as true when server state is launching', async () => {
      const wrapper = mount(Launch);
      await flushPromises();

      const vm = wrapper.vm as any;
      vm.serverState = 'launching';
      await wrapper.vm.$nextTick();

      expect(vm.busy).toBe(true);
    });

    it('should compute busy as true when server state is pending', async () => {
      const wrapper = mount(Launch);
      await flushPromises();

      const vm = wrapper.vm as any;
      vm.serverState = 'pending';
      await wrapper.vm.$nextTick();

      expect(vm.busy).toBe(true);
    });

    it('should compute busy as false when server state is ready', async () => {
      const wrapper = mount(Launch);
      await flushPromises();

      const vm = wrapper.vm as any;
      vm.serverState = 'ready';
      await wrapper.vm.$nextTick();

      expect(vm.busy).toBe(false);
    });

    it('should compute busy as false when server state is failed', async () => {
      const wrapper = mount(Launch);
      await flushPromises();

      const vm = wrapper.vm as any;
      vm.serverState = 'failed';
      await wrapper.vm.$nextTick();

      expect(vm.busy).toBe(false);
    });
  });

  describe('Connect Functionality', () => {
    it('should navigate to session when connect is clicked and server is ready', async () => {
      const wrapper = mount(Launch);
      await flushPromises();

      const vm = wrapper.vm as any;
      // Disable auto-connect to control navigation manually
      vm.autoConnect = false;
      vm.serverState = 'ready';
      await wrapper.vm.$nextTick();

      // Click connect button
      const connectBtn = wrapper.find('#connect-to-server');
      await connectBtn.trigger('click');

      expect(mockReplace).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'session',
          params: expect.objectContaining({ session: 'test-session-123' }),
        })
      );
    });
  });

  describe('Retry Functionality', () => {
    it('should re-trigger spawn on retry', async () => {
      const wrapper = mount(Launch);
      await flushPromises();

      // Clear call counts from initial spawn
      mockSessionStore.spawnServer.mockClear();
      mockFetch.mockClear();
      setupSpawnMock('retry-session');

      mockFetch.mockResolvedValue({
        ok: true,
        body: {
          getReader: () => ({
            read: vi.fn().mockResolvedValue({ done: true, value: undefined }),
          }),
        },
      });

      const vm = wrapper.vm as any;
      vm.serverState = 'failed';
      await wrapper.vm.$nextTick();

      await vm.retry();
      await flushPromises();

      expect(mockSessionStore.spawnServer).toHaveBeenCalled();
    });
  });
});
