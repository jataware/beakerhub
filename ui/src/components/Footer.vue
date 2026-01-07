<template>
  <footer class="site-footer splash-footer" :class="{ compact: props.compact }">
    <div class="footer-expandable" :style="props.compact ? undefined : expandableStyle">
      <div ref="footerContentRef" class="footer-content">
        <div class="footer-brand-section">
          <div class="footer-brand">
            <BeakerHubLogo />
            <h3>{{ footer.productName }}</h3>
          </div>
          <p class="footer-description">{{ footer.tagline }}</p>
        </div>

        <div class="footer-links-section">
          <div class="footer-links-group">
            <h4 class="footer-title">Get Started</h4>
            <ul class="footer-links">
              <li v-if="!props.compact && !isHidden('features')" class="features-link">
                <a @click="scrollToSection('features')">Features</a>
              </li>
              <li v-if="footer.documentationUrl">
                <a :href="footer.documentationUrl" target="_blank" rel="noopener">Documentation</a>
              </li>
            </ul>
          </div>

          <div class="footer-links-group">
            <h4 class="footer-title">Connect</h4>
            <ul class="footer-links">
              <li v-if="footer.githubUrl">
                <a :href="footer.githubUrl" target="_blank" rel="noopener">GitHub</a>
              </li>
              <li v-if="footer.contactEmail">
                <a
                  class="footer-email"
                  :href="`mailto:${footer.contactEmail}`"
                  @click.stop.prevent="showEmailContact"
                >{{ footer.contactEmail }}</a>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <div class="footer-bottom">
      <p>
        &copy; {{ footer.copyrightYears }}
        <a
          v-if="footer.copyrightUrl"
          :href="footer.copyrightUrl"
          target="_blank"
          rel="noopener"
        >{{ footer.copyrightHolder }}</a>
        <span v-else>{{ footer.copyrightHolder }}</span>.
        {{ footer.productName }} is available under the MIT License.
      </p>
    </div>
  </footer>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import BeakerHubLogo from './BeakerHubLogo.vue';
import { useSiteConfig } from '@/siteConfig';

defineOptions({
  name: 'BeakerHubFooter',
});

interface Props {
  compact?: boolean;
  hideTargets?: string;
  scrollProgress?: number;
}

const props = withDefaults(defineProps<Props>(), {
  compact: false,
  hideTargets: '',
  scrollProgress: 1,
});

const { footer } = useSiteConfig();
const footerContentRef = ref<HTMLElement | null>(null);
const contentHeight = ref(0);

function measureContent(): void {
  if (footerContentRef.value) {
    contentHeight.value = footerContentRef.value.scrollHeight;
  }
}

onMounted(() => {
  measureContent();
  window.addEventListener('resize', measureContent);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', measureContent);
});

const expandableStyle = computed(() => ({
  maxHeight: `${contentHeight.value * props.scrollProgress}px`,
  opacity: props.scrollProgress,
  overflow: 'hidden',
}));

const hiddenTargets = computed(() => {
  if (!props.hideTargets) {
    return [];
  }
  return props.hideTargets.split(',').map((target) => target.trim().toLowerCase());
});

function isHidden(target: string): boolean {
  return hiddenTargets.value.includes(target.toLowerCase());
}

function scrollToSection(sectionId: string): void {
  document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth' });
}

function showEmailContact(): void {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(footer.contactEmail).then(() => {
      showCopyFeedback('Email address copied to clipboard!');
    }).catch(() => {
      fallbackCopyToClipboard(footer.contactEmail);
    });
  } else {
    fallbackCopyToClipboard(footer.contactEmail);
  }
}

function fallbackCopyToClipboard(text: string): void {
  const textArea = document.createElement('textarea');
  textArea.value = text;
  textArea.style.position = 'fixed';
  textArea.style.left = '-999999px';
  textArea.style.top = '-999999px';
  textArea.setAttribute('readonly', '');
  textArea.style.opacity = '0';

  document.body.appendChild(textArea);

  try {
    textArea.focus();
    textArea.select();
    textArea.setSelectionRange(0, 99999);

    if (document.execCommand('copy')) {
      showCopyFeedback('Email address copied to clipboard!');
    } else {
      showCopyFeedback(`Please manually copy: ${text}`);
    }
  } catch {
    showCopyFeedback(`Please manually copy: ${text}`);
  } finally {
    document.body.removeChild(textArea);
  }
}

function showCopyFeedback(message: string): void {
  const toast = document.createElement('div');
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: var(--p-primary-color);
    color: white;
    padding: 1rem 2rem;
    border-radius: 0.5rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 1000;
    font-weight: 500;
    font-size: 1rem;
    max-width: 90vw;
    text-align: center;
  `;

  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => {
      document.body.removeChild(toast);
    }, 300);
  }, 2000);
}
</script>

<style lang="scss" scoped>
.site-footer {
  opacity: 1;
  position: relative;
  z-index: 1;

  &:not(.compact) {
    .footer-content {
      max-width: 700px;
      margin: 0 auto;
      padding: 1rem 0 0;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 0.5rem;
      text-align: center;
    }

    .footer-brand-section {
      flex: 0 0 auto;
      min-width: 240px;
    }

    .footer-brand {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      margin-bottom: 1rem;

      h3 {
        font-size: 1.5rem;
        font-weight: 600;
        color: var(--p-primary-color);
        margin: 0.5rem 0 0;
        background: linear-gradient(135deg, var(--p-primary-color), var(--p-blue-500));
        background-clip: text;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
      }
    }

    .footer-description {
      color: var(--text-color-secondary);
      line-height: 1.6;
      font-size: 1rem;
    }

    .footer-links-section {
      display: flex;
      gap: 2rem;
      justify-content: center;
    }

    .footer-title {
      font-size: 1rem;
      font-weight: 600;
      margin-bottom: 1rem;
      color: var(--p-text-color);
    }

    .footer-links {
      list-style: none;
      padding: 0;
      margin: 0;

      li {
        margin-bottom: 0.5rem;
      }
    }

    .features-link a {
      cursor: pointer;
    }

    .footer-email {
      user-select: text;
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
      font-size: 0.9rem;
    }

    .footer-bottom {
      max-width: 1200px;
      margin: 0 auto;
      text-align: center;
    }
  }

  &.compact {
    display: flex;
    flex-direction: row;
    justify-content: center;
    align-items: center;
    padding: 0.4rem;
    gap: 3rem;

    .footer-expandable,
    .footer-content,
    .footer-links-section,
    .footer-links-group,
    .footer-links {
      display: contents;
    }

    .footer-brand-section {
      display: grid;
      grid-template-areas:
        'logo title'
        'logo tagline';
      grid-template-columns: auto auto;
      align-items: center;
    }

    .footer-brand {
      display: contents;

      :deep(.beaker-logo) {
        grid-area: logo;
        height: 3.4rem;
      }

      h3 {
        grid-area: title;
        font-size: 1.2rem;
        font-weight: 600;
        color: var(--p-primary-color);
        margin: 0.5rem 0 0;
        background: linear-gradient(135deg, var(--p-primary-color), var(--p-blue-500));
        background-clip: text;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
      }
    }

    .footer-description {
      grid-area: tagline;
      color: var(--text-color-secondary);
      line-height: 1.2;
      font-size: 1rem;
      margin: 0;
    }

    .footer-title,
    .features-link {
      display: none;
    }

    .footer-bottom p {
      margin: 0;
    }
  }

  a {
    color: var(--text-color-secondary);
    text-decoration: none;
    transition: color 0.2s;

    &:hover {
      color: var(--p-primary-color);
    }
  }

  .footer-bottom {
    color: var(--text-color-secondary);

    a {
      color: var(--p-primary-color);
      font-weight: 500;

      &:hover {
        color: var(--p-blue-500);
        text-decoration: underline;
      }
    }
  }
}

@media (max-width: 768px) {
  .site-footer:not(.compact) {
    .footer-content,
    .footer-links-section {
      flex-direction: column;
    }

    .footer-content {
      gap: 3rem;
    }

    .footer-links-section {
      gap: 2rem;
    }
  }
}
</style>
