import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach } from 'vitest'

import { server } from './server'

// Listen before any test module loads, so clients created at import time use the mocked fetch.
server.listen({ onUnhandledFrame: 'error' })

afterEach(() => {
  cleanup()
  server.resetHandlers()
})

afterAll(() => {
  server.close()
})
