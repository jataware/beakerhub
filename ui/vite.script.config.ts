import { fileURLToPath, URL } from 'node:url';
import path from 'path';

import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import vueJsx from '@vitejs/plugin-vue-jsx';
import vueDevTools from 'vite-plugin-vue-devtools';
import topLevelAwait from 'vite-plugin-top-level-await';


// const beakerKernelProxyConfig = {
//   target: `${BeakerKernelHost}/`,
//   xfwd: true,
//   changeOrigin: false,
//   ws: true,  // Enable WebSocket proxying for kernel channels
// };

const BeakerhubProxy = process.env.BEAKERHUB_URL || 'http://localhost:8000';

import parentConfig from "./vite.config";
console.log(parentConfig);

parentConfig.server.watch = null;
console.log(parentConfig);

export default parentConfig;
