import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    strictPort: true,
    proxy: {
      '/api': `http://127.0.0.1:${process.env.API_PORT ?? '8000'}`,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Browser journeys run with Playwright (`make e2e`), not Vitest.
    exclude: ['e2e/**', 'node_modules/**'],
  },
})
