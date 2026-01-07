<template>
  <div class="auth-container">
    <div class="auth-content">
        <div class="auth-header">
          <div class="auth-header-logo">
            <BeakerHubLogo />
            <h1 class="brand-name">BeakerHub</h1>
          </div>
          <p class="auth-subtitle">AI-Powered Interactive Notebook Environments</p>
        </div>

        <Card class="auth-card">
          <template #content>
            <div class="form-header">
              <div class="login-icon">
                <i class="pi pi-sign-in"></i>
              </div>
              <h2 class="form-title">Welcome Back</h2>
              <p class="form-subtitle">Log in to access your BeakerHub workspaces</p>
            </div>

            <form @submit.prevent="handleSubmit" class="form-content">
              <Message v-if="errorMessage" severity="error" :closable="false" class="error-message">
                {{ errorMessage }}
              </Message>

              <div class="form-field">
                <label for="email" class="field-label">Email Address</label>
                <div class="input-wrapper">
                  <InputText
                    id="email"
                    v-model="formData.email"
                    type="email"
                    placeholder="your.email@example.com"
                    class="input-with-icon"
                    required
                  />
                  <i class="pi pi-envelope input-icon"></i>
                </div>
              </div>

              <div class="form-field">
                <label for="password" class="field-label">Password</label>
                <div class="input-wrapper password-wrapper">
                  <Password
                    id="password"
                    v-model="formData.password"
                    placeholder="Enter your password"
                    class="password-input"
                    :feedback="false"
                    toggleMask
                    required
                  />
                  <i class="pi pi-lock password-icon"></i>
                </div>
              </div>

              <div class="forgot-password">
                <RouterLink :to="{ name: 'reset-password' }" class="forgot-link">Forgot your password?</RouterLink>
              </div>

              <Button
                type="submit"
                :disabled="!isFormValid || isSubmitting"
                :loading="isSubmitting"
                class="submit-button"
                size="large"
              >
                {{ isSubmitting ? 'Logging in...' : 'Log In' }}
              </Button>
            </form>

            <Divider />

            <div class="signup-link">
              <span class="signup-text">New to BeakerHub? </span>
              <RouterLink :to="{ name: 'signup' }" class="signup-link-text">Sign Up</RouterLink>
            </div>

            <div class="hub-link">
              <RouterLink :to="{ name: 'home' }" class="hub-link-text">← Back to Site</RouterLink>
            </div>
          </template>
        </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, inject, onBeforeMount } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import Card from 'primevue/card';
import InputText from 'primevue/inputtext';
import Password from 'primevue/password';
import Button from 'primevue/button';
import Message from 'primevue/message';
import Divider from 'primevue/divider';
import BeakerHubLogo from '@/components/BeakerHubLogo.vue';
import { useUserStore } from '@/stores/user';

interface FormData {
  email: string;
  password: string;
}

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();

const formData = ref<FormData>({
  email: '',
  password: ''
});

const isSubmitting = ref(false);
const errorMessage = ref<string | null>(null);

const isFormValid = computed(() => {
  return formData.value.email && formData.value.password;
});

const handleSubmit = async () => {
  if (!isFormValid.value) return;

  isSubmitting.value = true;
  errorMessage.value = null;

  try {
    const loginResult = await userStore.login(formData.value.email, formData.value.password);
    if (loginResult.success) {
      const next = route.query.next;
      if (next && typeof next === 'string') {
        router.push(next);
      } else {
        router.push({ name: 'home' });
      }
    }
    else {
      errorMessage.value = loginResult.error
    }
  } catch (err) {
    errorMessage.value = 'login failed';
    console.error('login error:', err);
  } finally {
    isSubmitting.value = false;
  }
};

</script>

<style scoped>
.auth-container {
  min-height: 100vh;
  background: linear-gradient(135deg,
    var(--p-surface-a) 0%,
    rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.03) 25%,
    rgba(var(--p-blue-500-rgb, 59, 130, 246), 0.02) 50%,
    rgba(var(--p-purple-500-rgb, 168, 85, 247), 0.03) 75%,
    var(--p-surface-a) 100%
  );
  color: var(--p-text-color);
  position: relative;
  display: flex;
  justify-content: center;
  padding: 1rem;
  align-items: start;

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

  > * {
    position: relative;
    z-index: 1;
  }

  * {
    box-sizing: border-box;
  }
  button, input, select, textarea {
    font-family: inherit;
    font-size: inherit;
  }
}

.auth-content {
  width: 100%;
  max-width: 28rem;
  margin-top: max(1.5rem, 14vh);
}

.auth-header {
  margin-bottom: 1rem;
}

.auth-title {
  /* margin-bottom: 0.5rem; */

  font-size: 2.25rem;
  font-weight: bold;
  color: var(--p-text-color);
  /* margin-bottom: 0.5rem; */
  margin-top: 0;
  margin-bottom: 0;
}

.auth-subtitle {
  color: var(--p-text-muted-color);
  margin-top: 0.25rem;
  margin-bottom: 0;
  font-size: 1.125rem;
}

.auth-card {
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.form-header {
  text-align: center;
  margin-bottom: 1.5rem;
}

.login-icon {
  margin: 0 auto 0.75rem;
  width: 3rem;
  height: 3rem;
  background-color: var(--p-purple-600);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-icon i {
  font-size: 1.5rem;
  color: var(--p-surface-0);
}

.form-title {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 0.5rem;
  color: var(--p-text-color);
}

.form-subtitle {
  color: var(--p-text-muted-color);
  font-size: 0.875rem;
}

.form-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.error-message {
  margin-bottom: 0.5rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.field-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--p-text-color);
}

.input-wrapper {
  position: relative;
  width: 100%;
}

.input-with-icon {
  width: 100%;
  padding-left: 2.5rem;
}

.input-icon {
  position: absolute;
  left: 0.875rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--p-text-muted-color);
  opacity: 0.6;
  pointer-events: none;
  z-index: 1;
}

.password-wrapper {
  position: relative;
  width: 100%;
}

.password-input {
  width: 100%;
}

.password-input :deep(.p-password-input) {
  width: 100%;
  padding-left: 2.5rem;
}

.password-icon {
  position: absolute;
  left: 0.875rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--p-text-muted-color);
  opacity: 0.6;
  pointer-events: none;
  z-index: 2;
}

.forgot-password {
  text-align: right;
  margin-top: -0.5rem;
}

.forgot-link {
  font-size: 0.875rem;
  color: var(--p-primary-color);
  text-decoration: none;
}

.forgot-link:hover {
  text-decoration: underline;
}

.submit-button {
  width: 100%;
}

.signup-link {
  text-align: center;
}

.signup-text {
  font-size: 0.875rem;
  color: var(--p-text-muted-color);
}

.signup-link-text {
  color: var(--p-primary-color);
  text-decoration: none;
  font-weight: 500;
  font-size: 0.875rem;
}

.signup-link-text:hover {
  text-decoration: underline;
}

.hub-link {
  text-align: center;
  margin-top: 1rem;
}

.hub-link-text {
  color: var(--p-text-muted-color);
  text-decoration: none;
  font-size: 0.875rem;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.hub-link-text:hover {
  color: var(--p-primary-color);
}

@media (max-width: 640px) {
  .auth-title {
    font-size: 2rem;
  }

  .auth-container {
    padding: 0.75rem;
  }
}

@media (max-height: 600px) {
  .auth-content {
    margin-top: max(1rem, 6vh);
  }
}


.auth-header-logo {
  display: flex;
  align-items: flex-end;
  margin-bottom: 0;
 }

.brand-name {
    font-size: 2.25rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--p-primary-color), var(--p-blue-500));
    background-clip: text;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}


</style>
