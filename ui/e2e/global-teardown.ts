/**
 * Playwright global teardown - stops moto_server.
 */

import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

async function globalTeardown() {
  const motoPid = process.env.MOTO_PID;

  if (motoPid) {
    console.log(`Stopping moto_server (PID: ${motoPid})...`);
    try {
      // Kill the moto_server process and its children
      await execAsync(`kill -TERM -${motoPid} 2>/dev/null || kill -TERM ${motoPid} 2>/dev/null || true`);
      console.log('moto_server stopped');
    } catch (error) {
      // Process may have already exited
      console.log('moto_server process already stopped or not found');
    }
  }
}

export default globalTeardown;
