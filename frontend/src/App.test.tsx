import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'

import { App } from './App'
import { renderWithQueryClient } from './test/render'
import { server } from './test/server'

describe('App', () => {
  beforeEach(() => {
    server.use(
      http.get('*/api/health', () => HttpResponse.json({ status: 'ok', version: '1.2.3' })),
      http.get('*/api/documents', () => HttpResponse.json([])),
    )
  })

  it('shows the API status in the header', async () => {
    renderWithQueryClient(<App />)

    const header = screen.getByRole('banner')
    expect(await within(header).findByText(/API: ok/)).toBeInTheDocument()
  })

  it('shows the document panel and the chat', async () => {
    renderWithQueryClient(<App />)

    expect(await screen.findByRole('heading', { name: 'Documents' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Ask a question' })).toBeInTheDocument()
  })
})
