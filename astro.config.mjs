// @ts-check
import { defineConfig } from 'astro/config';
import node from '@astrojs/node';

// https://astro.build/config
export default defineConfig({
  output: 'server',
  adapter: node({
    mode: 'standalone',
  }),
  vite: {
    optimizeDeps: {
      exclude: ['better-sqlite3'],
    },
    server: {
      allowedHosts: ['todo.brooksmcmillin.com'],
    },
  },
  security: {
    checkOrigin: false,
  },
  server: {
    allowedHosts: ['todo.brooksmcmillin.com'],
  },
});
