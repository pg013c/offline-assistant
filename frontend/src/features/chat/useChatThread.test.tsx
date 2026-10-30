import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import { server } from '../../test/server'
import { useChatThread, type ChatThread } from './useChatThread'

const CITATION = {
  type: 'citation',
  chunk_id: 'a1:0',
  document_id: 'a1',
  document_title: 'policy',
  quote: 'Providers keep logs.',
}

function sse(events: object[]): string {
  return events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('')
}

/** Streams the body in two parts, split inside an event, as a network would. */
function streamed(body: string): ReadableStream<Uint8Array> {
  const bytes = new TextEncoder().encode(body)
  const middle = Math.floor(bytes.length / 2)
  return new ReadableStream({
    start(controller) {
      controller.enqueue(bytes.slice(0, middle))
      controller.enqueue(bytes.slice(middle))
      controller.close()
    },
  })
}

function serveAnswer(events: object[]) {
  const questions: unknown[] = []
  server.use(
    http.post('*/api/chat', async ({ request }) => {
      questions.push(await request.json())
      return new HttpResponse(streamed(sse(events)), {
        headers: { 'Content-Type': 'text/event-stream' },
      })
    }),
  )
  return questions
}

function last(thread: ChatThread) {
  const turn = thread.turns[thread.turns.length - 1]
  if (!turn) {
    throw new Error('no turn yet')
  }
  return turn.answer
}

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe('useChatThread', () => {
  it('starts with an empty thread', () => {
    const { result } = renderHook(() => useChatThread(), { wrapper })

    expect(result.current.turns).toEqual([])
  })

  it('sends the question and collects text, citations and the model', async () => {
    const questions = serveAnswer([
      { type: 'text', text: 'Providers ' },
      { type: 'text', text: 'keep logs.' },
      CITATION,
      { type: 'end', model_id: 'fake-extractive', found: true, is_test_model: true },
    ])
    const { result } = renderHook(() => useChatThread(), { wrapper })

    act(() => {
      result.current.ask('How long are logs kept?')
    })

    await waitFor(() => {
      expect(last(result.current).status).toBe('done')
    })
    expect(questions).toEqual([{ question: 'How long are logs kept?' }])
    expect(result.current.turns[0]?.question).toBe('How long are logs kept?')
    expect(last(result.current)).toEqual({
      status: 'done',
      text: 'Providers keep logs.',
      citations: [CITATION],
      tools: [],
      notes: [],
      modelId: 'fake-extractive',
      found: true,
      isTestModel: true,
    })
  })

  it('collects the notes the agent saved', async () => {
    serveAnswer([
      { type: 'tool', name: 'save_note', arguments: { title: 'Breach duties', content: 'x [1]' } },
      { type: 'note', id: '20261030-091507-breach-duties', title: 'Breach duties' },
      { type: 'text', text: 'Saved the checklist [1].' },
      { type: 'end', model_id: 'qwen3-8b', found: true, is_test_model: false },
    ])
    const { result } = renderHook(() => useChatThread(), { wrapper })

    act(() => {
      result.current.ask('Save a checklist of breach duties as a note.')
    })

    await waitFor(() => {
      expect(last(result.current).status).toBe('done')
    })
    expect(last(result.current).notes).toEqual([
      { id: '20261030-091507-breach-duties', title: 'Breach duties' },
    ])
  })

  it('collects the tool calls of the agent in order, before the answer', async () => {
    serveAnswer([
      { type: 'tool', name: 'search_documents', arguments: { query: 'breach' } },
      { type: 'tool', name: 'get_article', arguments: { document: 'GDPR (EN)', number: '33' } },
      { type: 'text', text: 'Within 72 hours [1].' },
      { type: 'end', model_id: 'qwen3-8b', found: true, is_test_model: false },
    ])
    const { result } = renderHook(() => useChatThread(), { wrapper })

    act(() => {
      result.current.ask('When must a breach be notified?')
    })

    await waitFor(() => {
      expect(last(result.current).status).toBe('done')
    })
    expect(last(result.current).tools).toEqual([
      { name: 'search_documents', arguments: { query: 'breach' } },
      { name: 'get_article', arguments: { document: 'GDPR (EN)', number: '33' } },
    ])
  })

  it('reports an error when the request fails', async () => {
    server.use(http.post('*/api/chat', () => new HttpResponse(null, { status: 500 })))
    const { result } = renderHook(() => useChatThread(), { wrapper })

    act(() => {
      result.current.ask('Anything?')
    })

    await waitFor(() => {
      expect(last(result.current).status).toBe('error')
    })
  })

  it('reports an error when the stream ends without an end event', async () => {
    serveAnswer([{ type: 'text', text: 'Cut off mid' }])
    const { result } = renderHook(() => useChatThread(), { wrapper })

    act(() => {
      result.current.ask('Anything?')
    })

    await waitFor(() => {
      expect(last(result.current).status).toBe('error')
    })
    expect(last(result.current).text).toBe('Cut off mid')
  })

  it('keeps each question with its own answer, in order', async () => {
    serveAnswer([
      { type: 'tool', name: 'search_documents', arguments: { query: 'first' } },
      { type: 'text', text: 'First answer.' },
      CITATION,
      { type: 'end', model_id: 'fake-extractive', found: true, is_test_model: true },
    ])
    const { result } = renderHook(() => useChatThread(), { wrapper })
    act(() => {
      result.current.ask('First?')
    })
    await waitFor(() => {
      expect(last(result.current).status).toBe('done')
    })
    serveAnswer([
      { type: 'text', text: 'Second answer.' },
      { type: 'end', model_id: 'qwen3-8b', found: false, is_test_model: false },
    ])

    act(() => {
      result.current.ask('Second?')
    })

    await waitFor(() => {
      expect(result.current.turns).toHaveLength(2)
      expect(last(result.current).status).toBe('done')
    })
    const [first, second] = result.current.turns
    expect(first?.question).toBe('First?')
    expect(first?.answer.text).toBe('First answer.')
    expect(first?.answer.citations).toEqual([CITATION])
    expect(first?.answer.tools).toHaveLength(1)
    expect(second?.question).toBe('Second?')
    expect(second?.answer.text).toBe('Second answer.')
    expect(second?.answer.citations).toEqual([])
    expect(second?.answer.modelId).toBe('qwen3-8b')
  })

  it('stops the running answer when a new question is asked', async () => {
    const signals: AbortSignal[] = []
    server.use(
      http.post('*/api/chat', ({ request }) => {
        signals.push(request.signal)
        // A stream that never ends, as an answer still being written.
        return new HttpResponse(new ReadableStream(), {
          headers: { 'Content-Type': 'text/event-stream' },
        })
      }),
    )
    const { result } = renderHook(() => useChatThread(), { wrapper })
    act(() => {
      result.current.ask('First?')
    })
    await waitFor(() => {
      expect(signals).toHaveLength(1)
    })

    act(() => {
      result.current.ask('Second?')
    })

    await waitFor(() => {
      expect(signals[0]?.aborted).toBe(true)
    })
    expect(result.current.turns.map((turn) => turn.question)).toEqual(['First?', 'Second?'])
  })

  it('names the chosen model in the request and on the turn', async () => {
    const questions = serveAnswer([
      { type: 'text', text: 'Quoted.' },
      { type: 'end', model_id: 'fake-extractive', found: true, is_test_model: true },
    ])
    const { result } = renderHook(() => useChatThread(), { wrapper })

    act(() => {
      result.current.ask('How long?', 'fake-extractive')
    })

    await waitFor(() => {
      expect(last(result.current).status).toBe('done')
    })
    expect(questions).toEqual([{ question: 'How long?', model: 'fake-extractive' }])
    expect(result.current.turns[0]?.model).toBe('fake-extractive')
  })

  it('drops the text and citations of a discarded attempt', async () => {
    serveAnswer([
      { type: 'text', text: 'Wrong answer.' },
      CITATION,
      { type: 'discard', reason: 'the answer cites no passage' },
      { type: 'text', text: 'Right answer.' },
      CITATION,
      { type: 'end', model_id: 'qwen3-8b', found: true, is_test_model: false, usage: null },
    ])
    const { result } = renderHook(() => useChatThread(), { wrapper })

    act(() => {
      result.current.ask('How long are logs kept?')
    })

    await waitFor(() => {
      expect(last(result.current).status).toBe('done')
    })
    expect(last(result.current).text).toBe('Right answer.')
    expect(last(result.current).citations).toEqual([CITATION])
  })

  it('ends with the error of an error event, not as an unfinished stream', async () => {
    serveAnswer([
      { type: 'text', text: 'Partial' },
      { type: 'discard', reason: 'not valid JSON' },
      {
        type: 'error',
        code: 'invalid_answer',
        message: 'The model gave no valid answer after 3 attempts.',
      },
      { type: 'end', model_id: 'qwen3-8b', found: true, is_test_model: false, usage: null },
    ])
    const { result } = renderHook(() => useChatThread(), { wrapper })

    act(() => {
      result.current.ask('Anything?')
    })

    await waitFor(() => {
      expect(last(result.current).status).toBe('error')
    })
    expect(last(result.current).error).toBe(
      'The model could not produce a valid answer. Try asking again.',
    )
    expect(last(result.current).text).toBe('')
  })
})
