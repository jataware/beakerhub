import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import { ref, computed } from 'vue';
import UserMenuButton from '@/components/UserMenuButton.vue';

// Mock vue-router
const mockPush = vi.fn();
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

// Mock PrimeVue components
vi.mock('primevue/button', () => ({
  default: {
    name: 'Button',
    template: '<button @click="$emit(\'click\', $event)"><slot /></button>',
    props: ['text', 'size', 'title'],
  },
}));

vi.mock('primevue/menu', () => ({
  default: {
    name: 'Menu',
    template: '<div class="mock-menu"><slot /></div>',
    props: ['model', 'popup'],
    methods: {
      toggle: vi.fn(),
    },
  },
}));

// Mock the auth store
const mockUserStore = {
  isLoggedIn: false,
  username: '',
  isAdmin: false,
  logout: vi.fn(),
};

vi.mock('@/stores/user', () => ({
  useUserStore: () => mockUserStore,
}));

describe('UserMenuButton', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();

    // Reset mock auth store state
    mockUserStore.isLoggedIn = false;
    mockUserStore.username = '';
    mockUserStore.isAdmin = false;
    mockUserStore.logout.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Menu Items - Not Logged In', () => {
    it('should show login and signup options when not logged in', () => {
      mockUserStore.isLoggedIn = false;

      const wrapper = mount(UserMenuButton);

      // Access the computed userMenuItems
      const vm = wrapper.vm as any;
      const menuItems = vm.userMenuItems;

      expect(menuItems).toHaveLength(2);
      expect(menuItems[0].label).toBe('Login');
      expect(menuItems[1].label).toBe('Sign up');
    });

    it('should navigate to login when login clicked', async () => {
      mockUserStore.isLoggedIn = false;

      const wrapper = mount(UserMenuButton);
      const vm = wrapper.vm as any;
      const menuItems = vm.userMenuItems;

      // Execute the login command
      menuItems[0].command();

      expect(mockPush).toHaveBeenCalledWith({name: 'login'});
    });

    it('should navigate to signup when signup clicked', async () => {
      mockUserStore.isLoggedIn = false;

      const wrapper = mount(UserMenuButton);
      const vm = wrapper.vm as any;
      const menuItems = vm.userMenuItems;

      // Execute the signup command
      menuItems[1].command();

      expect(mockPush).toHaveBeenCalledWith({name: 'signup'});
    });
  });

  describe('Menu Items - Logged In', () => {
    it('should show username and logout options when logged in', () => {
      mockUserStore.isLoggedIn = true;
      mockUserStore.username = 'testuser@example.com';

      const wrapper = mount(UserMenuButton);
      const vm = wrapper.vm as any;
      const menuItems = vm.userMenuItems;

      expect(menuItems).toHaveLength(2);
      expect(menuItems[0].label).toBe('testuser@example.com');
      expect(menuItems[0].disabled).toBe(true);
      expect(menuItems[1].label).toBe('Logout');
    });

    it('should show admin option when user is admin', () => {
      mockUserStore.isLoggedIn = true;
      mockUserStore.username = 'admin@example.com';
      mockUserStore.isAdmin = true;

      const wrapper = mount(UserMenuButton);
      const vm = wrapper.vm as any;
      const menuItems = vm.userMenuItems;

      expect(menuItems).toHaveLength(3);
      // Admin is spliced at index 1, between username and Logout
      expect(menuItems[1].label).toBe('Admin');
    });

    it('should call logout and navigate to login on logout click', async () => {
      mockUserStore.isLoggedIn = true;
      mockUserStore.username = 'testuser@example.com';

      const wrapper = mount(UserMenuButton);
      const vm = wrapper.vm as any;
      const menuItems = vm.userMenuItems;

      // Execute the logout command
      await menuItems[1].command();

      expect(mockPush).toHaveBeenCalledWith({ name: 'logout', force: true });
    });
  });

  describe('Rendering', () => {
    it('should render a button with user icon', () => {
      const wrapper = mount(UserMenuButton);

      const button = wrapper.find('button');
      expect(button.exists()).toBe(true);

      const icon = wrapper.find('i.pi-user');
      expect(icon.exists()).toBe(true);
    });
  });
});
