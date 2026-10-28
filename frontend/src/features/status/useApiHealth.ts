import { useQuery } from '@tanstack/react-query'

import { apiClient } from '../../api/client'
import type { components } from '../../api/schema'

export type Health = components['schemas']['HealthResponse']

const REFRESH_INTERVAL_MS = 30_000

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
  })
}
