import { createApp } from 'vue';
import { createPinia } from 'pinia';

import PrimeVue from 'primevue/config';
import Tooltip from 'primevue/tooltip';
import ConfirmationService from 'primevue/confirmationservice';
import DialogService from 'primevue/dialogservice';
import ToastService from 'primevue/toastservice';
import FocusTrap from 'primevue/focustrap';
import { vKeybindings } from '@jataware/beaker-vue/directives/keybindings';
import { vAutoScroll } from '@jataware/beaker-vue/directives/autoscroll';
import BeakerThemePlugin from '@jataware/beaker-vue/plugins/theme';

import App from './App.vue';
import { DefaultTheme } from '@jataware/beaker-vue/themes';
import 'primeicons/primeicons.css';

import createRouter from './router';
import { resolveSiteConfig, siteConfigKey, type SiteConfig } from './siteConfig';
import './index.scss';

const siteConfigElement = document.getElementById('site-config');
const configuredSiteConfig: Partial<SiteConfig> = siteConfigElement
  ? JSON.parse(siteConfigElement.textContent ?? '{}')
  : {};
const siteConfig = resolveSiteConfig(configuredSiteConfig);

const app = createApp(App);
const router = createRouter(siteConfig);

app.use(createPinia());
app.use(router);
app.provide(siteConfigKey, siteConfig);
app.use(PrimeVue, {
  theme: {
    preset: DefaultTheme,
    options: {
      darkModeSelector: '.beaker-dark',
      cssLayer: {
        name: 'primevue',
        order: 'primevue, beaker'
      }
    }
  },
});
app.use(ToastService);
app.use(ConfirmationService);
app.use(DialogService);
app.use(BeakerThemePlugin);
app.directive('tooltip', Tooltip);
app.directive('focustrap', FocusTrap);
app.directive('keybindings', vKeybindings);
app.directive('autoscroll', vAutoScroll);

app.mount('#app');
