import { createParser } from 'eventsource-parser'
import { useCallback, useEffect, useReducer, useRef } from 'react'

import { apiClient } from '../../api/client'
import type { components } from '../../api/schema'

type Schemas = components['schemas']
export type ChatCitation = Schemas['ChatCitationEvent']
type ChatEvent = Schemas['ChatEvent']
type ChatErrorCode = Schemas['ChatErrorEvent']['code']

export interface ChatAnswer {
  status: 'idle' | 'streaming' | 'done' | 'error'
  question?: string
  text: string
  citations: ChatCitation[]
  modelId?: string
  found?: boolean
  isTestModel?: boolean
  error?: string
}

type Action =
  | { type: 'asked'; question: string }
  | { type: 'event'; event: ChatEvent }
  | { type: 'failed'; message: string }

const IDLE: ChatAnswer = { status: 'idle', text: '', citations: [] }

function reduce(answer: ChatAnswer, action: Action): ChatAnswer {
  switch (action.type) {
    case 'asked':
      return { status: 'streaming', question: action.question, text: '', citations: [] }
    case 'failed':
      return { ...answer, status: 'error', error: action.message }
    case 'event':
      switch (action.event.type) {
        case 'text':
          return { ...answer, text: answer.text + action.event.text }
        case 'citation':
          return { ...answer, citations: [...answer.citations, action.event] }
        case 'discard':
          return { ...answer, text: '', citations: [] }
        case 'error':
          return {
            ...answer,
            status: 'error',
            text: '',
            citations: [],
            error: errorMessage(action.event.code, action.event.message),
          }
        case 'end':
          return {
            ...answer,
            // An error event already ended the answer; the end event only closes the stream.
            status: answer.status === 'error' ? 'error' : 'done',
            modelId: action.event.model_id,
            found: action.event.found,
            isTestModel: action.event.is_test_model,
          }
      }
  }
}

/** What the user reads when the model gives no answer (F-06). */
function errorMessage(code: ChatErrorCode, message: string): string {
  switch (code) {
    case 'invalid_answer':
      return 'The model could not produce a valid answer. Try asking again.'
    case 'model_unreachable':
      return `The language model is not reachable. ${message}`
    case 'model_timeout':
      return `The language model took too long to answer. ${message}`
    case 'model_error':
      return `The model server failed to answer. ${message}`
  }
}

function isChatEvent(value: unknown): value is ChatEvent {
  return (
    typeof value === 'object' &&
    value !== null &&
    'type' in value &&
    (value.type === 'text' ||
      value.type === 'discard' ||
      value.type === 'error' ||
      value.type === 'citation' ||
      value.type === 'end')
  )
}

async function streamAnswer(
  question: string,
  signal: AbortSignal,
  onEvent: (event: ChatEvent) => void,
): Promise<void> {
  const { response } = await apiClient.POST('/api/chat', {
    body: { question },
    parseAs: 'stream',
    signal,
  })
  if (!response.ok || !response.body) {
    throw new Error(`The answer failed with HTTP ${String(response.status)}`)
  }
  // Set from the parser's callback, so it lives in an object the type checker does not narrow.
  const progress = { ended: false }
  const parser = createParser({
    onEvent: ({ data }) => {
      const event: unknown = JSON.parse(data)
      if (isChatEvent(event)) {
        progress.ended ||= event.type === 'end'
        onEvent(event)
      }
    },
  })
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  for (;;) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    parser.feed(value)
  }
  if (!progress.ended) {
    throw new Error('The answer stopped before it was complete.')
  }
}

/** Asks a question and follows the streamed answer (FE-12). A new question cancels the last one. */
export function useChatStream(): { answer: ChatAnswer; ask: (question: string) => void } {
  const [answer, dispatch] = useReducer(reduce, IDLE)
  const current = useRef<AbortController | null>(null)

  useEffect(() => () => current.current?.abort(), [])

  const ask = useCallback((question: string) => {
    current.current?.abort()
    const controller = new AbortController()
    current.current = controller
    dispatch({ type: 'asked', question })
    streamAnswer(question, controller.signal, (event) => {
      dispatch({ type: 'event', event })
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) {
        dispatch({
          type: 'failed',
          message: error instanceof Error ? error.message : String(error),
        })
      }
    })
  }, [])

  return { answer, ask }
}
