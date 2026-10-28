import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { App } from './App'
import { renderWithQueryClient } from './test/render'
import { server } from './test/server'

describe('App', () => {
  it('shows the API status in the header', async () => {
    server.use(
      http.get('*/api/health', () => HttpResponse.json({ status: 'ok', version: '1.2.3' })),
    )

    renderWithQueryClient(<App />)

    const header = screen.getByRole('banner')
    expect(await within(header).findByText(/API: ok/)).toBeInTheDocument()
  })
})
