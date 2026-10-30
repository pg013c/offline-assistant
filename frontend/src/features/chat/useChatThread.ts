import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useReducer, useRef } from 'react'

import { NOTES_KEY } from '../notes/useNotes'

import {
  reduceAnswer,
  STREAMING,
  streamAnswer,
  type AnswerAction,
  type ChatAnswer,
} from './chatStream'

export interface ChatTurn {
  question: string
  model?: string | undefined
  answer: ChatAnswer
}

export interface ChatThread {
  turns: ChatTurn[]
  ask: (question: string, model?: string) => void
}

type ThreadAction =
  | { type: 'asked'; question: string; model: string | undefined }
  | { type: 'answer'; turn: number; action: AnswerAction }

function reduce(turns: ChatTurn[], action: ThreadAction): ChatTurn[] {
  switch (action.type) {
    case 'asked':
      return [
        ...turns.map((turn) =>
          turn.answer.status === 'streaming'
            ? { ...turn, answer: { ...turn.answer, status: 'stopped' as const } }
            : turn,
        ),
        { question: action.question, model: action.model, answer: STREAMING },
      ]
    case 'answer':
      return turns.map((turn, index) =>
        // A stopped turn takes nothing more from its stream.
        index === action.turn && turn.answer.status !== 'stopped'
          ? { ...turn, answer: reduceAnswer(turn.answer, action.action) }
          : turn,
      )
  }
}

/**
 * The questions of this session with their streamed answers, in order (F-08). Each question
 * gets its own turn; a new question stops the answer still being written. Nothing is stored.
 */
export function useChatThread(): ChatThread {
  const [turns, dispatch] = useReducer(reduce, [])
  const current = useRef<AbortController | null>(null)
  const count = useRef(0)

  useEffect(() => () => current.current?.abort(), [])

  const queryClient = useQueryClient()

  const ask = useCallback(
    (question: string, model?: string) => {
      current.current?.abort()
      const controller = new AbortController()
      current.current = controller
      const turn = count.current
      count.current += 1
      dispatch({ type: 'asked', question, model })
      streamAnswer(question, model, controller.signal, (event) => {
        dispatch({ type: 'answer', turn, action: { type: 'event', event } })
        if (event.type === 'note') {
          // The library lists the new note without a reload.
          void queryClient.invalidateQueries({ queryKey: NOTES_KEY })
        }
      }).catch((error: unknown) => {
        if (!controller.signal.aborted) {
          const message = error instanceof Error ? error.message : String(error)
          dispatch({ type: 'answer', turn, action: { type: 'failed', message } })
        }
      })
    },
    [queryClient],
  )

  return { turns, ask }
}
