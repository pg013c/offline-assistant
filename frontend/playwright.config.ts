import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig, devices } from '@playwright/test'

// Ports away from the development defaults, so a running `make dev` does not interfere.
const API_PORT = process.env.E2E_API_PORT ?? '8011'
const UI_PORT = process.env.E2E_UI_PORT ?? '5181'
// Every run starts with an empty data directory. The config is loaded by every Playwright
// process; the environment variable makes them share one directory, removed in global teardown.
// The parsing models from `make models`; `make` passes ASSISTANT_MODELS_DIR.
const MODELS_DIR =
  process.env.ASSISTANT_MODELS_DIR ?? fileURLToPath(new URL('../data/models', import.meta.url))
const DATA_DIR = (process.env.E2E_DATA_DIR ??= mkdtempSync(
  join(tmpdir(), 'offline-assistant-e2e-'),
))

export default defineConfig({
  testDir: './e2e',
  globalTeardown: './e2e/global-teardown.ts',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: `http://127.0.0.1:${UI_PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `uv run --directory ../backend uvicorn assistant.app:main --factory --port ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      env: {
        ASSISTANT_DATA_DIR: DATA_DIR,
        ASSISTANT_MODELS_DIR: MODELS_DIR,
        // A collection of its own: restore on the empty data directory clears it, and must not
        // clear the one `make dev` uses.
        ASSISTANT_QDRANT_COLLECTION_PREFIX: 'e2e',
      },
      reuseExistingServer: false,
    },
    {
      command: `pnpm exec vite --host 127.0.0.1 --port ${UI_PORT} --strictPort`,
      url: `http://127.0.0.1:${UI_PORT}`,
      env: { API_PORT },
      reuseExistingServer: false,
    },
  ],
})
