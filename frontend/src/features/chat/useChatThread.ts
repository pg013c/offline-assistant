import type { ChatAnswer } from './useChatStream'

export interface ChatTurn {
  question: string
  model?: string
  answer: ChatAnswer
}

export interface ChatThread {
  turns: ChatTurn[]
  ask: (question: string, model?: string) => void
}

/** The questions of this session with their streamed answers (F-08). */
export function useChatThread(): ChatThread {
  throw new Error('not implemented')
}
