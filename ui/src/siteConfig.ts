import { inject, type InjectionKey } from 'vue';

export interface FooterConfig {
  productName: string;
  tagline: string;
  documentationUrl: string;
  githubUrl: string;
  contactEmail: string;
  copyrightYears: string;
  copyrightHolder: string;
  copyrightUrl: string;
}

export interface SiteConfig {
  pathPrefix: string;
  username: string | null;
  _xsrf?: string;
  footer: FooterConfig;
}

export const defaultFooterConfig: FooterConfig = {
  productName: 'BeakerHub',
  tagline: 'Your AI-powered co-scientist.',
  documentationUrl: 'https://jataware.github.io/beaker-notebook',
  githubUrl: 'https://github.com/jataware/beaker-notebook',
  contactEmail: 'contact@beakerhub.com',
  copyrightYears: '2024-present',
  copyrightHolder: 'Jataware Corp',
  copyrightUrl: 'https://jataware.com',
};

export const defaultSiteConfig: SiteConfig = {
  pathPrefix: '/',
  username: null,
  footer: defaultFooterConfig,
};

export const siteConfigKey: InjectionKey<SiteConfig> = Symbol('siteConfig');

export function resolveSiteConfig(config: Partial<SiteConfig>): SiteConfig {
  return {
    ...defaultSiteConfig,
    ...config,
    footer: {
      ...defaultFooterConfig,
      ...config.footer,
    },
  };
}

export function useSiteConfig(): SiteConfig {
  return inject(siteConfigKey, defaultSiteConfig);
}
