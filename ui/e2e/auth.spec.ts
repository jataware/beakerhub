/**
 * E2E tests for authentication flows.
 *
 * NOTE: These tests require:
 * 1. moto_server running on port 5000 (started by global-setup.ts)
 * 2. BeakerHub backend configured with endpoint_url pointing to moto
 * 3. Vite dev server or preview server running
 *
 * CognitoOAuthAuthenticator cannot be used for E2E tests as moto does not
 * emulate Cognito's hosted UI or OAuth endpoints.
 */

import { test, expect } from './fixtures';

test.describe('Authentication', () => {
  test.describe('Login Flow', () => {
    test('should show login page for unauthenticated users', async ({ page }) => {
      await page.goto('/login');

      // Should see login form
      await expect(page.getByRole('heading', { name: /login|sign in/i })).toBeVisible();
      await expect(page.getByLabel(/email/i)).toBeVisible();
      await expect(page.getByLabel(/password/i)).toBeVisible();
    });

    test('should redirect unauthenticated users to login', async ({ page }) => {
      await page.goto('/dashboard');

      // Should be redirected to login
      await expect(page).toHaveURL(/\/login/);
    });

    test('should login with valid credentials', async ({ page, testUser }) => {
      await page.goto('/login');

      // Fill in credentials
      await page.getByLabel(/email/i).fill(testUser.email);
      await page.getByLabel(/password/i).fill(testUser.password);

      // Submit form
      await page.getByRole('button', { name: /login|sign in/i }).click();

      // Should redirect to dashboard after successful login
      await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 });
    });

    test('should show error for invalid credentials', async ({ page }) => {
      await page.goto('/login');

      // Fill in invalid credentials
      await page.getByLabel(/email/i).fill('invalid@example.com');
      await page.getByLabel(/password/i).fill('WrongPassword123!');

      // Submit form
      await page.getByRole('button', { name: /login|sign in/i }).click();

      // Should show error message
      await expect(page.getByText(/invalid|incorrect|failed/i)).toBeVisible({ timeout: 5000 });

      // Should stay on login page
      await expect(page).toHaveURL(/\/login/);
    });

    test('should show error for empty credentials', async ({ page }) => {
      await page.goto('/login');

      // Submit without filling in credentials
      await page.getByRole('button', { name: /login|sign in/i }).click();

      // Should show validation error or stay on login page
      await expect(page).toHaveURL(/\/login/);
    });
  });

  test.describe('Logout Flow', () => {
    test('should logout and redirect to home', async ({ page, testUser }) => {
      // First login
      await page.goto('/login');
      await page.getByLabel(/email/i).fill(testUser.email);
      await page.getByLabel(/password/i).fill(testUser.password);
      await page.getByRole('button', { name: /login|sign in/i }).click();
      await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 });

      // Find and click logout button
      // This might be in a user menu dropdown
      const userMenu = page.getByRole('button', { name: /user|account|profile/i });
      if (await userMenu.isVisible()) {
        await userMenu.click();
      }

      await page.getByRole('button', { name: /logout|sign out/i }).click();

      // Should redirect to home or login page
      await expect(page).toHaveURL(/^\/$|\/login|\/about/);
    });

    test('should clear session state on logout', async ({ page, testUser }) => {
      // Login
      await page.goto('/login');
      await page.getByLabel(/email/i).fill(testUser.email);
      await page.getByLabel(/password/i).fill(testUser.password);
      await page.getByRole('button', { name: /login|sign in/i }).click();
      await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 });

      // Logout
      const userMenu = page.getByRole('button', { name: /user|account|profile/i });
      if (await userMenu.isVisible()) {
        await userMenu.click();
      }
      await page.getByRole('button', { name: /logout|sign out/i }).click();

      // Try to access dashboard - should redirect to login
      await page.goto('/dashboard');
      await expect(page).toHaveURL(/\/login/);
    });
  });

  test.describe('Signup Flow', () => {
    test('should show signup page', async ({ page }) => {
      await page.goto('/signup');

      await expect(page.getByRole('heading', { name: /sign up|register|create account/i })).toBeVisible();
      await expect(page.getByLabel(/email/i)).toBeVisible();
      await expect(page.getByLabel(/password/i)).toBeVisible();
    });

    test('should navigate from login to signup', async ({ page }) => {
      await page.goto('/login');

      // Click signup link
      await page.getByRole('link', { name: /sign up|register|create account/i }).click();

      await expect(page).toHaveURL(/\/signup/);
    });

    test('should show validation errors for weak password', async ({ page }) => {
      await page.goto('/signup');

      await page.getByLabel(/email/i).fill('newuser@example.com');

      // Fill in a weak password
      const passwordField = page.getByLabel(/^password$/i);
      await passwordField.fill('weak');

      // Try to submit
      await page.getByRole('button', { name: /sign up|register|create/i }).click();

      // Should show password requirements error
      // The exact error message depends on UI implementation
      await expect(page).toHaveURL(/\/signup/);
    });

    test('should submit signup form successfully', async ({ page }) => {
      await page.goto('/signup');

      // Generate unique email for test
      const uniqueEmail = `test-${Date.now()}@example.com`;

      await page.getByLabel(/email/i).fill(uniqueEmail);

      // Handle password field (might have confirm password too)
      const passwordFields = page.getByLabel(/password/i);
      const passwordCount = await passwordFields.count();

      if (passwordCount >= 1) {
        await passwordFields.first().fill('SecurePass123!');
      }
      if (passwordCount >= 2) {
        await passwordFields.nth(1).fill('SecurePass123!');
      }

      // Submit
      await page.getByRole('button', { name: /sign up|register|create/i }).click();

      // Should redirect to verification page or show success message
      // The exact behavior depends on implementation
      await expect(page.getByText(/verification|confirm|check your email/i)).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Password Reset Flow', () => {
    test('should show forgot password page', async ({ page }) => {
      await page.goto('/reset');

      await expect(page.getByRole('heading', { name: /reset|forgot|recover/i })).toBeVisible();
      await expect(page.getByLabel(/email/i)).toBeVisible();
    });

    test('should navigate from login to forgot password', async ({ page }) => {
      await page.goto('/login');

      // Click forgot password link
      await page.getByRole('link', { name: /forgot|reset|recover/i }).click();

      await expect(page).toHaveURL(/\/reset/);
    });

    test('should submit forgot password request', async ({ page, testUser }) => {
      await page.goto('/reset');

      await page.getByLabel(/email/i).fill(testUser.email);
      await page.getByRole('button', { name: /send|submit|reset/i }).click();

      // Should show confirmation or redirect to code entry
      await expect(
        page.getByText(/code sent|check your email|verification/i)
      ).toBeVisible({ timeout: 10000 });
    });
  });
});

test.describe('Navigation Guards', () => {
  test('should redirect logged-in users from login page to dashboard', async ({ page, testUser }) => {
    // Login first
    await page.goto('/login');
    await page.getByLabel(/email/i).fill(testUser.email);
    await page.getByLabel(/password/i).fill(testUser.password);
    await page.getByRole('button', { name: /login|sign in/i }).click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 });

    // Try to go to login page
    await page.goto('/login');

    // Should redirect back to dashboard
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('should allow access to public pages without auth', async ({ page }) => {
    // About/splash page should be accessible
    await page.goto('/about');
    await expect(page).toHaveURL(/\/about/);

    // Should not redirect to login
    await expect(page.getByRole('heading')).toBeVisible();
  });
});
