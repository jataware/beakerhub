<template>
  <div class="not-found-page">
    <div class="not-found-content">
      <h1 class="not-found-code">404</h1>
      <p class="not-found-message">Page not found</p>
      <p class="not-found-description">
        The page you're looking for doesn't exist or has been moved.
      </p>
      <Button as="router-link" :to="{name: 'home'}">
        <i class="pi pi-home"></i>
        Go Home
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import Button from 'primevue/button';
</script>

<style lang="scss" scoped>
.not-found-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  text-align: center;
  padding: 2rem;
}

.not-found-content {
  max-width: 480px;
}

.not-found-code {
  font-size: 6rem;
  font-weight: 700;
  line-height: 1;
  margin-bottom: 0.5rem;
  color: var(--p-primary-color);
}

.not-found-message {
  font-size: 1.5rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--p-text-color);
}

.not-found-description {
  color: var(--text-color-secondary);
  margin-bottom: 2rem;
  line-height: 1.6;
}
</style>
