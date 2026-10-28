import type { components } from '../../api/schema'

export type ChatCitation = components['schemas']['ChatCitationEvent']

export interface ChatAnswer {
  status: 'idle' | 'streaming' | 'done' | 'error'
  question?: string
  text: string
  citations: ChatCitation[]
  modelId?: string
  found?: boolean
  error?: string
}

/** Asks a question and follows the streamed answer (FE-12). */
export function useChatStream(): { answer: ChatAnswer; ask: (question: string) => void } {
  throw new Error('not implemented')
}
