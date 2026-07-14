import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

const backendTarget = 'http://localhost:9001';
const proxy = {
  '/api': backendTarget,
  '/artifacts': backendTarget
};

export default defineConfig({
  plugins: [vue()],
  root: 'web/frontend',
  server: {
    port: 9000,
    strictPort: true,
    proxy
  },
  preview: {
    port: 9000,
    strictPort: true,
    proxy
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
});
