import { useQuery } from '@tanstack/react-query'

import { apiClient } from '../../api/client'
import type { components } from '../../api/schema'

export type Health = components['schemas']['HealthResponse']

const REFRESH_INTERVAL_MS = 30_000
// One quick retry: a status indicator should report an outage within a second, not after backoff.
const RETRIES = 1
const RETRY_DELAY_MS = 300

/** Backend health, refreshed periodically so the shell notices when the API goes down. */
export function useApiHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: async (): Promise<Health> => {
      const { data, response } = await apiClient.GET('/api/health')
      if (data === undefined) {
        throw new Error(`Health check failed with HTTP ${String(response.status)}`)
      }
      return data
    },
    refetchInterval: REFRESH_INTERVAL_MS,
    retry: RETRIES,
    retryDelay: RETRY_DELAY_MS,
  })
}
