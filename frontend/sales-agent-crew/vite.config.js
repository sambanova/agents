import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import VueDevTools from 'vite-plugin-vue-devtools';

const plugins = [vue()];
if (process.env.NODE_ENV !== 'production') {
  plugins.push(VueDevTools());
}

export default defineConfig({
  plugins,
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    // Basic optimizations
    target: 'es2015',
    minify: 'esbuild',
    rollupOptions: {
      output: {
        // Simple chunk splitting
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
          ui: ['@headlessui/vue', '@heroicons/vue'],
        },
      },
    },
    sourcemap: false,
    cssCodeSplit: true,
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        ws: true, // Enable WebSocket proxying
      },
    },
  },
});
