import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useContextStore, type Context } from '@/stores/context';

// Mock the fetch utility
vi.mock('@/utils/fetch', () => ({
  fetch: vi.fn(),
}));

import { fetch } from '@/utils/fetch';

const mockFetch = fetch as ReturnType<typeof vi.fn>;

const mockContexts: Record<string, Context> = {
  'data-science': {
    id: 1,
    slug: 'data-science',
    display_name: 'Data Science',
    description: 'Data science tools and analysis',
    icon: 'vue://components/icons/DataScienceIcon.vue',
    theme: 'data-science',
    weight: 100,
    enabled: true,
    default_payload: {},
    languages: [{ slug: 'python', subkernel: 'python3' }],
    integrations: [],
    workflows: [],
    api_keys: [],
  },
  weather: {
    id: 2,
    slug: 'weather',
    display_name: 'Weather Analysis',
    description: 'Weather data processing',
    icon: 'vue://components/icons/WeatherIcon.vue',
    theme: 'weather',
    weight: 50,
    enabled: true,
    default_payload: {},
    languages: [{ slug: 'python', subkernel: 'python3' }],
    integrations: [],
    workflows: [],
    api_keys: [],
  },
};

describe('Context Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initial State', () => {
    it('should have empty contexts initially', () => {
      const store = useContextStore();
      expect(store.contexts).toEqual([]);
    });

    it('should have contextsInitialized as false', () => {
      const store = useContextStore();
      expect(store.contextsInitialized).toBe(false);
    });
  });

  describe('Computed: sortedContexts', () => {
    it('should return contexts sorted by weight descending', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ contexts: mockContexts, nodes: {} }),
      });

      const store = useContextStore();
      await store.fetchContextsDetail();

      const sorted = store.sortedContexts;
      expect(sorted[0].slug).toBe('weather'); // weight: 50
      expect(sorted[1].slug).toBe('data-science'); // weight: 100
    });

    it('should return empty array when no contexts', () => {
      const store = useContextStore();
      expect(store.sortedContexts).toEqual([]);
    });
  });

  describe('Computed: getContextBySlug', () => {
    it('should return context matching slug', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ contexts: mockContexts, nodes: {} }),
      });

      const store = useContextStore();
      await store.fetchContextsDetail();

      const context = store.getContextBySlug('weather');
      expect(context?.display_name).toBe('Weather Analysis');
    });

    it('should return undefined for non-existent slug', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ contexts: mockContexts, nodes: {} }),
      });

      const store = useContextStore();
      await store.fetchContextsDetail();

      const context = store.getContextBySlug('nonexistent');
      expect(context).toBeUndefined();
    });
  });

  describe('Action: fetchContextsDetail', () => {
    it('should fetch and store contexts', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ contexts: mockContexts, nodes: {} }),
      });

      const store = useContextStore();
      await store.fetchContextsDetail();

      expect(store.contexts).toHaveLength(2);
      expect(store.contextsInitialized).toBe(true);
      expect(store.contextsLoading).toBe(false);
    });

    it('should set loading state during fetch', async () => {
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      mockFetch.mockReturnValue(pendingPromise);

      const store = useContextStore();
      const fetchPromise = store.fetchContextsDetail();

      expect(store.contextsLoading).toBe(true);

      resolvePromise!({
        ok: true,
        json: () => Promise.resolve({ contexts: mockContexts, nodes: {} }),
      });

      await fetchPromise;
      expect(store.contextsLoading).toBe(false);
    });

    it('should set error on failed fetch', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: 'Internal Server Error',
      });

      const store = useContextStore();

      await expect(store.fetchContextsDetail()).rejects.toThrow();
      expect(store.contextsError).toContain('Failed to fetch contexts');
    });

    it('should handle network errors', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const store = useContextStore();

      await expect(store.fetchContextsDetail()).rejects.toThrow('Network error');
      expect(store.contextsError).toBe('Network error');
    });
  });

  describe('Action: ensureContextsLoaded', () => {
    it('should fetch contexts if not initialized', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ contexts: mockContexts, nodes: {} }),
      });

      const store = useContextStore();
      await store.ensureContextsLoaded();

      expect(mockFetch).toHaveBeenCalledTimes(1);
      expect(store.contextsInitialized).toBe(true);
    });

    it('should not fetch if already initialized', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ contexts: mockContexts, nodes: {} }),
      });

      const store = useContextStore();
      await store.fetchContextsDetail();

      vi.clearAllMocks();

      await store.ensureContextsLoaded();
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('should not fetch if already loading', async () => {
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      mockFetch.mockReturnValue(pendingPromise);

      const store = useContextStore();

      // Start first fetch
      store.fetchContextsDetail();

      // Try to ensure loaded while still loading
      await store.ensureContextsLoaded();

      // Should only have one fetch call
      expect(mockFetch).toHaveBeenCalledTimes(1);

      resolvePromise!({
        ok: true,
        json: () => Promise.resolve({ contexts: mockContexts, nodes: {} }),
      });
    });
  });
});
