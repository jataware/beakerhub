<template>
  <div id="spinner-container">
    <div style="flex: 1"></div>
    <div id="spinner-content">
      <h2 v-if="props.text">{{ props.text }}</h2>
      <ProgressSpinner stroke-width="4"/>
    </div>
    <div style="flex: 2"></div>
  </div>
</template>

<script setup lang="ts">
import ProgressSpinner from 'primevue/progressspinner';

interface Props {
  text?: string;
}

const props = defineProps<Props>();

</script>

<style lang="scss" scoped>
#spinner-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
}

#spinner-content {
  width: fit-content;
  height: fit-content;
  text-align: center;
}

.p-progressspinner {
  aspect-ratio: 1/1;
  width: 75%;
  height: 75%;
}
</style>
