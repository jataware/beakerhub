import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import SignUp from '@/pages/auth/SignUp.vue';

// Mock vue-router
const mockPush = vi.fn();
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
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

vi.mock('primevue/select', () => ({
  default: {
    name: 'Select',
    template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="opt in options" :key="opt.value" :value="opt.value">{{ opt.label }}</option></select>',
    props: ['modelValue', 'options', 'optionLabel', 'optionValue', 'placeholder', 'required'],
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
  signup: vi.fn(),
};

vi.mock('@/stores/user', () => ({
  useUserStore: () => mockUserStore,
}));

describe('SignUp', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    mockUserStore.signup.mockResolvedValue({ success: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Form Validation', () => {
    it('should disable submit button when email is empty', async () => {
      const wrapper = mount(SignUp);

      // Set all fields except email
      const selects = wrapper.findAll('select');
      const inputs = wrapper.findAll('input');
      await selects[0].setValue('health-research');
      await inputs[1].setValue('password123');
      await inputs[2].setValue('password123');

      const submitButton = wrapper.find('button[type="submit"]');
      expect(submitButton.attributes('disabled')).toBeDefined();
    });

    it('should disable submit button when use case is empty', async () => {
      const wrapper = mount(SignUp);

      const inputs = wrapper.findAll('input');
      await inputs[0].setValue('test@example.com');
      await inputs[1].setValue('password123');
      await inputs[2].setValue('password123');

      const submitButton = wrapper.find('button[type="submit"]');
      expect(submitButton.attributes('disabled')).toBeDefined();
    });

    it('should disable submit button when passwords do not match', async () => {
      const wrapper = mount(SignUp);

      const inputs = wrapper.findAll('input');
      const selects = wrapper.findAll('select');
      await inputs[0].setValue('test@example.com');
      await selects[0].setValue('health-research');
      await inputs[1].setValue('password123');
      await inputs[2].setValue('differentpassword');

      const submitButton = wrapper.find('button[type="submit"]');
      expect(submitButton.attributes('disabled')).toBeDefined();
    });

    it('should show password mismatch error when passwords differ', async () => {
      const wrapper = mount(SignUp);

      const inputs = wrapper.findAll('input');
      await inputs[1].setValue('password123');
      await inputs[2].setValue('differentpassword');

      expect(wrapper.text()).toContain('Passwords do not match');
    });

    it('should enable submit button when all fields are valid', async () => {
      const wrapper = mount(SignUp);

      const inputs = wrapper.findAll('input');
      const selects = wrapper.findAll('select');
      await inputs[0].setValue('test@example.com');
      await selects[0].setValue('health-research');
      await inputs[1].setValue('password123');
      await inputs[2].setValue('password123');

      const submitButton = wrapper.find('button[type="submit"]');
      expect(submitButton.attributes('disabled')).toBeUndefined();
    });
  });

  describe('Form Submission', () => {
    it('should call userStore.signup with email, password, and useCase on submit', async () => {
      const wrapper = mount(SignUp);

      const inputs = wrapper.findAll('input');
      const selects = wrapper.findAll('select');
      await inputs[0].setValue('test@example.com');
      await selects[0].setValue('health-research');
      await inputs[1].setValue('password123');
      await inputs[2].setValue('password123');

      const form = wrapper.find('form');
      await form.trigger('submit');
      await flushPromises();

      expect(mockUserStore.signup).toHaveBeenCalledWith('test@example.com', 'password123', 'health-research');
    });

    it('should show success message on successful signup', async () => {
      mockUserStore.signup.mockResolvedValue({ success: true });

      const wrapper = mount(SignUp);

      const inputs = wrapper.findAll('input');
      const selects = wrapper.findAll('select');
      await inputs[0].setValue('test@example.com');
      await selects[0].setValue('health-research');
      await inputs[1].setValue('password123');
      await inputs[2].setValue('password123');

      const form = wrapper.find('form');
      await form.trigger('submit');
      await flushPromises();

      expect(wrapper.text()).toContain('Welcome to BeakerHub');
      expect(wrapper.text()).toContain('Check your email');
    });

    it('should display error message on failed signup', async () => {
      mockUserStore.signup.mockResolvedValue({ success: false, error: 'Email already registered' });

      const wrapper = mount(SignUp);

      const inputs = wrapper.findAll('input');
      const selects = wrapper.findAll('select');
      await inputs[0].setValue('test@example.com');
      await selects[0].setValue('health-research');
      await inputs[1].setValue('password123');
      await inputs[2].setValue('password123');

      const form = wrapper.find('form');
      await form.trigger('submit');
      await flushPromises();

      expect(wrapper.text()).toContain('Email already registered');
    });

    it('should display generic error message on exception', async () => {
      mockUserStore.signup.mockRejectedValue(new Error('Network error'));

      const wrapper = mount(SignUp);

      const inputs = wrapper.findAll('input');
      const selects = wrapper.findAll('select');
      await inputs[0].setValue('test@example.com');
      await selects[0].setValue('health-research');
      await inputs[1].setValue('password123');
      await inputs[2].setValue('password123');

      const form = wrapper.find('form');
      await form.trigger('submit');
      await flushPromises();

      expect(wrapper.text()).toContain('an unexpected error occurred');
    });
  });

  describe('Navigation', () => {
    it('should navigate to email verification with email param when clicking verify button', async () => {
      mockUserStore.signup.mockResolvedValue({ success: true });

      const wrapper = mount(SignUp);

      const inputs = wrapper.findAll('input');
      const selects = wrapper.findAll('select');
      await inputs[0].setValue('test@example.com');
      await selects[0].setValue('health-research');
      await inputs[1].setValue('password123');
      await inputs[2].setValue('password123');

      // Submit form to show success state
      const form = wrapper.find('form');
      await form.trigger('submit');
      await flushPromises();

      // Click the verification button
      const verifyButton = wrapper.findAll('button').find(b => b.text().includes('Verify'));
      await verifyButton!.trigger('click');

      expect(mockPush).toHaveBeenCalledWith({
        name: 'email-validation',
        query: { email: 'test@example.com' }
      });
    });

    it('should have link to login page', () => {
      const wrapper = mount(SignUp);

      const loginLink = wrapper.findAll('a').find(a => a.text().includes('Log In'));
      expect(loginLink).toBeDefined();
    });

    it('should have link to invite signup page', () => {
      const wrapper = mount(SignUp);

      const inviteLink = wrapper.findAll('a').find(a => a.text().includes('Join by Invite'));
      expect(inviteLink).toBeDefined();
    });

    it('should have link back to home page', () => {
      const wrapper = mount(SignUp);

      const homeLink = wrapper.findAll('a').find(a => a.text().includes('Back to Site'));
      expect(homeLink).toBeDefined();
    });
  });

  describe('Use Case Options', () => {
    it('should render all use case options', () => {
      const wrapper = mount(SignUp);

      const select = wrapper.find('select');
      const options = select.findAll('option');

      expect(options.length).toBeGreaterThan(5);
      expect(wrapper.text()).toContain('Health & Medical Research');
      expect(wrapper.text()).toContain('Environmental Data Analysis');
      expect(wrapper.text()).toContain('Biomedical Discovery');
    });
  });
});
