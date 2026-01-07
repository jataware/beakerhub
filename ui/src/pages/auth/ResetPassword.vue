<template>
  <div class="auth-container">
    <div class="auth-content">
      <div v-if="!submitted && !showCodeForm">
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
              <div class="reset-icon">
                <i class="pi pi-key"></i>
              </div>
              <h2 class="form-title">Reset Password</h2>
              <p class="form-subtitle">Enter your email to receive a password reset link</p>
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

              <Button
                type="submit"
                :disabled="!isFormValid || isSubmitting"
                :loading="isSubmitting"
                class="submit-button"
                size="large"
              >
                {{ isSubmitting ? 'Sending...' : 'Send Reset Link' }}
              </Button>
            </form>

            <Divider />

            <div class="already-have-code">
              <button @click="handleAlreadyHaveCode" class="already-have-code-link" type="button">
                I already have a code
              </button>
            </div>

            <div class="back-to-login">
              <span class="back-text">Remember your password? </span>
              <RouterLink :to="{ name: 'login' }" class="back-link-text">Back to Login</RouterLink>
            </div>

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

      <Card v-else-if="showCodeForm && !passwordResetComplete" class="auth-card">
        <template #content>
          <div class="form-header">
            <div class="reset-icon">
              <i class="pi pi-lock"></i>
            </div>
            <h2 class="form-title">Enter Reset Code</h2>
            <p class="form-subtitle" v-if="!skipToCodeEntry">Check your email ({{ formData.email }}) for the verification code</p>
            <p class="form-subtitle" v-else>Enter your email and the verification code you received</p>
          </div>

          <form @submit.prevent="handleConfirmPassword" class="form-content">
            <Message v-if="errorMessage" severity="error" :closable="false" class="error-message">
              {{ errorMessage }}
            </Message>

            <div v-if="skipToCodeEntry" class="form-field">
              <label for="email-code" class="field-label">Email Address</label>
              <div class="input-wrapper">
                <InputText
                  id="email-code"
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
                  placeholder="Enter code from email"
                  class="input-with-icon"
                  required
                />
                <i class="pi pi-shield input-icon"></i>
              </div>
            </div>

            <div class="form-field">
              <label for="newPassword" class="field-label">New Password</label>
              <div class="input-wrapper">
                <Password
                  id="newPassword"
                  v-model="formData.newPassword"
                  placeholder="Enter new password"
                  toggleMask
                  :feedback="false"
                  class="full-width-password"
                  required
                />
              </div>
            </div>

            <div class="form-field">
              <label for="confirmNewPassword" class="field-label">Confirm New Password</label>
              <div class="input-wrapper">
                <Password
                  id="confirmNewPassword"
                  v-model="formData.confirmNewPassword"
                  placeholder="Confirm new password"
                  toggleMask
                  :feedback="false"
                  class="full-width-password"
                  required
                />
              </div>
            </div>

            <Message v-if="formData.newPassword && formData.confirmNewPassword && formData.newPassword !== formData.confirmNewPassword" severity="warn" :closable="false">
              passwords do not match
            </Message>

            <Button
              type="submit"
              :disabled="!isCodeFormValid || isSubmitting"
              :loading="isSubmitting"
              class="submit-button"
              size="large"
            >
              {{ isSubmitting ? 'Resetting...' : 'Reset Password' }}
            </Button>
          </form>

          <Divider />

          <p v-if="!skipToCodeEntry" class="resend-text">
            Didn't receive a code?
            <button @click="resendEmail" class="resend-link" :disabled="resendCooldown > 0">
              {{ resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend' }}
            </button>
          </p>

          <div class="back-to-login">
            <RouterLink :to="{ name: 'login' }" class="back-link-text">← Back to Login</RouterLink>
          </div>
        </template>
      </Card>

      <Card v-else-if="passwordResetComplete" class="auth-card success-card">
        <template #content>
          <div class="success-header">
            <i class="pi pi-check-circle success-icon"></i>
            <h2 class="success-title">Password Reset Successful</h2>
            <p class="success-subtitle">Your password has been successfully reset</p>
          </div>

          <Message severity="success" class="success-message">
            <div>
              You can now log in with your new password.
            </div>
          </Message>

          <Button @click="goToLogin" class="continue-button" size="large">
            Go to Login
          </Button>
        </template>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
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
  code: string;
  newPassword: string;
  confirmNewPassword: string;
}

const router = useRouter();

const formData = ref<FormData>({
  email: '',
  code: '',
  newPassword: '',
  confirmNewPassword: ''
});

const isSubmitting = ref(false);
const submitted = ref(false);
const showCodeForm = ref(false);
const passwordResetComplete = ref(false);
const resendCooldown = ref(0);
const errorMessage = ref<string | null>(null);
const skipToCodeEntry = ref(false);
let resendInterval: number | null = null;

const isFormValid = computed(() => {
  return formData.value.email;
});

const isCodeFormValid = computed(() => {
  const baseValid = formData.value.code &&
    formData.value.newPassword &&
    formData.value.confirmNewPassword &&
    formData.value.newPassword === formData.value.confirmNewPassword;

  if (skipToCodeEntry.value) {
    return baseValid && formData.value.email;
  }

  return baseValid;
});

const userStore = useUserStore();

const handleSubmit = async () => {
  if (!isFormValid.value) return;

  isSubmitting.value = true;
  errorMessage.value = null;

  try {
    const result = await userStore.forgotPassword(formData.value.email);

    if (result.success) {
      submitted.value = true;
      showCodeForm.value = true;
    } else {
      errorMessage.value = result.error || 'failed to send reset link';
    }
  } catch (err) {
    errorMessage.value = 'an unexpected error occurred';
    console.error('forgot password error:', err);
  } finally {
    isSubmitting.value = false;
  }
};

const handleConfirmPassword = async () => {
  if (!isCodeFormValid.value) return;

  isSubmitting.value = true;
  errorMessage.value = null;

  try {
    const result = await userStore.confirmPassword(
      formData.value.email,
      formData.value.code,
      formData.value.newPassword
    );

    if (result.success) {
      passwordResetComplete.value = true;
    } else {
      errorMessage.value = result.error || 'failed to reset password';
    }
  } catch (err) {
    errorMessage.value = 'an unexpected error occurred';
    console.error('confirm password error:', err);
  } finally {
    isSubmitting.value = false;
  }
};

const resendEmail = async () => {
  try {
    await userStore.forgotPassword(formData.value.email);
    resendCooldown.value = 30;
    resendInterval = window.setInterval(() => {
      resendCooldown.value--;
      if (resendCooldown.value <= 0 && resendInterval) {
        clearInterval(resendInterval);
        resendInterval = null;
      }
    }, 1000);
  } catch (err) {
    console.error('resend error:', err);
  }
};

const goToLogin = () => {
  router.push({ name: 'login' });
};

const handleAlreadyHaveCode = () => {
  skipToCodeEntry.value = true;
  showCodeForm.value = true;
  errorMessage.value = null;
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
  margin-top: max(1.5rem, 15vh);
}

.auth-header {
  margin-bottom: 1rem;
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
  font-size: 1.125rem;
  margin-bottom: 0;
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

.reset-icon {
  margin: 0 auto 0.75rem;
  width: 3rem;
  height: 3rem;
  background-color: var(--p-purple-600);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.reset-icon i {
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

.submit-button {
  width: 100%;
}

.back-to-login, .signup-link, .already-have-code {
  text-align: center;
}

.already-have-code {
  margin-bottom: 1rem;
}

.back-text, .signup-text {
  font-size: 0.875rem;
  color: var(--p-text-muted-color);
}

.back-link-text, .signup-link-text {
  color: var(--p-primary-color);
  text-decoration: none;
  font-weight: 500;
  font-size: 0.875rem;
}

.back-link-text:hover, .signup-link-text:hover {
  text-decoration: underline;
}

.already-have-code-link {
  color: var(--p-primary-color);
  background: none;
  border: none;
  text-decoration: underline;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  padding: 0;
}

.already-have-code-link:hover {
  color: var(--p-primary-600);
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

.success-card {
  text-align: center;
}

.success-header {
  margin-bottom: 1.5rem;
}

.success-icon {
  font-size: 4rem;
  color: var(--p-purple-600);
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

.resend-text {
  font-size: 0.875rem;
  color: var(--p-text-muted-color);
  margin-bottom: 1rem;
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

.continue-button {
  width: 100%;
}

.full-width-password {
  width: 100%;
}

.full-width-password :deep(.p-password-input) {
  width: 100%;
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
</style>
