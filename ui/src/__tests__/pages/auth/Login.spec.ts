import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import Login from '@/pages/auth/Login.vue';

// Mock vue-router
const mockPush = vi.fn();
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useRoute: () => ({
    params: {},
    query: {},
  }),
  RouterLink: {
    name: 'RouterLink',
    template: '<a :href="to"><slot /></a>',
    props: ['to'],
  },
}));

// Mock PrimeVue components
vi.mock('primevue/card', () => ({
  default: {
    name: 'Card',
    template: '<div class="mock-card"><slot /><slot name="content" /></div>',
  },
}));

vi.mock('primevue/inputtext', () => ({
  default: {
    name: 'InputText',
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    props: ['modelValue', 'type', 'placeholder', 'required'],
    emits: ['update:modelValue'],
  },
}));

vi.mock('primevue/password', () => ({
  default: {
    name: 'Password',
    template: '<input type="password" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    props: ['modelValue', 'placeholder', 'feedback', 'toggleMask', 'required'],
    emits: ['update:modelValue'],
  },
}));

vi.mock('primevue/button', () => ({
  default: {
    name: 'Button',
    template: '<button :disabled="disabled" :type="type" @click="$emit(\'click\', $event)"><slot /></button>',
    props: ['type', 'disabled', 'loading', 'size'],
  },
}));

vi.mock('primevue/message', () => ({
  default: {
    name: 'Message',
    template: '<div class="mock-message"><slot /></div>',
    props: ['severity', 'closable'],
  },
}));

vi.mock('primevue/divider', () => ({
  default: {
    name: 'Divider',
    template: '<hr />',
  },
}));

vi.mock('@/components/BeakerHubLogo.vue', () => ({
  default: {
    name: 'BeakerHubLogo',
    template: '<div class="mock-logo"></div>',
  },
}));

// Mock the auth store
const mockUserStore = {
  login: vi.fn(),
};

vi.mock('@/stores/user', () => ({
  useUserStore: () => mockUserStore,
}));

describe('Login', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    mockUserStore.login.mockResolvedValue({ success: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Form Validation', () => {
    it('should disable submit button when email is empty', async () => {
      const wrapper = mount(Login);

      // Set only password
      const passwordInput = wrapper.find('input[type="password"]');
      await passwordInput.setValue('password123');

      const submitButton = wrapper.find('button[type="submit"]');
      expect(submitButton.attributes('disabled')).toBeDefined();
    });

    it('should disable submit button when password is empty', async () => {
      const wrapper = mount(Login);

      // Set only email
      const inputs = wrapper.findAll('input');
      const emailInput = inputs[0];
      await emailInput.setValue('test@example.com');

      const submitButton = wrapper.find('button[type="submit"]');
      expect(submitButton.attributes('disabled')).toBeDefined();
    });

    it('should enable submit button when both email and password are provided', async () => {
      const wrapper = mount(Login);

      const inputs = wrapper.findAll('input');
      await inputs[0].setValue('test@example.com');
      await inputs[1].setValue('password123');

      const submitButton = wrapper.find('button[type="submit"]');
      expect(submitButton.attributes('disabled')).toBeUndefined();
    });
  });

  describe('Form Submission', () => {
    it('should call userStore.login with email and password on submit', async () => {
      const wrapper = mount(Login);

      const inputs = wrapper.findAll('input');
      await inputs[0].setValue('test@example.com');
      await inputs[1].setValue('password123');

      const form = wrapper.find('form');
      await form.trigger('submit');
      await flushPromises();

      expect(mockUserStore.login).toHaveBeenCalledWith('test@example.com', 'password123');
    });

    it('should navigate to home on successful login', async () => {
      mockUserStore.login.mockResolvedValue({ success: true });

      const wrapper = mount(Login);

      const inputs = wrapper.findAll('input');
      await inputs[0].setValue('test@example.com');
      await inputs[1].setValue('password123');

      const form = wrapper.find('form');
      await form.trigger('submit');
      await flushPromises();

      expect(mockPush).toHaveBeenCalledWith({ name: 'home' });
    });

    it('should display error message on failed login', async () => {
      mockUserStore.login.mockResolvedValue({ success: false, error: 'Invalid credentials' });

      const wrapper = mount(Login);

      const inputs = wrapper.findAll('input');
      await inputs[0].setValue('test@example.com');
      await inputs[1].setValue('wrongpassword');

      const form = wrapper.find('form');
      await form.trigger('submit');
      await flushPromises();

      expect(wrapper.text()).toContain('Invalid credentials');
      expect(mockPush).not.toHaveBeenCalled();
    });

    it('should display generic error message on exception', async () => {
      mockUserStore.login.mockRejectedValue(new Error('Network error'));

      const wrapper = mount(Login);

      const inputs = wrapper.findAll('input');
      await inputs[0].setValue('test@example.com');
      await inputs[1].setValue('password123');

      const form = wrapper.find('form');
      await form.trigger('submit');
      await flushPromises();

      expect(wrapper.text()).toContain('login failed');
    });

    it('should not submit when form is invalid', async () => {
      const wrapper = mount(Login);

      // Don't fill in the form
      const form = wrapper.find('form');
      await form.trigger('submit');
      await flushPromises();

      expect(mockUserStore.login).not.toHaveBeenCalled();
    });
  });

  describe('Navigation Links', () => {
    it('should have link to signup page', () => {
      const wrapper = mount(Login);

      const signupLink = wrapper.findAll('a').find(a => a.text().includes('Sign Up'));
      expect(signupLink).toBeDefined();
    });

    it('should have link to reset password page', () => {
      const wrapper = mount(Login);

      const resetLink = wrapper.findAll('a').find(a => a.text().includes('Forgot'));
      expect(resetLink).toBeDefined();
    });

    it('should have link back to home page', () => {
      const wrapper = mount(Login);

      const homeLink = wrapper.findAll('a').find(a => a.text().includes('Back to Site'));
      expect(homeLink).toBeDefined();
    });
  });

  describe('Loading State', () => {
    it('should show loading text while submitting', async () => {
      // Create a promise that we can resolve manually
      let resolveLogin: (value: any) => void;
      const loginPromise = new Promise((resolve) => {
        resolveLogin = resolve;
      });
      mockUserStore.login.mockReturnValue(loginPromise);

      const wrapper = mount(Login);

      const inputs = wrapper.findAll('input');
      await inputs[0].setValue('test@example.com');
      await inputs[1].setValue('password123');

      const form = wrapper.find('form');
      await form.trigger('submit');

      // Check loading state before promise resolves
      expect(wrapper.text()).toContain('Logging in...');

      // Resolve the promise
      resolveLogin!({ success: true });
      await flushPromises();

      // After completion, should show regular text
      expect(wrapper.text()).toContain('Log In');
    });
  });
});
