import { useQuery } from '@tanstack/react-query'

import { apiClient } from '../../api/client'
import type { components } from '../../api/schema'

export type ModelChoice = components['schemas']['ModelChoiceResponse']

// How often the list is asked for again, so a model whose server stops leaves it (F-09b).
export const MODELS_REFRESH_MS = 10_000

/** The models the API can answer with now (F-08), refreshed periodically (F-09b). */
export function useModels() {
  return useQuery({
    queryKey: ['models'],
    queryFn: async (): Promise<ModelChoice[]> => {
      const { data, response } = await apiClient.GET('/api/models')
      if (data === undefined) {
        throw new Error(`Loading models failed with HTTP ${String(response.status)}`)
      }
      return data
    },
    refetchInterval: MODELS_REFRESH_MS,
  })
}
