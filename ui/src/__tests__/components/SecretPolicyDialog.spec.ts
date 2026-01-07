import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import SecretPolicyDialog from '@/components/SecretPolicyDialog.vue';
import { SECRET_POLICY_AXES, type SecretPolicies } from '@/utils/secretPolicies';

// Mock PrimeVue components: Dialog renders its slots inline so the content is queryable.
vi.mock('primevue/dialog', () => ({
  default: {
    name: 'Dialog',
    template: '<div class="mock-dialog"><slot /><div class="mock-footer"><slot name="footer" /></div></div>',
    props: ['visible', 'header', 'modal', 'style'],
  },
}));

vi.mock('primevue/select', () => ({
  default: {
    name: 'Select',
    template: '<div class="mock-select"></div>',
    props: ['modelValue', 'options', 'optionLabel', 'optionValue', 'inputId'],
  },
}));

vi.mock('primevue/button', () => ({
  default: {
    name: 'Button',
    template: '<button :disabled="disabled" @click="$emit(\'click\', $event)">{{ label }}</button>',
    props: ['label', 'severity', 'text', 'disabled', 'loading'],
    // Declared so Vue does not also bind the parent's @click natively, which
    // would fire the handler twice.
    emits: ['click'],
  },
}));

vi.mock('primevue/tag', () => ({
  default: {
    name: 'Tag',
    template: '<span class="mock-tag">{{ value }}</span>',
    props: ['value', 'severity'],
  },
}));

function mountDialog(policies: SecretPolicies = {}) {
  return mount(SecretPolicyDialog, {
    props: { visible: true, envVar: 'MY_API_KEY', policies },
  });
}

/** The mocked Select for a given axis key, located via its inputId. */
function selectFor(wrapper: ReturnType<typeof mountDialog>, key: string) {
  const select = wrapper
    .findAllComponents({ name: 'Select' })
    .find(component => component.props('inputId') === `policy-${key}`);
  if (!select) {
    throw new Error(`No Select rendered for axis ${key}`);
  }
  return select;
}

function buttonByLabel(wrapper: ReturnType<typeof mountDialog>, label: string) {
  const button = wrapper
    .findAllComponents({ name: 'Button' })
    .find(component => component.props('label') === label);
  if (!button) {
    throw new Error(`No Button with label "${label}"`);
  }
  return button;
}

describe('SecretPolicyDialog', () => {
  it('renders one select per policy axis', () => {
    const wrapper = mountDialog();
    expect(wrapper.findAllComponents({ name: 'Select' })).toHaveLength(SECRET_POLICY_AXES.length);
  });

  it('shows every axis as inheriting its default when there are no overrides', () => {
    const wrapper = mountDialog();
    const tags = wrapper.findAll('.mock-tag').map(tag => tag.text());
    expect(tags).toEqual(SECRET_POLICY_AXES.map(() => 'default'));

    for (const axis of SECRET_POLICY_AXES) {
      expect(selectFor(wrapper, axis.key).props('modelValue')).toBe(axis.defaultValue);
    }
  });

  it('lists each policy once, with the default hoisted and marked', () => {
    const wrapper = mountDialog();
    const options = selectFor(wrapper, 'subkernel_environment_policy').props('options') as {
      value: string;
      label: string;
    }[];
    expect(options).toHaveLength(2);
    expect(options[0]).toMatchObject({ value: 'remove', label: 'Remove (Default)' });
    expect(options[1]).toMatchObject({ value: 'allow', label: 'Allow' });
  });

  it('never offers the same policy value twice on any axis', () => {
    const wrapper = mountDialog();
    for (const axis of SECRET_POLICY_AXES) {
      const options = selectFor(wrapper, axis.key).props('options') as { value: string }[];
      const values = options.map(o => o.value);
      expect(values).toEqual([...new Set(values)]);
      expect(values).toHaveLength(axis.options.length);
      // The default leads, and is the only option labelled as such.
      expect(values[0]).toBe(axis.defaultValue);
      const marked = (options as { label: string }[]).filter(o => o.label.includes('(Default)'));
      expect(marked).toHaveLength(1);
    }
  });

  it('marks an overridden axis and preselects its value', () => {
    const wrapper = mountDialog({ subkernel_environment_policy: 'allow' });
    expect(selectFor(wrapper, 'subkernel_environment_policy').props('modelValue')).toBe('allow');
    expect(wrapper.findAll('.mock-tag').map(t => t.text())).toContain('overridden');
  });

  it('treats a stored value equal to the default as inherited, not overridden', () => {
    const wrapper = mountDialog({ subkernel_environment_policy: 'remove' });
    expect(selectFor(wrapper, 'subkernel_environment_policy').props('modelValue')).toBe('remove');
    expect(wrapper.findAll('.mock-tag').map(t => t.text())).not.toContain('overridden');
  });

  it('emits only genuine overrides on save', async () => {
    const wrapper = mountDialog();
    await selectFor(wrapper, 'subkernel_environment_policy').vm.$emit('update:modelValue', 'allow');
    await selectFor(wrapper, 'ui_message_policy').vm.$emit('update:modelValue', 'redact'); // == default
    await buttonByLabel(wrapper, 'Save').trigger('click');

    expect(wrapper.emitted('save')).toEqual([[{ subkernel_environment_policy: 'allow' }]]);
  });

  it('drops an axis back to inherited when the default option is chosen', async () => {
    const wrapper = mountDialog({ subkernel_environment_policy: 'allow' });
    await selectFor(wrapper, 'subkernel_environment_policy').vm.$emit('update:modelValue', 'remove');
    expect(selectFor(wrapper, 'subkernel_environment_policy').props('modelValue')).toBe('remove');
    expect(wrapper.findAll('.mock-tag').map(t => t.text())).not.toContain('overridden');

    await buttonByLabel(wrapper, 'Save').trigger('click');
    expect(wrapper.emitted('save')).toEqual([[{}]]);
  });

  it('resets every axis to its default', async () => {
    const wrapper = mountDialog({
      subkernel_environment_policy: 'allow',
      agent_message_policy: 'remove',
    });
    const reset = buttonByLabel(wrapper, 'Reset all to defaults');
    expect(reset.props('disabled')).toBe(false);

    await reset.trigger('click');
    await buttonByLabel(wrapper, 'Save').trigger('click');
    expect(wrapper.emitted('save')).toEqual([[{}]]);
  });

  it('disables reset when nothing is overridden', () => {
    const wrapper = mountDialog();
    expect(buttonByLabel(wrapper, 'Reset all to defaults').props('disabled')).toBe(true);
  });

  it('discards edits when cancelled, and reloads the props on reopen', async () => {
    const wrapper = mountDialog();
    await selectFor(wrapper, 'ui_message_policy').vm.$emit('update:modelValue', 'allow');
    expect(selectFor(wrapper, 'ui_message_policy').props('modelValue')).toBe('allow');

    await buttonByLabel(wrapper, 'Cancel').trigger('click');
    expect(wrapper.emitted('update:visible')).toEqual([[false]]);

    // Reopening resyncs the working copy from the props.
    await wrapper.setProps({ visible: false });
    await wrapper.setProps({ visible: true });
    expect(selectFor(wrapper, 'ui_message_policy').props('modelValue')).toBe('redact');
  });

  it('names the secret in the header', () => {
    const wrapper = mountDialog();
    expect(wrapper.findComponent({ name: 'Dialog' }).props('header')).toBe('Policies — MY_API_KEY');
  });

  it('flags the agent policy as not yet enforced', () => {
    const wrapper = mountDialog();
    expect(wrapper.text()).toContain('not yet enforced by the notebook server');
  });
});
