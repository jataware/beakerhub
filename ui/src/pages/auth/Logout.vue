<template>
  <Spinner text="Logging out..."/>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import ProgressSpinner from 'primevue/progressspinner';
import { useRouter } from 'vue-router';

import { useUserStore } from '@/stores/user';
import Spinner from '@/components/Spinner.vue';

const router = useRouter();
const userStore = useUserStore();

onMounted(async () => {
  await userStore.logout();
  router.push({name: "login"});
});
</script>

<style lang="scss" scoped>
#logout-container {
  display: flex;
  flex-direction: column;
  // justify-content: center;
  align-items: center;

  height: 100%;

}

#logout-content {
  width: fit-content;
  height: fit-content;
}
</style>
