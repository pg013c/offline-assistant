import createClient from 'openapi-fetch'

import type { paths } from './schema'

/**
 * The only way the UI talks to the backend (FE-10). Types come from the generated schema;
 * regenerate with `make api-client` after an API change.
 */
export const apiClient = createClient<paths>({ baseUrl: window.location.origin })
