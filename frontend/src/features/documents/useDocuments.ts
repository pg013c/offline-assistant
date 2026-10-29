import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiClient } from '../../api/client'
import type { components } from '../../api/schema'

export type DocumentSummary = components['schemas']['DocumentResponse']

const DOCUMENTS_KEY = ['documents'] as const
const POLL_INTERVAL_MS = 2000

/** The document list; it refreshes while any document is still being parsed. */
export function useDocuments(pollIntervalMs: number = POLL_INTERVAL_MS) {
  return useQuery({
    queryKey: DOCUMENTS_KEY,
    refetchInterval: (query) =>
      query.state.data?.some((document) => document.status === 'processing')
        ? pollIntervalMs
        : false,
    queryFn: async (): Promise<DocumentSummary[]> => {
      const { data, response } = await apiClient.GET('/api/documents')
      if (data === undefined) {
        throw new Error(`Loading documents failed with HTTP ${String(response.status)}`)
      }
      return data
    },
  })
}

/** Uploads one file; the error message is the API's explanation when it rejects the file. */
export function useUploadDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (file: File): Promise<DocumentSummary> => {
      const { data, error } = await apiClient.POST('/api/documents', {
        // The schema types the binary field as a string; the real body is built below.
        body: { file: '' },
        bodySerializer: () => {
          const form = new FormData()
          form.append('file', file)
          return form
        },
      })
      if (data === undefined) {
        throw new Error(messageOf(error) ?? `Uploading ${file.name} failed`)
      }
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: DOCUMENTS_KEY }),
  })
}

function messageOf(error: unknown): string | undefined {
  if (typeof error === 'object' && error !== null && 'message' in error) {
    const { message } = error
    return typeof message === 'string' ? message : undefined
  }
  return undefined
}
