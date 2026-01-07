<template>
  <div class="auth-container">
    <div class="auth-content">
      <div v-if="!validated">
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
              <h2 class="form-title">Verify Your Email</h2>
              <p class="form-subtitle">Enter the verification code sent to your email address</p>
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
                <label for="code" class="field-label">Verification Code</label>
                <div class="input-wrapper">
                  <InputText
                    id="code"
                    v-model="formData.code"
                    type="text"
                    placeholder="Enter 6-digit code"
                    class="input-with-icon code-input"
                    maxlength="6"
                    required
                  />
                  <i class="pi pi-key input-icon"></i>
                </div>
                <small class="field-help">Check your email for the 6-digit verification code</small>
              </div>

              <Button
                type="submit"
                :disabled="!isFormValid || isSubmitting"
                :loading="isSubmitting"
                class="submit-button"
                size="large"
              >
                {{ isSubmitting ? 'Verifying...' : 'Verify Email' }}
              </Button>
            </form>

            <div class="resend-section">
              <p class="resend-text">
                Didn't receive a code?
                <button @click="resendCode" class="resend-link" :disabled="resendCooldown > 0">
                  {{ resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend Code' }}
                </button>
              </p>
            </div>

            <Divider />

            <div class="login-link">
              <span class="login-text">Already verified? </span>
              <RouterLink :to="{ name: 'login' }" class="login-link-text">Log In</RouterLink>
            </div>

            <div class="hub-link">
              <RouterLink :to="{ name: 'home' }" class="hub-link-text">← Back to Site</RouterLink>
            </div>
          </template>
        </Card>
      </div>

      <Card v-else class="auth-card success-card">
        <template #content>
          <div class="success-header">
            <i class="pi pi-check-circle success-icon"></i>
            <h2 class="success-title">Email Verified!</h2>
            <p class="success-subtitle">Your email address has been successfully verified</p>
          </div>

          <Message severity="success" class="success-message">
            <template #icon>
              <i class="pi pi-info-circle"></i>
            </template>
            <div>
              <h3 class="message-title">What's Next?</h3>
              <ul class="message-list">
                <li>Your account is now fully activated</li>
                <li>You can access all BeakerHub features</li>
                <li>Start creating your first notebook</li>
              </ul>
            </div>
          </Message>

          <Button @click="goToLogin" class="continue-button" size="large">
            Continue to Login
          </Button>
        </template>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter, RouterLink } from 'vue-router';
import Card from 'primevue/card';
import InputText from 'primevue/inputtext';
import Button from 'primevue/button';
import Message from 'primevue/message';
import Divider from 'primevue/divider';
import BeakerHubLogo from '@/components/BeakerHubLogo.vue';
import { useUserStore } from '@/stores/user';

interface FormData {
  email: string;
  code: string;
}

const route = useRoute();
const router = useRouter();

const formData = ref<FormData>({
  email: '',
  code: ''
});

const isSubmitting = ref(false);
const validated = ref(false);
const resendCooldown = ref(0);
const errorMessage = ref<string | null>(null);
let resendInterval: number | null = null;

const isFormValid = computed(() => {
  return formData.value.email && formData.value.code && formData.value.code.length === 6;
});

onMounted(() => {
  const emailFromQuery = route.query.email as string;
  if (emailFromQuery) {
    formData.value.email = emailFromQuery;
  }
});

const userStore = useUserStore();

const handleSubmit = async () => {
  if (!isFormValid.value) return;

  isSubmitting.value = true;
  errorMessage.value = null;

  try {
    const result = await userStore.confirmSignup(formData.value.email, formData.value.code);

    if (result.success) {
      validated.value = true;
    } else {
      errorMessage.value = result.error || 'verification failed';
    }
  } catch (err) {
    errorMessage.value = 'an unexpected error occurred';
    console.error('email verification error:', err);
  } finally {
    isSubmitting.value = false;
  }
};

const resendCode = async () => {
  if (!formData.value.email) return;

  try {
    // TODO: This is a bug - calling signup() to resend the verification code is incorrect.
    // Should use a dedicated Cognito resendSignUpConfirmationCode API instead.
    await userStore.signup(formData.value.email, 'temp-password-not-used', '');

    resendCooldown.value = 60;
    resendInterval = window.setInterval(() => {
      resendCooldown.value--;
      if (resendCooldown.value <= 0 && resendInterval) {
        clearInterval(resendInterval);
        resendInterval = null;
      }
    }, 1000);
  } catch (err) {
    console.error('resend code error:', err);
  }
};

const goToLogin = () => {
  router.push({ name: 'login' });
};

onUnmounted(() => {
  if (resendInterval) {
    clearInterval(resendInterval);
  }
});
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
  margin-top: max(1.5rem, 17vh);
}

.auth-header {
  margin-bottom: 0.5rem;
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

.auth-subtitle {
  color: var(--p-text-muted-color);
  margin-top: 0.25rem;
  margin-bottom: 0;
  font-size: 1.125rem;
}

.auth-header-logo {
  display: flex;
  align-items: flex-end;
  margin-bottom: 0;
}

.auth-card {
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.form-header {
  text-align: center;
  margin-bottom: 1.5rem;
}

.validation-icon {
  margin: 0 auto 0.75rem;
  width: 3rem;
  height: 3rem;
  background-color: var(--p-purple-600);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.validation-icon i {
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

.field-help {
  color: var(--p-text-muted-color);
  font-size: 0.75rem;
  margin-top: 0.25rem;
}

.input-wrapper {
  position: relative;
  width: 100%;
}

.input-with-icon {
  width: 100%;
  padding-left: 2.5rem;
}

.code-input {
  text-align: center;
  font-family: monospace;
  font-size: 1.1rem;
  letter-spacing: 0.2rem;
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

.submit-button {
  width: 100%;
}

.resend-section {
  text-align: center;
  margin-top: 1rem;
}

.resend-text {
  font-size: 0.875rem;
  color: var(--p-text-muted-color);
}

.resend-link {
  color: var(--p-primary-color);
  background: none;
  border: none;
  text-decoration: underline;
  cursor: pointer;
  font-size: 0.875rem;
}

.resend-link:hover:not(:disabled) {
  color: var(--p-primary-600);
}

.resend-link:disabled {
  color: var(--p-text-muted-color);
  cursor: not-allowed;
}

.login-link {
  text-align: center;
}

.login-text {
  font-size: 0.875rem;
  color: var(--p-text-muted-color);
}

.login-link-text {
  color: var(--p-primary-color);
  text-decoration: none;
  font-weight: 500;
  font-size: 0.875rem;
}

.login-link-text:hover {
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
  color: var(--p-purple-600);
}

.success-card {
  text-align: center;
}

.success-header {
  margin-bottom: 1.5rem;
}

.success-icon {
  font-size: 4rem;
  color: var(--p-green-400);
  margin-bottom: 1rem;
  display: block;
}

.success-title {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 0.5rem;
  color: var(--p-text-color);
}

.success-subtitle {
  color: var(--p-text-muted-color);
}

.success-message {
  text-align: left;
  margin-bottom: 1.5rem;
}

.message-title {
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.message-list {
  font-size: 0.875rem;
  list-style-type: disc;
  list-style-position: inside;
}

.message-list li {
  margin-bottom: 0.25rem;
}

.continue-button {
  width: 100%;
}

@media (max-width: 640px) {
  .auth-container {
    padding: 0.75rem;
  }
}

@media (max-height: 600px) {
  .auth-content {
    margin-top: max(1rem, 6vh);
  }
}
</style>
