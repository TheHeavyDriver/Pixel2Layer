import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    environmentOptions: {
      jsdom: { url: 'http://localhost:3000' },
    },
    globals: true,
    setupFiles: ['vitest-canvas-mock', './src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
  resolve: {
    alias: {
      '@': new URL('./src', import.meta.url).pathname,
      '@pixel2layer/schema': new URL('../../packages/schema/src/index.ts', import.meta.url).pathname,
    },
  },
});