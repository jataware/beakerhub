<template>
  <div class="content">
      <h2 style="text-align: center;">Launching session for {{ contextDisplayName }}:</h2>
      <div class="update-container" ref="spawnStatus">
        <div v-for="message in messages" :key="message" class="message" v-html="message"/>
        <div id="busy-indicator" v-if="busy"></div>
      </div>
      <ProgressBar id="launch-progress" :value="server?.provisioning?.percentage ?? 0"></ProgressBar>
      <div class="action-container">
        <span class="auto-connect-container">
          <label for="auto-connect-checkbox">Automatically connect when ready:</label>
          <Checkbox inputId="auto-connect-checkbox" v-model="autoConnect" binary/>
        </span>
        <Button v-if="!(serverState === 'failed')" id="connect-to-server" label="Connect" :disabled="!(serverState === 'ready')" @click="connectToSession()"/>
        <Button v-else id="retry-launch-server" label="Retry" severity="danger" @click="retry()"/>
      </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { URLExt } from '@jupyterlab/coreutils';

import Button from 'primevue/button';
import ProgressBar from 'primevue/progressbar';

import { fetch } from '@/utils/fetch';
import { useUserStore } from '@/stores/user';
import { useContextStore, type Context, type NodeImage } from '@/stores/context';
import Checkbox from 'primevue/checkbox';
import { useSessionStore, type SessionConfig, type ServerStatus,  type SessionServerData } from '@/stores/session';


const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const contextStore = useContextStore();
const sessionStore = useSessionStore();

const spawnStatus = ref<HTMLDivElement>();
const wasAtBottom = ref<boolean>();
const serverState = ref<ServerStatus>("pending")
const autoConnect = ref<boolean>(true);
const sessionId = ref<string>((typeof(route.params.session) == "string" && route.params.session !== "") ? route.params.session : undefined);

const server = computed<SessionServerData>(() => {
  const serverObj = sessionStore.servers[sessionId.value];
  if (sessionId.value !== undefined) {
    return serverObj;
  }
  else {
    return undefined
  }
});
const messages = computed<string[]>(() => (server.value?.provisioning?.logs ?? []));

const busy = computed<boolean>(() => (["pending", "launching"].includes(serverState.value)));

const currentContext = computed<Context>(() => {
  return contextStore.contexts.find((context) => context.slug === route.params.context);
});

const currentNodeImage = computed<NodeImage>(() => (contextStore.nodeImages[currentContext.value.image]))

const contextDisplayName = computed(() => {
  return currentContext.value?.display_name;
})

const scrollToBottom = () => {
  spawnStatus.value.scrollTop = spawnStatus.value.scrollHeight;
}

const isAtBottom = () => {
  const threshold = 10;
  return spawnStatus.value.scrollHeight - spawnStatus.value.scrollTop - spawnStatus.value.clientHeight < threshold;
}

const onMessage = (data: string) => {
  let payload;
  try {
    payload = JSON.parse(data);
  }
  catch(e) {
    console.error(`Got an while decoding event payload to json: "${data}"!`)
    console.error(e);
  }

  if (payload.ready && Object.keys(payload).includes("session_id")) {
    const url = URLExt.normalize(router.resolve({name: "session", params: {"session": payload["session_id"]} }).href);
    messages.value.push(`Server ready at <a href="${url}">${url}</a>`);
  }
  else if (payload.html_message) {
    messages.value.push(payload.html_message);
  }
  else if (payload.message) {
    messages.value.push(payload.message);
  }
  if (payload.progress) {
    server.value.provisioning.percentage = payload.progress;
  }
  if (payload.ready) {
    serverState.value = "ready";
  }
}

const streamEvents = async (url: string, onMessage: (data: string) => void) => {
  const serverProgress = await fetch(url);
  const reader = serverProgress.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const {done, value} = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, {stream: true});
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        onMessage(line.slice(6));
      }
    }
  }
}

const connectToSession = () => {
  // Only reroute from this page if we are actually on this page. Due to closures and callbacks, this function can be
  // called after the user has navigated away from the page in some cases.
  if (router.currentRoute.value.fullPath === route.fullPath && sessionId.value) {
    router.replace({name: "session", params: {"session": sessionId.value}})
  }
}

watch(serverState, (newValue) => {
  if (newValue === "ready" && autoConnect.value === true) {
    connectToSession();
  }
})

// Runs prior to a new message is added and rendered to get dom status just before update.
watch(messages, () => {
  wasAtBottom.value = isAtBottom();
}, {flush: "pre", deep: true})

// Runs after new message is added, scrolling to the bottom if needed.
watch(messages, () => {
  if (wasAtBottom.value) {
    scrollToBottom();
  }
}, {flush: "post", deep: true})

const retry = async () => {
  // Clear logs
  server.value?.provisioning?.logs?.splice(0, server.value.provisioning.logs.length);
  startSpawn();
}

const startSpawn = async () => {
  const serverInfo = await sessionStore.spawnServer(sessionId.value, userOptions.value)

  // Set session ID if not set
  if (sessionId.value !== serverInfo.name) {
    sessionId.value = serverInfo.name;
  }

  if (route.params.session !== sessionId.value) {
    router.replace({name: route.name, params: {...route.params, session: sessionId.value}, replace: true, force: true})
  }

  if (serverInfo.ready && autoConnect.value === true) {
    connectToSession();
  }
  else {
    streamEvents(serverInfo.progress_url, onMessage);
  }

  userStore.refresh();
}

const userOptions = computed<SessionConfig>(() => (
  {
    nodeSlug: currentNodeImage.value.slug,
    contextSlug: currentContext.value.slug,
    contextOptions: {},
  }
));

onMounted(async () => {
  await contextStore.ensureContextsLoaded();
  scrollToBottom();
  startSpawn();
});



</script>

<style lang="scss" scoped>
.content {
  margin: 0 auto;
  min-width: 30rem;
  max-width: 50rem;
}

.update-container {
  margin: 0 auto;
  background-color: #222;
  color: #ddd;
  display: flex;
  flex-direction: column;
  font-size: larger;
  font-family: monospace;
  grid-auto-flow: row;
  padding: 0.5rem;
  gap: 0.5rem;
  height: 30rem;
  border: 1px solid black;
  overflow: scroll;

  border-radius: var(--p-border-radius-md);
  border-bottom: none;
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
}

#launch-progress {
  border-top-left-radius: 0;
  border-top-right-radius: 0;
  border: 1px solid black;
  border-top: 0;
}

#busy-indicator {
  overflow: hidden;
  position: relative;
  width: min-content;
  &::after {
    content: "...";
    position: relative;
    animation: slide 2s steps(90, end) infinite;
  }
}

@keyframes slide {
  from {
    right: 90%;
  }
  to {
    right: -90%;
  }

}

.action-container {
  padding: 1rem 0;
  display: flex;
  align-items: center;

  label {
    font-weight: bold;
    cursor: pointer;
  }
}

.auto-connect-container {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1
}

</style>
