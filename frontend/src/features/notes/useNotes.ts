import { useQuery } from '@tanstack/react-query'

import { apiClient } from '../../api/client'
import type { components } from '../../api/schema'

export type NoteSummary = components['schemas']['NoteSummary']
export type NoteDetail = components['schemas']['NoteDetail']

/** The notes query; the chat invalidates it when the agent saves a note (F-08). */
export const NOTES_KEY = ['notes'] as const

/** The saved notes, newest first. */
export function useNotes() {
  return useQuery({
    queryKey: NOTES_KEY,
    queryFn: async (): Promise<NoteSummary[]> => {
      const { data, response } = await apiClient.GET('/api/notes')
      if (data === undefined) {
        throw new Error(`Loading notes failed with HTTP ${String(response.status)}`)
      }
      return data
    },
  })
}

/** One note with its text and sources, once one is chosen. */
export function useNote(noteId: string | null) {
  return useQuery({
    queryKey: [...NOTES_KEY, noteId],
    enabled: noteId !== null,
    queryFn: async (): Promise<NoteDetail> => {
      const { data, response } = await apiClient.GET('/api/notes/{note_id}', {
        params: { path: { note_id: noteId ?? '' } },
      })
      if (data === undefined) {
        throw new Error(`Loading the note failed with HTTP ${String(response.status)}`)
      }
      return data
    },
  })
}
