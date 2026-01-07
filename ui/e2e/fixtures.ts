/**
 * Playwright test fixtures for E2E tests.
 */

import { test as base, expect } from '@playwright/test';

// Test user credentials from global setup
export interface TestUser {
  email: string;
  password: string;
}

// Extended test fixture with test user data
export const test = base.extend<{ testUser: TestUser }>({
  testUser: async ({}, use) => {
    const testUser: TestUser = {
      email: process.env.E2E_TEST_EMAIL || 'e2e-test@example.com',
      password: process.env.E2E_TEST_PASSWORD || 'TestPass123!',
    };
    await use(testUser);
  },
});

export { expect };
