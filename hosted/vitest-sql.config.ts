import { defineConfig } from 'vitest/config';
export default defineConfig({ test: {
  include: ['hosted/history-sql.test.mjs'], environment: 'node', testTimeout: 30000,
} });
