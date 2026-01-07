import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import Dashboard from '@/pages/Dashboard.vue';

// Mock vue-router
const mockPush = vi.fn();
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

// Mock PrimeVue components
vi.mock('primevue/card', () => ({
  default: {
    name: 'Card',
    template: '<div class="mock-card" @click="$emit(\'click\', $event)"><slot name="header" /><slot name="content" /></div>',
    props: ['class'],
  },
}));

vi.mock('primevue/button', () => ({
  default: {
    name: 'Button',
    template: '<button @click="$emit(\'click\', $event)"><slot /></button>',
    props: ['text', 'size'],
  },
}));

vi.mock('primevue/tag', () => ({
  default: {
    name: 'Tag',
    template: '<span class="mock-tag">{{ value }}</span>',
    props: ['value', 'size', 'severity'],
  },
}));

vi.mock('primevue/dialog', () => ({
  default: {
    name: 'Dialog',
    template: '<div v-if="visible" class="mock-dialog"><slot /></div>',
    props: ['visible', 'modal', 'header', 'style', 'closable'],
    emits: ['update:visible'],
  },
}));

vi.mock('primevue/datatable', () => ({
  default: {
    name: 'DataTable',
    template: '<div class="mock-datatable"><slot name="empty" /><slot /></div>',
    props: ['value', 'tableStyle'],
  },
}));

vi.mock('primevue/column', () => ({
  default: {
    name: 'Column',
    template: '<div class="mock-column"><slot name="body" :data="{}" /></div>',
    props: ['header', 'field'],
  },
}));

vi.mock('primevue/confirmdialog', () => ({
  default: {
    name: 'ConfirmDialog',
    template: '<div class="mock-confirm-dialog"></div>',
  },
}));

const mockConfirm = {
  require: vi.fn(),
};

vi.mock('primevue/useconfirm', () => ({
  useConfirm: () => mockConfirm,
}));

// Mock icon components
vi.mock('@/components/icons/DataScienceIcon.vue', () => ({
  default: { template: '<span class="data-science-icon">DS</span>' },
}));

vi.mock('@/components/icons/BiomedicalIcon.vue', () => ({
  default: { template: '<span class="biomedical-icon">BIO</span>' },
}));

vi.mock('@/components/icons/WeatherIcon.vue', () => ({
  default: { template: '<span class="weather-icon">WX</span>' },
}));

vi.mock('@/components/icons/GeospatialIcon.vue', () => ({
  default: { template: '<span class="geospatial-icon">GEO</span>' },
}));

vi.mock('@/components/icons/WildfireIcon.vue', () => ({
  default: { template: '<span class="wildfire-icon">FIRE</span>' },
}));

vi.mock('@/components/icons/CustomDomainIcon.vue', () => ({
  default: { template: '<span class="custom-domain-icon">CUSTOM</span>' },
}));

// Mock stores
const mockContextStore = {
  contextsLoading: false,
  contextsError: null as string | null,
  sortedEnabledContexts: [] as any[],
  contexts: [] as any[],
  ensureContextsLoaded: vi.fn(),
};

const mockUserStore = {
  username: 'testuser',
};

const mockSessionStore = {
  servers: {} as Record<string, any>,
  deleteServer: vi.fn(),
};

vi.mock('@/stores/context', () => ({
  useContextStore: () => mockContextStore,
  getVueIconComponent: (iconUrl: string | undefined | null) => {
    if (!iconUrl || !iconUrl.startsWith('vue://')) return undefined;
    const match = iconUrl.match(/([^/]+)\.vue$/);
    return match ? match[1] : undefined;
  },
}));

vi.mock('@/stores/user', () => ({
  useUserStore: () => mockUserStore,
}));

vi.mock('@/stores/session', () => ({
  useSessionStore: () => mockSessionStore,
}));

describe('Dashboard', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    mockContextStore.contextsLoading = false;
    mockContextStore.contextsError = null;
    mockContextStore.sortedEnabledContexts = [];
    mockContextStore.contexts = [];
    mockSessionStore.servers = {};
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Loading State', () => {
    it('should show loading indicator when contexts are loading', () => {
      mockContextStore.contextsLoading = true;

      const wrapper = mount(Dashboard);

      expect(wrapper.text()).toContain('Loading contexts...');
      expect(wrapper.find('.pi-spinner').exists()).toBe(true);
    });

    it('should not show loading indicator when contexts are loaded', () => {
      mockContextStore.contextsLoading = false;

      const wrapper = mount(Dashboard);

      expect(wrapper.text()).not.toContain('Loading contexts...');
    });
  });

  describe('Error State', () => {
    it('should show error message when contexts fail to load', () => {
      mockContextStore.contextsError = 'Failed to fetch contexts';

      const wrapper = mount(Dashboard);

      expect(wrapper.text()).toContain('Failed to fetch contexts');
      expect(wrapper.find('.pi-exclamation-triangle').exists()).toBe(true);
    });

    it('should show retry button when error occurs', () => {
      mockContextStore.contextsError = 'Network error';

      const wrapper = mount(Dashboard);

      const retryButton = wrapper.findAll('button').find(b => b.text().includes('Retry'));
      expect(retryButton).toBeDefined();
    });
  });

  describe('Context Cards', () => {
    const mockContexts = [
      {
        slug: 'data-science-context',
        display_name: 'Data Science',
        description: 'A powerful context for data analysis. It includes many features.',
        workflows: [{ title: 'Analysis' }, { title: 'Visualization' }],
        integrations: [{ name: 'pandas' }, { name: 'numpy' }],
      },
      {
        slug: 'biomedical-research',
        display_name: 'Biomedical Research',
        description: 'Research tools for biomedical sciences!',
        workflows: [],
        integrations: [{ name: 'biopython' }],
      },
      {
        slug: 'weather-forecast',
        display_name: 'Weather Forecasting',
        description: 'Weather analysis tools?',
        workflows: [{ title: 'Forecast' }],
        integrations: [],
      },
    ];

    beforeEach(() => {
      mockContextStore.sortedEnabledContexts = mockContexts;
    });

    it('should render cards for each context', () => {
      const wrapper = mount(Dashboard);

      expect(wrapper.text()).toContain('Data Science');
      expect(wrapper.text()).toContain('Biomedical Research');
      expect(wrapper.text()).toContain('Weather Forecasting');
    });

    it('should show first sentence of description', () => {
      const wrapper = mount(Dashboard);

      // Should show first sentence only
      expect(wrapper.text()).toContain('A powerful context for data analysis.');
      expect(wrapper.text()).not.toContain('It includes many features.');
    });
  });

  describe('Helper Functions', () => {
    // Helper to create minimal context objects for testing
    const makeContext = (slug: string, theme?: string) => ({
      slug,
      theme: theme || '',
      display_name: 'Test',
      description: 'Test.',
      workflows: [],
      integrations: [],
      icon: '',
    });

    it('getContextCardClass should return card class based on theme', async () => {
      const wrapper = mount(Dashboard);
      const vm = wrapper.vm as any;

      expect(vm.getContextCardClass(makeContext('test', 'data-science'))).toBe('data-science-card');
      expect(vm.getContextCardClass(makeContext('test', 'biomedical'))).toBe('biomedical-card');
      expect(vm.getContextCardClass(makeContext('test', 'weather'))).toBe('weather-card');
    });

    it('getContextCardClass should fallback to slug inference when no theme', async () => {
      const wrapper = mount(Dashboard);
      const vm = wrapper.vm as any;

      expect(vm.getContextCardClass(makeContext('data-science'))).toBe('data-science-card');
      expect(vm.getContextCardClass(makeContext('default'))).toBe('data-science-card');
      expect(vm.getContextCardClass(makeContext('biomedical'))).toBe('biomedical-card');
      expect(vm.getContextCardClass(makeContext('weather'))).toBe('weather-card');
      expect(vm.getContextCardClass(makeContext('aviation'))).toBe('weather-card');
    });

    it('getContextTheme should return theme from context', async () => {
      const wrapper = mount(Dashboard);
      const vm = wrapper.vm as any;

      expect(vm.getContextTheme(makeContext('test', 'data-science'))).toBe('data-science');
      expect(vm.getContextTheme(makeContext('test', 'biomedical'))).toBe('biomedical');
      expect(vm.getContextTheme(makeContext('test', 'weather'))).toBe('weather');
    });

    it('getContextTheme should fallback to slug inference when no theme', async () => {
      const wrapper = mount(Dashboard);
      const vm = wrapper.vm as any;

      expect(vm.getContextTheme(makeContext('data-science'))).toBe('data-science');
      expect(vm.getContextTheme(makeContext('biomedical'))).toBe('biomedical');
      expect(vm.getContextTheme(makeContext('weather'))).toBe('weather');
      expect(vm.getContextTheme(makeContext('unknown'))).toBe('data-science');
    });

    it('getFirstSentence should extract first sentence ending with period', async () => {
      const wrapper = mount(Dashboard);
      const vm = wrapper.vm as any;

      expect(vm.getFirstSentence('First sentence. Second sentence.')).toBe('First sentence.');
    });

    it('getFirstSentence should extract first sentence ending with exclamation', async () => {
      const wrapper = mount(Dashboard);
      const vm = wrapper.vm as any;

      expect(vm.getFirstSentence('Exciting! More text.')).toBe('Exciting!');
    });

    it('getFirstSentence should extract first sentence ending with question mark', async () => {
      const wrapper = mount(Dashboard);
      const vm = wrapper.vm as any;

      expect(vm.getFirstSentence('Is this working? Yes.')).toBe('Is this working?');
    });

    it('getFirstSentence should return full text if no sentence ending found', async () => {
      const wrapper = mount(Dashboard);
      const vm = wrapper.vm as any;

      expect(vm.getFirstSentence('No punctuation here')).toBe('No punctuation here');
    });
  });

  describe('Domain Details Dialog', () => {
    const mockContext = {
      slug: 'test-context',
      display_name: 'Test Context',
      description: 'A test context description.',
      workflows: [{ title: 'Workflow 1' }, { title: 'Workflow 2' }],
      integrations: [{ name: 'Integration 1' }],
    };

    beforeEach(() => {
      mockContextStore.sortedEnabledContexts = [mockContext];
    });

    it('showDomainDetails should set selectedDomainDetails with context data', async () => {
      const wrapper = mount(Dashboard);
      const vm = wrapper.vm as any;

      vm.showDomainDetails('test-context');

      expect(vm.selectedDomainDetails).toEqual({
        title: 'Test Context',
        slug: 'test-context',
        description: 'A test context description.',
        workflows: ['Workflow 1', 'Workflow 2'],
        integrations: ['Integration 1'],
        tools: [],
        languages: [],
      });
      expect(vm.detailsDialogVisible).toBe(true);
    });

    it('showDomainDetails should not set details for unknown context', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const wrapper = mount(Dashboard);
      const vm = wrapper.vm as any;

      vm.showDomainDetails('unknown-context');

      expect(vm.selectedDomainDetails).toBeNull();
      expect(vm.detailsDialogVisible).toBe(false);
      expect(consoleSpy).toHaveBeenCalledWith('context not found:', 'unknown-context');

      consoleSpy.mockRestore();
    });
  });

  describe('Create Environment', () => {
    it('createEnvironment should navigate to launch page with context slug', async () => {
      const wrapper = mount(Dashboard);
      const vm = wrapper.vm as any;

      vm.createEnvironment('test-context');

      expect(mockPush).toHaveBeenCalledWith({
        name: 'launch',
        params: { context: 'test-context' },
      });
    });
  });

  describe('Display Items', () => {
    it('should show empty message for context with no workflows or integrations', () => {
      mockContextStore.sortedEnabledContexts = [
        {
          slug: 'empty-context',
          display_name: 'Empty',
          description: 'Empty context.',
          workflows: [],
          integrations: [],
        },
      ];

      const wrapper = mount(Dashboard);

      expect(wrapper.text()).toContain('Default. No workflows or integrations.');
    });

    it('should show workflows and integrations when both exist', () => {
      mockContextStore.sortedEnabledContexts = [
        {
          slug: 'full-context',
          display_name: 'Full',
          description: 'Full context.',
          workflows: [{ title: 'WF1' }, { title: 'WF2' }, { title: 'WF3' }],
          integrations: [{ name: 'INT1' }, { name: 'INT2' }, { name: 'INT3' }],
        },
      ];

      const wrapper = mount(Dashboard);

      expect(wrapper.text()).toContain('Workflows:');
      expect(wrapper.text()).toContain('Integrations:');
    });

    it('should show "more" indicator when there are extra items', () => {
      mockContextStore.sortedEnabledContexts = [
        {
          slug: 'many-items',
          display_name: 'Many',
          description: 'Many items.',
          workflows: [
            { title: 'W1' }, { title: 'W2' }, { title: 'W3' },
            { title: 'W4' }, { title: 'W5' },
          ],
          integrations: [
            { name: 'I1' }, { name: 'I2' }, { name: 'I3' },
            { name: 'I4' }, { name: 'I5' },
          ],
        },
      ];

      const wrapper = mount(Dashboard);

      // Should show "+X more" tags
      expect(wrapper.text()).toContain('+');
      expect(wrapper.text()).toContain('more');
    });
  });
});
