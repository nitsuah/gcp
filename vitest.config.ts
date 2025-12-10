import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Specify test file patterns
    include: ['**/*.{test,spec}.{ts,js}'],
    // Exclude directories from test collection
    exclude: ['dist', 'build', 'node_modules', '.git', 'coverage'],
    // Coverage configuration
    coverage: {
      provider: 'c8',
      reportsDirectory: 'coverage',
      // Set coverage threshold (adjust as needed)
      lines: 80,
      functions: 80,
      branches: 80,
      statements: 80,
      // Exclude files from coverage
      exclude: [
        '**/test/**',
        '**/*.test.*',
        '**/*.spec.*',
        '**/setup.*',
        '**/conftest.*'
      ]
    }
  }
});