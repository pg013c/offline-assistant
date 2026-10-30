import { useQuery } from '@tanstack/react-query'

import { apiClient } from '../../api/client'
import type { components } from '../../api/schema'

export type ModelChoice = components['schemas']['ModelChoiceResponse']

/** The models the API can answer with now (F-08). */
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
  })
}
