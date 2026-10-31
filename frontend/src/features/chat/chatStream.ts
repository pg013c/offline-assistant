import { createParser } from 'eventsource-parser'

import { apiClient } from '../../api/client'
import type { components } from '../../api/schema'

type Schemas = components['schemas']
export type ChatCitation = Schemas['ChatCitationEvent']
export type ChatTool = Pick<Schemas['ChatToolEvent'], 'name' | 'arguments'>
export type ChatNote = Pick<Schemas['ChatNoteEvent'], 'id' | 'title'>
type ChatEvent = Schemas['ChatEvent']
type ChatErrorCode = Schemas['ChatErrorEvent']['code']

export interface ChatAnswer {
  // `stopped`: a newer question cut the answer short.
  status: 'streaming' | 'done' | 'error' | 'stopped'
  text: string
  citations: ChatCitation[]
  // The agent's tool calls, in order, before the answer text (F-07).
  tools: ChatTool[]
  // Notes the agent saved (F-07a).
  notes: ChatNote[]
  modelId?: string
  found?: boolean
  isTestModel?: boolean
  error?: string
}

export type AnswerAction = { type: 'event'; event: ChatEvent } | { type: 'failed'; message: string }

/** An answer before its first event. */
export const STREAMING: ChatAnswer = {
  status: 'streaming',
  text: '',
  citations: [],
  tools: [],
  notes: [],
}

/** The answer after one more event of its stream, or after the stream failed. */
export function reduceAnswer(answer: ChatAnswer, action: AnswerAction): ChatAnswer {
  switch (action.type) {
    case 'failed':
      return { ...answer, status: 'error', error: action.message }
    case 'event':
      switch (action.event.type) {
        case 'note':
          return {
            ...answer,
            notes: [...answer.notes, { id: action.event.id, title: action.event.title }],
          }
        case 'tool':
          return {
            ...answer,
            tools: [
              ...answer.tools,
              { name: action.event.name, arguments: action.event.arguments },
            ],
          }
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
    case 'invalid_tool_call':
      return `The model could not use its tools correctly. ${message}`
  }
}

function isChatEvent(value: unknown): value is ChatEvent {
  return (
    typeof value === 'object' &&
    value !== null &&
    'type' in value &&
    (value.type === 'tool' ||
      value.type === 'note' ||
      value.type === 'text' ||
      value.type === 'discard' ||
      value.type === 'error' ||
      value.type === 'citation' ||
      value.type === 'end')
  )
}

/** Posts the question and calls `onEvent` for each event of the streamed answer (FE-12). */
export async function streamAnswer(
  question: string,
  model: string | undefined,
  signal: AbortSignal,
  onEvent: (event: ChatEvent) => void,
): Promise<void> {
  const { response } = await apiClient.POST('/api/chat', {
    body: model === undefined ? { question } : { question, model },
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
