import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { mount, config } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import Header from '@/components/Header.vue';

// Mock vue-router
const mockPush = vi.fn();
const mockCurrentRoute = { value: { name: 'dashboard' } };
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
    currentRoute: mockCurrentRoute,
  }),
}));

// Mock PrimeVue components
vi.mock('primevue/button', () => ({
  default: {
    name: 'Button',
    template: '<button :class="$attrs.class" @click="$emit(\'click\', $event)"><slot /></button>',
    props: ['text', 'size', 'title'],
  },
}));

vi.mock('primevue/menu', () => ({
  default: {
    name: 'Menu',
    template: '<div class="mock-menu"></div>',
    props: ['model', 'popup'],
  },
}));

// Mock child components
vi.mock('@/components/HeaderLogo.vue', () => ({
  default: {
    name: 'HeaderLogo',
    template: '<div class="mock-header-logo">Logo</div>',
    props: ['size'],
  },
}));

vi.mock('@/components/UserMenuButton.vue', () => ({
  default: {
    name: 'UserMenuButton',
    template: '<div class="mock-user-menu">User Menu</div>',
  },
}));

// Mock the auth store
const mockUserStore = {
  isLoggedIn: false,
  logout: vi.fn(),
};

vi.mock('@/stores/user', () => ({
  useUserStore: () => mockUserStore,
}));

describe('Header', () => {
  let localStorageMock: { getItem: ReturnType<typeof vi.fn>; setItem: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    mockCurrentRoute.value = { name: 'dashboard' };

    // Reset localStorage mock
    localStorageMock = {
      getItem: vi.fn().mockReturnValue(null),
      setItem: vi.fn(),
    };
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock,
      writable: true,
    });

    // Reset document.documentElement
    document.documentElement.classList.remove('beaker-dark');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Rendering', () => {
    it('should render with default props', () => {
      const wrapper = mount(Header);

      expect(wrapper.find('.header-container').exists()).toBe(true);
      expect(wrapper.find('.mock-header-logo').exists()).toBe(true);
      expect(wrapper.find('.mock-user-menu').exists()).toBe(true);
    });

    it('should apply sticky class when sticky prop is true', () => {
      const wrapper = mount(Header, {
        props: { sticky: true },
      });

      expect(wrapper.find('.header-container.sticky').exists()).toBe(true);
    });

    it('should not apply sticky class when sticky prop is false', () => {
      const wrapper = mount(Header, {
        props: { sticky: false },
      });

      expect(wrapper.find('.header-container.sticky').exists()).toBe(false);
    });
  });

  describe('Dark Mode Toggle', () => {
    it('should show moon icon when in light mode', () => {
      localStorageMock.getItem.mockReturnValue(null);

      const wrapper = mount(Header);

      expect(wrapper.find('i.pi-moon').exists()).toBe(true);
    });

    it('should show sun icon when in dark mode', () => {
      localStorageMock.getItem.mockReturnValue('dark');

      const wrapper = mount(Header);

      expect(wrapper.find('i.pi-sun').exists()).toBe(true);
    });

    it('should call localStorage.setItem when toggling dark mode', async () => {
      localStorageMock.getItem.mockReturnValue(null);

      const wrapper = mount(Header);

      // Find the dark mode toggle button (the one with pi-moon or pi-sun)
      const buttons = wrapper.findAll('button');
      const darkModeButton = buttons.find(
        (b) => b.find('i.pi-moon').exists() || b.find('i.pi-sun').exists()
      );

      expect(darkModeButton).toBeDefined();
      await darkModeButton!.trigger('click');

      // Verify localStorage was called to save the preference
      expect(localStorageMock.setItem).toHaveBeenCalledWith('theme-lightmode', 'dark');
    });

  });

  describe('Logo Navigation', () => {
    it('should navigate to home when logo clicked and not on home page', async () => {
      mockCurrentRoute.value = { name: 'dashboard' };

      const wrapper = mount(Header);

      // Find the first button in header-icon (the logo button)
      const logoButton = wrapper.find('.header-icon button');
      expect(logoButton.exists()).toBe(true);
      await logoButton.trigger('click');

      expect(mockPush).toHaveBeenCalledWith({ name: 'home' });
    });

    it('should not navigate when already on home page', async () => {
      mockCurrentRoute.value = { name: 'home' };

      const wrapper = mount(Header);

      const logoButton = wrapper.find('.header-icon button');
      await logoButton.trigger('click');

      // Should not push when already on home
      expect(mockPush).not.toHaveBeenCalled();
    });
  });
});
