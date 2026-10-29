import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { components } from '../../api/schema'
import { renderWithQueryClient } from '../../test/render'
import { server } from '../../test/server'
import { DocumentPanel } from './DocumentPanel'

type DocumentResponse = components['schemas']['DocumentResponse']

const POLICY: DocumentResponse = {
  id: 'a1',
  title: 'policy',
  filename: 'policy.txt',
  status: 'ready',
  chunk_count: 2,
  page_count: null,
  failure_reason: null,
}

function serveDocuments(initial: DocumentResponse[]) {
  const documents = [...initial]
  server.use(
    http.get('*/api/documents', () => HttpResponse.json(documents)),
    http.post('*/api/documents', async ({ request }) => {
      const file = (await request.formData()).get('file')
      if (!(file instanceof File)) {
        return HttpResponse.json({ code: 'bad_request', message: 'no file' }, { status: 400 })
      }
      const created: DocumentResponse = {
        id: 'b2',
        title: 'notes',
        filename: file.name,
        status: 'ready',
        chunk_count: 1,
        page_count: null,
        failure_reason: null,
      }
      documents.push(created)
      return HttpResponse.json(created, { status: 202 })
    }),
  )
}

describe('DocumentPanel', () => {
  it('lists the uploaded documents', async () => {
    serveDocuments([POLICY])

    renderWithQueryClient(<DocumentPanel />)

    expect(await screen.findByText('policy')).toBeInTheDocument()
    expect(screen.getByText(/2 passages/)).toBeInTheDocument()
  })

  it('says so when there are no documents', async () => {
    serveDocuments([])

    renderWithQueryClient(<DocumentPanel />)

    expect(await screen.findByText(/no documents yet/i)).toBeInTheDocument()
  })

  it('uploads a file chosen in the labelled input and shows it in the list', async () => {
    serveDocuments([POLICY])
    renderWithQueryClient(<DocumentPanel />)
    await screen.findByText('policy')

    await userEvent.upload(
      screen.getByLabelText(/upload a document/i),
      new File(['Some notes.'], 'notes.txt', { type: 'text/plain' }),
    )

    expect(await screen.findByText('notes')).toBeInTheDocument()
  })

  it('shows the reason when the API rejects a file', async () => {
    serveDocuments([])
    server.use(
      http.post('*/api/documents', () =>
        HttpResponse.json(
          {
            code: 'unsupported_file_type',
            message: 'policy.pdf: only .txt and .md files are supported',
          },
          { status: 415 },
        ),
      ),
    )
    renderWithQueryClient(<DocumentPanel />)
    await screen.findByText(/no documents yet/i)
    // The input only offers .txt and .md; a user can still pick "All files" in the file dialog.
    const user = userEvent.setup({ applyAccept: false })

    await user.upload(
      screen.getByLabelText(/upload a document/i),
      new File(['%PDF'], 'policy.pdf', { type: 'application/pdf' }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'policy.pdf: only .txt and .md files are supported',
    )
  })
})
