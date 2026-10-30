import { fileURLToPath, URL } from 'node:url';
import path from 'path';

import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import vueJsx from '@vitejs/plugin-vue-jsx';
import vueDevTools from 'vite-plugin-vue-devtools';


const BeakerhubProxy = process.env.BEAKERHUB_URL || 'http://localhost:8000';
const baseUrl = process.env.BASE_URL || '/';
const proxies = {
  [`${baseUrl}api`]: BeakerhubProxy, 
  [`${baseUrl}session`]: BeakerhubProxy, 
  [`${baseUrl}health`]: BeakerhubProxy,
};

// https://vite.dev/config/
export default defineConfig({
  base: baseUrl,
  define: {
    global: 'globalThis',
  },
  server: {
    host: '0.0.0.0',
    port: 8080,
    allowedHosts: ["localhost", ".localhost", ".beakerhub.internal"],

    proxy: proxies,
  },
  plugins: [
    vue(),
    vueJsx(),
    vueDevTools(),
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
