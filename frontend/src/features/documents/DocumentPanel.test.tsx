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
    http.delete('*/api/documents/:id', ({ params }) => {
      const index = documents.findIndex((document) => document.id === params.id)
      documents.splice(index, 1)
      return new HttpResponse(null, { status: 204 })
    }),
  )
}

describe('DocumentPanel', () => {
  it('lists the uploaded documents', async () => {
    serveDocuments([POLICY])

    renderWithQueryClient(<DocumentPanel />)

    expect(await screen.findByText('policy')).toBeInTheDocument()
    expect(screen.getByText('policy.txt · 2 passages')).toBeInTheDocument()
  })

  it('shows the page count of documents that have pages', async () => {
    serveDocuments([{ ...POLICY, filename: 'ai-act.pdf', chunk_count: 12, page_count: 3 }])

    renderWithQueryClient(<DocumentPanel />)

    expect(await screen.findByText('ai-act.pdf · 12 passages · 3 pages')).toBeInTheDocument()
  })

  it('accepts PDF, Word, image and text files', () => {
    serveDocuments([])

    renderWithQueryClient(<DocumentPanel />)

    const accept = screen.getByLabelText(/upload a document/i).getAttribute('accept') ?? ''
    for (const extension of ['.pdf', '.docx', '.png', '.jpg', '.jpeg', '.txt', '.md']) {
      expect(accept.split(',')).toContain(extension)
    }
  })

  it('shows a document as processing and refreshes the list until it is ready', async () => {
    const processing: DocumentResponse = { ...POLICY, status: 'processing', chunk_count: 0 }
    let requests = 0
    server.use(
      http.get('*/api/documents', () => {
        requests += 1
        return HttpResponse.json([requests < 3 ? processing : POLICY])
      }),
    )

    renderWithQueryClient(<DocumentPanel pollIntervalMs={20} />)

    expect(await screen.findByText(/processing/i)).toBeInTheDocument()
    expect(await screen.findByText('policy.txt · 2 passages')).toBeInTheDocument()
    expect(screen.queryByText(/processing/i)).not.toBeInTheDocument()
  })

  it('stops refreshing once no document is processing', async () => {
    let requests = 0
    server.use(
      http.get('*/api/documents', () => {
        requests += 1
        return HttpResponse.json([POLICY])
      }),
    )

    renderWithQueryClient(<DocumentPanel pollIntervalMs={20} />)
    await screen.findByText('policy')
    await new Promise((resolve) => setTimeout(resolve, 100))

    expect(requests).toBe(1)
  })

  it('shows why a document could not be read', async () => {
    serveDocuments([
      {
        ...POLICY,
        filename: 'locked.pdf',
        status: 'failed',
        chunk_count: 0,
        failure_reason: 'The PDF is password-protected.',
      },
    ])

    renderWithQueryClient(<DocumentPanel />)

    expect(
      await screen.findByText('Could not be read: The PDF is password-protected.'),
    ).toBeInTheDocument()
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
            message:
              'slides.pptx: supported file types are .docx, .jpeg, .jpg, .md, .pdf, .png, .txt',
          },
          { status: 415 },
        ),
      ),
    )
    renderWithQueryClient(<DocumentPanel />)
    await screen.findByText(/no documents yet/i)
    // The input offers supported types only; a user can still pick "All files" in the dialog.
    const user = userEvent.setup({ applyAccept: false })

    await user.upload(
      screen.getByLabelText(/upload a document/i),
      new File(['PK'], 'slides.pptx', { type: 'application/vnd.ms-powerpoint' }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('slides.pptx: supported file types')
  })

  it('deletes a document after the user confirms', async () => {
    serveDocuments([POLICY])
    renderWithQueryClient(<DocumentPanel />)
    await screen.findByText('policy')

    await userEvent.click(screen.getByRole('button', { name: 'Delete policy' }))
    await userEvent.click(screen.getByRole('button', { name: 'Confirm deleting policy' }))

    expect(await screen.findByText(/no documents yet/i)).toBeInTheDocument()
  })

  it('keeps the document when the user cancels deleting it', async () => {
    let deleted = false
    serveDocuments([POLICY])
    server.use(
      http.delete('*/api/documents/:id', () => {
        deleted = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderWithQueryClient(<DocumentPanel />)
    await screen.findByText('policy')

    await userEvent.click(screen.getByRole('button', { name: 'Delete policy' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.getByText('policy')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Delete policy' })).toBeInTheDocument()
    expect(deleted).toBe(false)
  })

  it('re-indexes a document and shows it processing until it is ready', async () => {
    let reindexed = false
    server.use(
      http.get('*/api/documents', () =>
        HttpResponse.json([reindexed ? { ...POLICY, status: 'processing' } : POLICY]),
      ),
      http.post('*/api/documents/:id/reindex', () => {
        reindexed = true
        setTimeout(() => {
          reindexed = false
        }, 50)
        return HttpResponse.json({ ...POLICY, status: 'processing' }, { status: 202 })
      }),
    )
    renderWithQueryClient(<DocumentPanel pollIntervalMs={20} />)
    await screen.findByText('policy.txt · 2 passages')

    await userEvent.click(screen.getByRole('button', { name: 'Re-index policy' }))

    expect(await screen.findByText(/processing/i)).toBeInTheDocument()
    expect(await screen.findByText('policy.txt · 2 passages')).toBeInTheDocument()
  })

  it('shows the reason when deleting fails', async () => {
    serveDocuments([POLICY])
    server.use(
      http.delete('*/api/documents/:id', () =>
        HttpResponse.json(
          { code: 'document_not_found', message: 'No document has the id a1.' },
          { status: 404 },
        ),
      ),
    )
    renderWithQueryClient(<DocumentPanel />)
    await screen.findByText('policy')

    await userEvent.click(screen.getByRole('button', { name: 'Delete policy' }))
    await userEvent.click(screen.getByRole('button', { name: 'Confirm deleting policy' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('No document has the id a1.')
  })
})
