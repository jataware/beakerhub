<template>
  <div id="beakerhub-page">
    <header>
        <BeakerhubHeader :size="size" class="page-header"/>
    </header>

    <content>
      <main ref="mainRef">
        <RouterView />
      </main>

      <BeakerhubFooter
        v-if="route.name !== 'session'"
        :compact="size === 'small'"
        :scroll-progress="footerScrollProgress"
      />
    </content>
  </div>
</template>

<script setup lang="ts">
import { ref, onBeforeMount, onMounted, onBeforeUnmount, computed, watch } from 'vue';
import { RouterView } from 'vue-router';
import { useRoute } from 'vue-router';

import BeakerhubFooter from '@/components/Footer.vue';
import BeakerhubHeader from '@/components/Header.vue';

import { useUserStore } from '@/stores/user';

defineOptions({
  name: 'BeakerHubBasePage',
});

const userStore = useUserStore();
const route = useRoute();

const size = computed(() => {
  if (!userStore.isLoggedIn) return "large";
  if (route.name === 'session') return "minimal";
  return "small";
});

const mainRef = ref<HTMLElement | null>(null);
const footerScrollProgress = ref(0);
const SCROLL_THRESHOLD = 300;

function handleMainScroll() {
  if (!mainRef.value) return;
  const el = mainRef.value;
  const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
  if (distFromBottom <= 0) {
    footerScrollProgress.value = 1;
  } else if (distFromBottom >= SCROLL_THRESHOLD) {
    footerScrollProgress.value = 0;
  } else {
    const progress = 1 - (distFromBottom / SCROLL_THRESHOLD);
    footerScrollProgress.value = progress * (2 - progress); // ease-out
  }
}

onMounted(() => {
  if (mainRef.value) {
    mainRef.value.addEventListener('scroll', handleMainScroll, { passive: true });
  }
});

onBeforeUnmount(() => {
  if (mainRef.value) {
    mainRef.value.removeEventListener('scroll', handleMainScroll);
  }
});

watch(route, (newVal) => {
  let newTitle = newVal.meta?.title;
  if (typeof newTitle === "function") {
    newTitle = newTitle(newVal.params);

  }
  if (typeof newTitle === "string") {
    window.document.title = `BeakerHub - ${newTitle}`;
  }
  else {
    window.document.title = "BeakerHub";
  }
});

onBeforeMount(() => {
  // Apply saved theme on mount
  const savedTheme = localStorage.getItem('theme-lightmode');
  if (savedTheme === 'dark') {
    document.documentElement.classList.add('beaker-dark');
  }
});
</script>

<style lang="scss" scoped>
header {
  grid-area: header;
}

header.page-session .header-container {
  & > svg {
    max-height: 1rem;
    height: 1rem;
  }
}

content {
  grid-area: content;
  display: grid;
  overflow-y: auto;

  grid-template:
    "main" 1fr
    "footer" max-content /
    100%
  ;
}

main {
  grid-area: main;
  overflow-y: auto;
}

footer {
  grid-area: footer;
}

#beakerhub-page {
  height: 100vh;

  display: grid;
  grid-template:
    "header" max-content
    "content" 1fr /
    100%
  ;
  overflow: hidden;

  background: linear-gradient(135deg,
    var(--p-surface-a) 0%,
    rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.03) 25%,
    rgba(var(--p-blue-500-rgb, 59, 130, 246), 0.02) 50%,
    rgba(var(--p-purple-500-rgb, 168, 85, 247), 0.03) 75%,
    var(--p-surface-a) 100%
  );
  color: var(--p-text-color);
  position: relative;

  &::before {
    content: '';
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(
      circle at 20% 20%,
      rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.05) 0%,
      transparent 50%
    ),
    radial-gradient(
      circle at 80% 80%,
      rgba(var(--p-blue-500-rgb, 59, 130, 246), 0.04) 0%,
      transparent 50%
    ),
    radial-gradient(
      circle at 40% 60%,
      rgba(var(--p-purple-500-rgb, 168, 85, 247), 0.03) 0%,
      transparent 50%
    );
    pointer-events: none;
    z-index: 0;
  }

  button, input, select, textarea {
    font-family: inherit;
    font-size: inherit;
  }
}
</style>
