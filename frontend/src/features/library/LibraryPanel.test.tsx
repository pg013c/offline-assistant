import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'

import { renderWithQueryClient } from '../../test/render'
import { server } from '../../test/server'
import { LibraryPanel } from './LibraryPanel'

beforeEach(() => {
  server.use(
    http.get('*/api/documents', () => HttpResponse.json([])),
    http.get('*/api/notes', () => HttpResponse.json([])),
  )
})

describe('LibraryPanel', () => {
  it('shows the documents first', async () => {
    renderWithQueryClient(<LibraryPanel />)

    expect(screen.getByRole('tab', { name: 'Documents' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByText(/No documents yet/)).toBeInTheDocument()
  })

  it('switches to the notes by click', async () => {
    renderWithQueryClient(<LibraryPanel />)

    await userEvent.click(screen.getByRole('tab', { name: 'Notes' }))

    expect(screen.getByRole('tab', { name: 'Notes' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByText(/No notes yet/)).toBeInTheDocument()
  })

  it('switches tabs with the arrow keys', async () => {
    renderWithQueryClient(<LibraryPanel />)
    screen.getByRole('tab', { name: 'Documents' }).focus()

    await userEvent.keyboard('{ArrowRight}')

    expect(screen.getByRole('tab', { name: 'Notes' })).toHaveFocus()
    expect(screen.getByRole('tab', { name: 'Notes' })).toHaveAttribute('aria-selected', 'true')
  })

  it('keeps both panels, so every tab controls a panel and the documents keep their state', async () => {
    renderWithQueryClient(<LibraryPanel />)
    await userEvent.click(screen.getByRole('tab', { name: 'Notes' }))

    for (const name of ['Documents', 'Notes']) {
      const controlled = screen.getByRole('tab', { name }).getAttribute('aria-controls')
      expect(controlled && document.getElementById(controlled)).toBeTruthy()
    }
    // A hidden element has no accessible name, so the panel is found by the id its tab names.
    const documents = document.getElementById('library-panel-documents')
    if (!documents) {
      throw new Error('the documents panel is gone')
    }
    expect(documents).not.toBeVisible()
    expect(within(documents).getByText(/No documents yet/)).toBeInTheDocument()
  })
})
