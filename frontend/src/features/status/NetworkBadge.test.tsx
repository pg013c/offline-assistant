import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderWithQueryClient } from '../../test/render'
import { server } from '../../test/server'
import { NetworkBadge } from './NetworkBadge'

function serveHealth(network: boolean) {
  server.use(
    http.get('*/api/health', () => HttpResponse.json({ status: 'ok', version: '1', network })),
  )
}

describe('NetworkBadge', () => {
  it('says the assistant is offline while network mode is off', async () => {
    serveHealth(false)

    renderWithQueryClient(<NetworkBadge />)

    expect(await screen.findByText('Offline')).toBeInTheDocument()
  })

  it('warns when network mode is on', async () => {
    serveHealth(true)

    renderWithQueryClient(<NetworkBadge />)

    expect(await screen.findByText(/Network on/)).toBeInTheDocument()
    expect(screen.queryByText('Offline')).not.toBeInTheDocument()
  })
})
