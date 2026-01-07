<template>
    <component :is="pageComponent"/>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import SplashPage from '@/pages/SplashPage.vue';
import Dashboard from '@/pages/Dashboard.vue';
import { useUserStore } from '@/stores/user';

const userStore = useUserStore();
const pageComponent = computed(() => (userStore.isLoggedIn ? Dashboard : SplashPage))

</script>

<style lang="scss" scoped>
</style>
