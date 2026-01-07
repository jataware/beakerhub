import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useUserStore } from '@/stores/user';

// Mock the fetch utility
vi.mock('@/utils/fetch', () => ({
  fetch: vi.fn(),
}));

// Mock the session store
vi.mock('@/stores/session', () => ({
  useSessionStore: () => ({
    setServersFromUserApi: vi.fn(),
  }),
}));

import { fetch } from '@/utils/fetch';

const mockFetch = fetch as ReturnType<typeof vi.fn>;

describe('User Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();

    // Default mock: return failed auth (not logged in)
    mockFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({}),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initial State', () => {
    it('should have undefined username initially', () => {
      const store = useUserStore();
      // Note: refresh() is called on store creation, so we need to wait
      expect(store.username).toBeUndefined();
    });

    it('should have loading set to false after initialization', async () => {
      const store = useUserStore();
      // Wait for the initial refresh to complete
      await store.waitForInit();
      expect(store.loading).toBe(false);
    });

    it('should set initialized to true after refresh', async () => {
      const store = useUserStore();
      await store.waitForInit();
      expect(store.initialized).toBe(true);
    });
  });

  describe('Computed: isLoggedIn', () => {
    it('should return false when username is undefined', async () => {
      const store = useUserStore();
      await store.waitForInit();
      expect(store.isLoggedIn).toBe(false);
    });

    it('should return true when username is defined', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            name: 'testuser',
            roles: ['user'],
            groups: [],
            admin: false,
            servers: {},
          }),
      });

      const store = useUserStore();
      await store.waitForInit();
      expect(store.isLoggedIn).toBe(true);
    });
  });

  describe('Computed: displayName', () => {
    it('should return empty string when not logged in', async () => {
      const store = useUserStore();
      await store.waitForInit();
      expect(store.displayName).toBe('');
    });

    it('should return username when logged in', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            name: 'john@example.com',
            roles: ['user'],
            groups: [],
            admin: false,
            servers: {},
          }),
      });

      const store = useUserStore();
      await store.waitForInit();
      expect(store.displayName).toBe('john@example.com');
    });
  });

  describe('Action: refresh', () => {
    it('should populate user data on successful refresh', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            name: 'testuser',
            roles: ['user', 'admin'],
            groups: ['scientists'],
            admin: true,
            servers: { default: { name: 'default', ready: true } },
          }),
      });

      const store = useUserStore();
      await store.waitForInit();

      expect(store.username).toBe('testuser');
      expect(store.roles).toEqual(['user', 'admin']);
      expect(store.groups).toEqual(['scientists']);
      expect(store.isAdmin).toBe(true);
      expect(store.servers).toEqual({ default: { name: 'default', ready: true } });
    });

    it('should clear user data on failed refresh', async () => {
      // First, set up logged in state
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            name: 'testuser',
            roles: ['user'],
            groups: [],
            admin: false,
            servers: {},
          }),
      });

      const store = useUserStore();
      await store.waitForInit();
      expect(store.username).toBe('testuser');

      // Now simulate failed refresh
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({}),
      });

      await store.refresh();

      expect(store.username).toBeUndefined();
      expect(store.roles).toEqual([]);
      expect(store.groups).toEqual([]);
      expect(store.isAdmin).toBe(false);
    });

    it('should set loading state during refresh', async () => {
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      mockFetch.mockReturnValue(pendingPromise);

      const store = useUserStore();

      // Loading should be true while request is pending
      expect(store.loading).toBe(true);

      resolvePromise!({
        ok: true,
        json: () => Promise.resolve({ name: 'test', roles: [], groups: [], admin: false, servers: {} }),
      });

      await store.waitForInit();
      expect(store.loading).toBe(false);
    });
  });

  describe('Action: login', () => {
    it('should return success and update state on successful login', async () => {
      // Initial state (not logged in)
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({}),
      });

      const store = useUserStore();
      await store.waitForInit();

      // Login request
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            name: 'user@example.com',
            roles: ['user'],
            groups: [],
            admin: false,
          }),
      });

      const result = await store.login('user@example.com', 'password123');

      expect(result.success).toBe(true);
      expect(store.username).toBe('user@example.com');
      expect(mockFetch).toHaveBeenCalledWith('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username: 'user@example.com', password: 'password123' }),
        headers: { 'Content-Type': 'application/json' },
      });
    });

    it('should return error on failed login', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({}),
      });

      const store = useUserStore();
      await store.waitForInit();

      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ message: 'Invalid credentials' }),
      });

      const result = await store.login('user@example.com', 'wrong');

      expect(result.success).toBe(false);
      expect(result.error).toBe('Invalid credentials');
    });

    it('should handle network errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({}),
      });

      const store = useUserStore();
      await store.waitForInit();

      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const result = await store.login('user@example.com', 'password');

      expect(result.success).toBe(false);
      expect(result.error).toBe('network error');
    });
  });

  describe('Action: logout', () => {
    it('should clear user state on logout', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            name: 'testuser',
            roles: ['user'],
            groups: ['team'],
            admin: false,
            servers: {},
          }),
      });

      const store = useUserStore();
      await store.waitForInit();
      expect(store.username).toBe('testuser');

      mockFetch.mockResolvedValueOnce({ ok: true });

      await store.logout();

      expect(store.username).toBeUndefined();
      expect(store.isLoggedIn).toBe(false);
    });

    it('should call logout API', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({}),
      });

      const store = useUserStore();
      await store.waitForInit();

      mockFetch.mockResolvedValueOnce({ ok: true });

      await store.logout();

      expect(mockFetch).toHaveBeenCalledWith('/api/auth/logout', expect.objectContaining({
        method: 'POST',
      }));
    });
  });

  describe('Action: signup', () => {
    it('should call signup API with correct data', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({}),
      });

      const store = useUserStore();
      await store.waitForInit();

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ user: { username: 'new-uuid' } }),
      });

      const result = await store.signup('new@example.com', 'SecurePass123!', 'Acme Corp');

      expect(result.success).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith('/api/auth/signup', {
        method: 'POST',
        body: JSON.stringify({
          username: 'new@example.com',
          password: 'SecurePass123!',
          organization: 'Acme Corp',
        }),
        headers: { 'Content-Type': 'application/json' },
      });
    });
  });

  describe('Action: confirmSignup', () => {
    it('should call confirmation API with correct data', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({}),
      });

      const store = useUserStore();
      await store.waitForInit();

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ confirmed: true }),
      });

      const result = await store.confirmSignup('user@example.com', '123456');

      expect(result.success).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith('/api/auth/signup-confirmation', {
        method: 'POST',
        body: JSON.stringify({ username: 'user@example.com', code: '123456' }),
        headers: { 'Content-Type': 'application/json' },
      });
    });
  });

  describe('Action: forgotPassword', () => {
    it('should call forgot password API', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({}),
      });

      const store = useUserStore();
      await store.waitForInit();

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ sent: true }),
      });

      const result = await store.forgotPassword('user@example.com');

      expect(result.success).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith('/api/auth/password-forgot', {
        method: 'POST',
        body: JSON.stringify({ username: 'user@example.com' }),
        headers: { 'Content-Type': 'application/json' },
      });
    });
  });

  describe('Action: confirmPassword', () => {
    it('should call confirm password API with correct data', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({}),
      });

      const store = useUserStore();
      await store.waitForInit();

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ reset: true }),
      });

      const result = await store.confirmPassword('user@example.com', '654321', 'NewSecurePass!');

      expect(result.success).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith('/api/auth/password-confirm', {
        method: 'POST',
        body: JSON.stringify({
          username: 'user@example.com',
          code: '654321',
          password: 'NewSecurePass!',
        }),
        headers: { 'Content-Type': 'application/json' },
      });
    });
  });

  describe('Action: isSessionValid', () => {
    it('should return false when not logged in', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({}),
      });

      const store = useUserStore();
      await store.waitForInit();

      const result = await store.isSessionValid();

      expect(result).toBe(false);
    });

    it('should check session validity with HEAD request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            name: 'testuser',
            roles: [],
            groups: [],
            admin: false,
            servers: {},
          }),
      });

      const store = useUserStore();
      await store.waitForInit();

      mockFetch.mockResolvedValueOnce({ ok: true });

      const result = await store.isSessionValid();

      expect(result).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith('/api/user?user=testuser', { method: 'HEAD' });
    });
  });

  describe('Action: prepareLogin', () => {
    it('should call login GET endpoint', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({}),
      });

      const store = useUserStore();
      await store.waitForInit();

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ status: 'proceed' }),
      });

      const result = await store.prepareLogin();

      expect(result.success).toBe(true);
      expect(result.status).toBe('proceed');
      expect(mockFetch).toHaveBeenCalledWith('/api/auth/login', { method: 'GET' });
    });
  });
});
