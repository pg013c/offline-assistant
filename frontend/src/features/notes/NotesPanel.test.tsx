import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderWithQueryClient } from '../../test/render'
import { server } from '../../test/server'
import { NotesPanel } from './NotesPanel'

const NOTES = [
  {
    id: '20261030-101000-deployer-duties',
    title: 'Deployer duties',
    created: '2026-10-30T10:10:00Z',
  },
  { id: '20261030-091507-breach-duties', title: 'Breach duties', created: '2026-10-30T09:15:07Z' },
]
const BREACH = {
  ...NOTES[1],
  content: '- Notify within 72 hours [1]',
  sources: [
    {
      number: 1,
      document_title: 'GDPR (EN)',
      chunk_id: 'gdpr:612',
      location: { heading_path: ['Article 33'], article: '33', paragraph: '1', page: 52 },
    },
  ],
  markdown: '# Breach duties',
}

describe('NotesPanel', () => {
  it('lists the notes in the order the API gives, newest first', async () => {
    server.use(http.get('*/api/notes', () => HttpResponse.json(NOTES)))

    renderWithQueryClient(<NotesPanel />)

    const list = await screen.findByRole('list', { name: 'Notes' })
    expect(
      within(list)
        .getAllByRole('button')
        .map((item) => item.textContent),
    ).toEqual([
      expect.stringContaining('Deployer duties'),
      expect.stringContaining('Breach duties'),
    ])
  })

  it('opens a note with its text and its sources', async () => {
    server.use(
      http.get('*/api/notes', () => HttpResponse.json(NOTES)),
      http.get('*/api/notes/:id', () => HttpResponse.json(BREACH)),
    )
    renderWithQueryClient(<NotesPanel />)

    await userEvent.click(await screen.findByRole('button', { name: /Breach duties/ }))

    const note = await screen.findByRole('region', { name: 'Breach duties' })
    expect(within(note).getByText('- Notify within 72 hours [1]')).toBeInTheDocument()
    expect(within(note).getByText(/\[1\] GDPR \(EN\), Art\. 33\(1\), p\. 52/)).toBeInTheDocument()
  })

  it('says so when there are no notes', async () => {
    server.use(http.get('*/api/notes', () => HttpResponse.json([])))

    renderWithQueryClient(<NotesPanel />)

    expect(await screen.findByText(/No notes yet/)).toBeInTheDocument()
  })
})
