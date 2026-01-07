import { fileURLToPath, URL } from 'node:url';
import path from 'path';

import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import vueJsx from '@vitejs/plugin-vue-jsx';
import vueDevTools from 'vite-plugin-vue-devtools';
import topLevelAwait from 'vite-plugin-top-level-await';


const BeakerhubProxy = process.env.BEAKERHUB_URL || 'http://localhost:8000';

// https://vite.dev/config/
export default defineConfig({
  define: {
    global: 'globalThis',
  },
  server: {
    host: '0.0.0.0',
    port: 8080,
    allowedHosts: ["localhost", ".localhost", ".beakerhub.internal"],

    proxy: {
      // Routes to BeakerHub service (port 8000) - auth, login, and context metadata
      // BeakerHub now serves from root (/) by default
      '/api': BeakerhubProxy,
      '/session': BeakerhubProxy,
      '/health': BeakerhubProxy,

    },
  },
  plugins: [
    vue(),
    vueJsx(),
    vueDevTools(),
    topLevelAwait(),
    {
      name: "sanitize-eval",
      transform(src, id) {
        // Custom inline plugin to replace 'eval()' calls with 'console.debug()'.
        if (id.includes("@jupyterlab/coreutils/lib/pageconfig")) {
          return src.replaceAll(/\beval\b/g, 'console.debug');
        }
      }
    }
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      'node-fetch': path.resolve(require.resolve('isomorphic-fetch'), '..'),
      'path': path.resolve(require.resolve('path-browserify'), '..'),
      'buffer': 'buffer',
    },
  },
  build: {
    target: 'esnext',
    assetsDir: 'beakerhub/static/',
    outDir: 'dist/',
    rollupOptions: {
      onwarn(warning, warn) {
        // Custom warning suppression for known issues that are not a concern
        if (
          (warning.code === "MISSING_EXPORT" && warning.message.includes('json5') && warning.message.includes('@jupyterlab/settingregistry'))
        ) {
          return;
        }
        warn(warning);
      },
    }
  },
  optimizeDeps: {
    include: ['buffer'],
    esbuildOptions: {
      target: 'esnext',
      define: {
        global: 'globalThis',
      },
    },
  }
})
