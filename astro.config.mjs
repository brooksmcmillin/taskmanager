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
      exclude: ['better-sqlite3', 'bcrypt'],
    },
    build: {
      rollupOptions: {
        external: ['bcrypt'],
      },
    },
    ssr: {
      external: ['bcrypt'],
    },
    server: {
      allowedHosts: ['todo.brooksmcmillin.com'],
    },
  },
  security: {
    checkOrigin: true,
  },
  server: {
    allowedHosts: ['todo.brooksmcmillin.com'],
  },
});
