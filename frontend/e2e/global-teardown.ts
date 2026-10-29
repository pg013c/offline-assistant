import { rmSync } from 'node:fs'

/** Removes the run's temporary data directory created in playwright.config.ts. */
export default function globalTeardown(): void {
  const dataDir = process.env.E2E_DATA_DIR
  if (dataDir) {
    rmSync(dataDir, { recursive: true, force: true })
  }
}
