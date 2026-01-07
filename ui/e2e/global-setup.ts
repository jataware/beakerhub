/**
 * Playwright global setup - starts moto_server for Cognito mocking.
 *
 * This setup:
 * 1. Starts moto_server as a subprocess on port 5000
 * 2. Creates a Cognito user pool and app client
 * 3. Creates test users for E2E tests
 *
 * NOTE: The BeakerHub backend must be configured with:
 *   c.CognitoBotoAuthenticator.endpoint_url = "http://localhost:5000"
 */

import { spawn, ChildProcess } from 'child_process';
import { promisify } from 'util';

const sleep = promisify(setTimeout);

let motoProcess: ChildProcess | null = null;

// Store for test data to be used by tests
interface TestConfig {
  motoEndpoint: string;
  userPoolId: string;
  clientId: string;
  clientSecret: string;
  testUser: {
    email: string;
    password: string;
  };
}

async function waitForMotoServer(port: number, maxAttempts = 30): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const response = await fetch(`http://localhost:${port}/moto-api/`);
      if (response.ok) {
        return true;
      }
    } catch {
      // Server not ready yet
    }
    await sleep(100);
  }
  return false;
}

async function setupCognitoPool(): Promise<TestConfig> {
  const motoEndpoint = 'http://localhost:5000';

  // Use AWS SDK to create user pool via moto
  // Note: In a real setup, you'd use @aws-sdk/client-cognito-identity-provider
  // For now, we'll use fetch to call moto's API directly

  const region = 'us-east-1';

  // Create User Pool
  const createPoolResponse = await fetch(motoEndpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': 'AWSCognitoIdentityProviderService.CreateUserPool',
    },
    body: JSON.stringify({
      PoolName: 'e2e-test-pool',
      Policies: {
        PasswordPolicy: {
          MinimumLength: 8,
          RequireUppercase: true,
          RequireLowercase: true,
          RequireNumbers: true,
          RequireSymbols: false,
        },
      },
      AutoVerifiedAttributes: ['email'],
      UsernameAttributes: ['email'],
    }),
  });

  const poolData = await createPoolResponse.json();
  const userPoolId = poolData.UserPool.Id;

  // Create App Client
  const createClientResponse = await fetch(motoEndpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': 'AWSCognitoIdentityProviderService.CreateUserPoolClient',
    },
    body: JSON.stringify({
      UserPoolId: userPoolId,
      ClientName: 'e2e-test-client',
      GenerateSecret: true,
      ExplicitAuthFlows: ['ALLOW_USER_PASSWORD_AUTH', 'ALLOW_REFRESH_TOKEN_AUTH'],
    }),
  });

  const clientData = await createClientResponse.json();
  const clientId = clientData.UserPoolClient.ClientId;
  const clientSecret = clientData.UserPoolClient.ClientSecret;

  // Create test user
  const testEmail = 'e2e-test@example.com';
  const testPassword = 'TestPass123!';

  await fetch(motoEndpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': 'AWSCognitoIdentityProviderService.AdminCreateUser',
    },
    body: JSON.stringify({
      UserPoolId: userPoolId,
      Username: testEmail,
      UserAttributes: [
        { Name: 'email', Value: testEmail },
        { Name: 'email_verified', Value: 'true' },
      ],
      MessageAction: 'SUPPRESS',
    }),
  });

  // Set password to make user confirmed
  await fetch(motoEndpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': 'AWSCognitoIdentityProviderService.AdminSetUserPassword',
    },
    body: JSON.stringify({
      UserPoolId: userPoolId,
      Username: testEmail,
      Password: testPassword,
      Permanent: true,
    }),
  });

  return {
    motoEndpoint,
    userPoolId,
    clientId,
    clientSecret,
    testUser: {
      email: testEmail,
      password: testPassword,
    },
  };
}

async function globalSetup() {
  console.log('Starting moto_server for E2E tests...');

  // Start moto_server
  motoProcess = spawn('moto_server', ['-p', '5000'], {
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: true,
  });

  // Store PID for teardown
  if (motoProcess.pid) {
    process.env.MOTO_PID = motoProcess.pid.toString();
  }

  motoProcess.stdout?.on('data', (data) => {
    if (process.env.DEBUG) {
      console.log(`moto: ${data}`);
    }
  });

  motoProcess.stderr?.on('data', (data) => {
    if (process.env.DEBUG) {
      console.error(`moto error: ${data}`);
    }
  });

  // Wait for moto to be ready
  const ready = await waitForMotoServer(5000);
  if (!ready) {
    throw new Error('moto_server failed to start within timeout');
  }

  console.log('moto_server is ready');

  // Setup Cognito pool and test users
  try {
    const config = await setupCognitoPool();
    console.log('Cognito test pool created');
    console.log(`  User Pool ID: ${config.userPoolId}`);
    console.log(`  Client ID: ${config.clientId}`);
    console.log(`  Test User: ${config.testUser.email}`);

    // Store config for tests to access
    process.env.E2E_USER_POOL_ID = config.userPoolId;
    process.env.E2E_CLIENT_ID = config.clientId;
    process.env.E2E_CLIENT_SECRET = config.clientSecret;
    process.env.E2E_TEST_EMAIL = config.testUser.email;
    process.env.E2E_TEST_PASSWORD = config.testUser.password;
  } catch (error) {
    console.error('Failed to setup Cognito pool:', error);
    throw error;
  }
}

export default globalSetup;
