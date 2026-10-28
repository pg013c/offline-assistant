import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderWithQueryClient } from '../../test/render'
import { server } from '../../test/server'
import { ApiStatus } from './ApiStatus'

const HEALTH_URL = '*/api/health'

describe('ApiStatus', () => {
  it('shows that the API is being checked while the request is pending', () => {
    server.use(http.get(HEALTH_URL, () => new Promise<never>(() => undefined)))

    renderWithQueryClient(<ApiStatus />)

    expect(screen.getByRole('status')).toHaveTextContent('API: checking')
  })

  it('shows ok and the version when the API is healthy', async () => {
    server.use(http.get(HEALTH_URL, () => HttpResponse.json({ status: 'ok', version: '1.2.3' })))

    renderWithQueryClient(<ApiStatus />)

    const status = await screen.findByText(/API: ok/)
    expect(status.closest('[role="status"]')).not.toBeNull()
    expect(screen.getByRole('status')).toHaveTextContent('1.2.3')
  })

  it('shows unavailable when the API cannot be reached', async () => {
    server.use(http.get(HEALTH_URL, () => HttpResponse.error()))

    renderWithQueryClient(<ApiStatus />)

    expect(await screen.findByText('API: unavailable')).toBeInTheDocument()
  })

  it('shows unavailable when the API answers with a server error', async () => {
    server.use(http.get(HEALTH_URL, () => new HttpResponse(null, { status: 503 })))

    renderWithQueryClient(<ApiStatus />)

    expect(await screen.findByText('API: unavailable')).toBeInTheDocument()
  })

  it('retries once with the default query settings, then shows unavailable', async () => {
    let requests = 0
    server.use(
      http.get(HEALTH_URL, () => {
        requests += 1
        return HttpResponse.error()
      }),
    )

    render(
      <QueryClientProvider client={new QueryClient()}>
        <ApiStatus />
      </QueryClientProvider>,
    )

    expect(await screen.findByText('API: unavailable', {}, { timeout: 3000 })).toBeInTheDocument()
    expect(requests).toBe(2)
  })
})
