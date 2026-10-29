import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderWithQueryClient } from '../../test/render'
import { server } from '../../test/server'
import { ChatView } from './ChatView'

const QUOTE = 'Providers keep logs for six months.'

function serveAnswer(events: object[]) {
  const body = events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join('')
  server.use(
    http.post(
      '*/api/chat',
      () => new HttpResponse(body, { headers: { 'Content-Type': 'text/event-stream' } }),
    ),
  )
}

const FOUND = [
  { type: 'text', text: 'Providers keep ' },
  { type: 'text', text: 'logs for six months.' },
  {
    type: 'citation',
    chunk_id: 'a1:0',
    document_id: 'a1',
    document_title: 'policy',
    quote: QUOTE,
    location: { heading_path: ['Article 12'], article: '12', paragraph: '2', page: 4 },
  },
  { type: 'end', model_id: 'fake-extractive', found: true, is_test_model: true },
]

async function ask(question: string) {
  await userEvent.type(screen.getByRole('textbox', { name: 'Question' }), question)
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
}

describe('ChatView', () => {
  it('cannot ask an empty question', () => {
    renderWithQueryClient(<ChatView />)

    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled()
  })

  it('shows the streamed answer and the model that produced it', async () => {
    serveAnswer(FOUND)
    renderWithQueryClient(<ChatView />)

    await ask('How long are logs kept?')

    expect(await screen.findByText('Providers keep logs for six months.')).toBeInTheDocument()
    expect(screen.getByText(/fake-extractive/)).toBeInTheDocument()
    expect(screen.getByText(/test model, not AI/i)).toBeInTheDocument()
  })

  it('marks answers from a test model by its flag, not its name', async () => {
    serveAnswer([
      { type: 'text', text: 'Quoted.' },
      { type: 'end', model_id: 'stand-in', found: true, is_test_model: true },
    ])
    renderWithQueryClient(<ChatView />)

    await ask('Anything?')

    expect(await screen.findByText(/test model, not AI/i)).toBeInTheDocument()
  })

  it('shows no test-model notice for a real model', async () => {
    serveAnswer([
      { type: 'text', text: 'An answer.' },
      { type: 'end', model_id: 'fake-extractive', found: true, is_test_model: false },
    ])
    renderWithQueryClient(<ChatView />)

    await ask('Anything?')

    expect(await screen.findByText(/Answered by fake-extractive/)).toBeInTheDocument()
    expect(screen.queryByText(/test model, not AI/i)).not.toBeInTheDocument()
  })

  it('opens a citation to show the quoted passage and its document', async () => {
    serveAnswer(FOUND)
    renderWithQueryClient(<ChatView />)
    await ask('How long are logs kept?')

    await userEvent.click(await screen.findByRole('button', { name: /policy/ }))

    const dialog = screen.getByRole('dialog', { name: 'policy' })
    expect(within(dialog).getByText(QUOTE)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows where each cited passage is, in the list and in the source', async () => {
    serveAnswer(FOUND)
    renderWithQueryClient(<ChatView />)
    await ask('How long are logs kept?')

    const citation = await screen.findByRole('button', { name: /policy/ })
    expect(citation).toHaveTextContent('policy · Art. 12(2), p. 4')
    await userEvent.click(citation)
    expect(
      within(screen.getByRole('dialog', { name: 'policy' })).getByText('Art. 12(2), p. 4'),
    ).toBeInTheDocument()
  })

  it('shows only the title of a citation whose location is unknown', async () => {
    serveAnswer(
      FOUND.map((event) =>
        event.type === 'citation'
          ? {
              ...event,
              location: { heading_path: [], article: null, paragraph: null, page: null },
            }
          : event,
      ),
    )
    renderWithQueryClient(<ChatView />)
    await ask('How long are logs kept?')

    expect(await screen.findByRole('button', { name: /policy/ })).toHaveTextContent(/^policy$/)
  })

  it('can be used from the keyboard: focus moves into the source and Escape returns it', async () => {
    serveAnswer(FOUND)
    renderWithQueryClient(<ChatView />)
    await ask('How long are logs kept?')
    const citation = await screen.findByRole('button', { name: /policy/ })

    citation.focus()
    await userEvent.keyboard('{Enter}')

    const dialog = screen.getByRole('dialog', { name: 'policy' })
    expect(within(dialog).getByRole('button', { name: 'Close' })).toHaveFocus()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(citation).toHaveFocus()
  })

  it('shows no citations when no relevant passage was found', async () => {
    serveAnswer([
      { type: 'text', text: 'No relevant passage was found in the uploaded documents.' },
      { type: 'end', model_id: 'fake-extractive', found: false, is_test_model: true },
    ])
    renderWithQueryClient(<ChatView />)

    await ask('Anything about biometrics?')

    expect(await screen.findByText(/no relevant passage/i)).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Sources' })).not.toBeInTheDocument()
  })

  it('tells the user when the answer failed', async () => {
    server.use(http.post('*/api/chat', () => new HttpResponse(null, { status: 500 })))
    renderWithQueryClient(<ChatView />)

    await ask('Anything?')

    expect(await screen.findByRole('alert')).toHaveTextContent(/answer failed/i)
  })

  it.each([
    ['invalid_answer', 'The model gave up.', /could not produce a valid answer/i],
    [
      'model_unreachable',
      'No model server answers at http://127.0.0.1:8080.',
      /not reachable.*127\.0\.0\.1:8080/i,
    ],
    ['model_timeout', 'The model server took over 60 s.', /took too long.*60 s/i],
  ])('explains a %s error', async (code, message, shown) => {
    serveAnswer([
      { type: 'error', code, message },
      { type: 'end', model_id: 'qwen3-8b', found: true, is_test_model: false, usage: null },
    ])
    renderWithQueryClient(<ChatView />)

    await ask('Anything?')

    expect(await screen.findByRole('alert')).toHaveTextContent(shown)
  })
})
