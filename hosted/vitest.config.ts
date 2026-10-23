import { defineConfig } from 'vitest/config';
export default defineConfig({ test: { include: ['hosted/**/*.test.ts'], environment: 'node' } });
