import { describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';

import Footer from '@/components/Footer.vue';
import {
  defaultFooterConfig,
  resolveSiteConfig,
  siteConfigKey,
} from '@/siteConfig';

vi.mock('@/components/BeakerHubLogo.vue', () => ({
  default: {
    name: 'BeakerHubLogo',
    template: '<div class="mock-beakerhub-logo">Logo</div>',
  },
}));

describe('Footer', () => {
  it('renders the default branding and links', () => {
    const wrapper = mount(Footer);

    expect(wrapper.text()).toContain('BeakerHub');
    expect(wrapper.text()).toContain('Your AI-powered co-scientist.');
    expect(wrapper.get('a[href="mailto:contact@beakerhub.com"]').text()).toBe('contact@beakerhub.com');
    expect(wrapper.get('a[href="https://jataware.github.io/beaker-notebook"]').text()).toBe('Documentation');
    expect(wrapper.get('a[href="https://github.com/jataware/beaker-notebook"]').text()).toBe('GitHub');
  });

  it('renders deployment-specific values and hides empty optional links', () => {
    const siteConfig = resolveSiteConfig({
      footer: {
        ...defaultFooterConfig,
        productName: 'Research Hub',
        tagline: 'Internal notebooks.',
        contactEmail: 'help@example.com',
        documentationUrl: '',
        githubUrl: '',
      },
    });
    const wrapper = mount(Footer, {
      global: {
        provide: {
          [siteConfigKey as symbol]: siteConfig,
        },
      },
    });

    expect(wrapper.text()).toContain('Research Hub');
    expect(wrapper.text()).toContain('Internal notebooks.');
    expect(wrapper.get('a[href="mailto:help@example.com"]').text()).toBe('help@example.com');
    expect(wrapper.text()).not.toContain('Documentation');
    expect(wrapper.text()).not.toContain('GitHub');
  });

  it('uses the compact layout and omits the splash-only feature link', () => {
    const wrapper = mount(Footer, {
      props: {
        compact: true,
      },
    });

    expect(wrapper.classes()).toContain('compact');
    expect(wrapper.text()).not.toContain('Features');
  });
});
