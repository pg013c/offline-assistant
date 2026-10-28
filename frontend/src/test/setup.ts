/// <reference types="node" />
import '@testing-library/jest-dom/vitest'
import { Blob as NodeBlob, File as NodeFile } from 'node:buffer'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach } from 'vitest'

import { server } from './server'

// Vitest's jsdom environment converts jsdom's FormData and Blob for Node's fetch, but loses file
// bytes and names on the way (vitest 5.0, jsdom 30.1). Tests use Node's own Request, FormData,
// File and Blob instead, so multipart uploads reach the mocked API as a browser would send them.
const NativeRequest = Object.getPrototypeOf(Request) as typeof Request
const probe = new NativeRequest('http://localhost/', {
  method: 'POST',
  body: new URLSearchParams(),
})
const NativeFormData = (await probe.formData()).constructor
Object.assign(globalThis, {
  Request: NativeRequest,
  FormData: NativeFormData,
  File: NodeFile,
  Blob: NodeBlob,
})

// Listen before any test module loads, so clients created at import time use the mocked fetch.
server.listen({ onUnhandledFrame: 'error' })

afterEach(() => {
  cleanup()
  server.resetHandlers()
})

afterAll(() => {
  server.close()
})
