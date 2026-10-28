import { setupServer } from 'msw/node'

/** Mock HTTP server shared by all UI tests; each test adds its handlers with `server.use`. */
export const server = setupServer()
