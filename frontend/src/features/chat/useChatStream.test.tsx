import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import { server } from '../../test/server'
import { useChatStream } from './useChatStream'

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

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe('useChatStream', () => {
  it('starts idle with an empty answer', () => {
    const { result } = renderHook(() => useChatStream(), { wrapper })

    expect(result.current.answer).toEqual({ status: 'idle', text: '', citations: [] })
  })

  it('sends the question and collects text, citations and the model', async () => {
    const questions = serveAnswer([
      { type: 'text', text: 'Providers ' },
      { type: 'text', text: 'keep logs.' },
      CITATION,
      { type: 'end', model_id: 'fake-extractive', found: true },
    ])
    const { result } = renderHook(() => useChatStream(), { wrapper })

    act(() => {
      result.current.ask('How long are logs kept?')
    })

    await waitFor(() => {
      expect(result.current.answer.status).toBe('done')
    })
    expect(questions).toEqual([{ question: 'How long are logs kept?' }])
    expect(result.current.answer).toEqual({
      status: 'done',
      question: 'How long are logs kept?',
      text: 'Providers keep logs.',
      citations: [CITATION],
      modelId: 'fake-extractive',
      found: true,
    })
  })

  it('reports an error when the request fails', async () => {
    server.use(http.post('*/api/chat', () => new HttpResponse(null, { status: 500 })))
    const { result } = renderHook(() => useChatStream(), { wrapper })

    act(() => {
      result.current.ask('Anything?')
    })

    await waitFor(() => {
      expect(result.current.answer.status).toBe('error')
    })
  })

  it('starts a fresh answer for a new question', async () => {
    serveAnswer([
      { type: 'text', text: 'First answer.' },
      { type: 'end', model_id: 'fake-extractive', found: true },
    ])
    const { result } = renderHook(() => useChatStream(), { wrapper })
    act(() => {
      result.current.ask('First?')
    })
    await waitFor(() => {
      expect(result.current.answer.status).toBe('done')
    })
    serveAnswer([
      { type: 'text', text: 'Second answer.' },
      { type: 'end', model_id: 'fake-extractive', found: false },
    ])

    act(() => {
      result.current.ask('Second?')
    })

    await waitFor(() => {
      expect(result.current.answer.question).toBe('Second?')
      expect(result.current.answer.status).toBe('done')
    })
    expect(result.current.answer.text).toBe('Second answer.')
    expect(result.current.answer.citations).toEqual([])
  })
})
