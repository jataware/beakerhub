<template>
  <div id="content-container">
    <iframe v-if="connectionStatus === 'ok'" id="session" :src="iframeUrl"></iframe>
    <Spinner v-else-if="connectionStatus === 'loading'" text="Connecting to notebook..." />
    <div v-else-if="connectionStatus === 'error'" id="error-container">
      <div id="error-content">
        <h2><span style="color: red">Error:</span> Unable to connect to notebook</h2>
        <div>
          <Button label="Return to dashboard" as="router-link" :to="{name: 'home'}"/>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeMount } from 'vue';
import Button from 'primevue/button';

import { URLExt } from '@jupyterlab/coreutils';

import { useSessionStore, type SessionServerData } from '@/stores/session';
import Spinner from '@/components/Spinner.vue';
import { fetch } from '@/utils/fetch';

type ConnectionStatus = "loading" | "ok" | "error"

interface Props {
  session: string;
  url?: string;
}

const sessionStore = useSessionStore();

const props = defineProps<Props>();

const connectionStatus = ref<ConnectionStatus>("loading");

const connectionFailureRetryLimit = 10;
const connectionFailureRetryDelayMs = 250;
const connectionFailureCount = ref<number>(0);

const server = computed<SessionServerData>(() => (props.session ? sessionStore.servers[props.session] : undefined));

// TODO: Finish determining session status and restart server is session is suspended.
// const sessionStatus = computed<SessionStatus>(() => {
//   const serverInfo = sessionStore.servers[props.session];
//   const cs = sessionStore.checkServer(props.session);
//   if (serverInfo?.ready) {
//     return "active";
//   }
//   return "unknown";
// })

const iframeUrl = computed<string>(() => {
  const url = new URL(URLExt.normalize(
    (props.url !== undefined)
    ? props.url
    : server.value.url
  ));
  // Match the protocol the user is currently connecting with, since the
  // backend-configured scheme may not reflect the actual connection (e.g.
  // TLS termination at the ingress returns http:// URLs in debug/prod).
  url.protocol = window.location.protocol;
  url.searchParams.set("session", props.session);
  return url.toString();
});

const notebookIsUp = async () => {
  try {
    const isResponding = await fetch(iframeUrl.value);
    if (!isResponding.ok) {
      connectionFailureCount.value++;
    }
    return isResponding.ok;
  }
  catch(err) {
    connectionFailureCount.value++;
    console.error(err);
    return false;
  }
}

const awaitConnection = async () => {
  if (await notebookIsUp()) {
    connectionStatus.value = "ok";
    return;
  }
  if (connectionFailureCount.value >= connectionFailureRetryLimit) {
    connectionStatus.value = "error";
    return;
  }
  setTimeout(awaitConnection, connectionFailureRetryDelayMs);
}

onBeforeMount(() => {
  // Asynchronously refreshing sessionStore prior to asynchronously awaiting the notebook connection.
  // This allows the fetching to start right away without delaying showing the spinner.
  sessionStore.refresh().then(awaitConnection);
})


</script>

<style lang="scss" scoped>
#content-container {
  display: flex;
  height: 100%;
}

iframe#session {
  flex: 1;
  border: 0;
}

#error-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 8rem;
}

#error-content {
  text-align: center;
}
</style>
