import { useState, type ChangeEvent, type JSX } from 'react'

import {
  type DocumentSummary,
  useDeleteDocument,
  useDocuments,
  useReindexDocument,
  useUploadDocument,
} from './useDocuments'

interface DocumentPanelProps {
  /** How often the list refreshes while a document is processing. */
  pollIntervalMs?: number
}

// Extensions and media types the API accepts (F-02).
const ACCEPTED_FILES = [
  '.pdf',
  '.docx',
  '.png',
  '.jpg',
  '.jpeg',
  '.txt',
  '.md',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'image/png',
  'image/jpeg',
  'text/plain',
  'text/markdown',
].join(',')

export function DocumentPanel({ pollIntervalMs }: DocumentPanelProps = {}): JSX.Element {
  const documents = useDocuments(pollIntervalMs)
  const upload = useUploadDocument()
  const remove = useDeleteDocument()
  const reindex = useReindexDocument()
  const actionError = remove.error ?? reindex.error

  function onFileChosen(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (file) {
      upload.mutate(file)
    }
    event.target.value = ''
  }

  return (
    <section aria-labelledby="documents-heading" className="flex flex-col gap-4">
      <h2 id="documents-heading" className="text-base font-semibold">
        Documents
      </h2>

      <label className="flex flex-col gap-1 text-sm">
        <span>Upload a document (PDF, Word, image or text)</span>
        <input
          type="file"
          accept={ACCEPTED_FILES}
          onChange={onFileChosen}
          disabled={upload.isPending}
          className="text-sm"
        />
      </label>
      {upload.isError && (
        <p role="alert" className="text-sm text-red-700">
          {upload.error.message}
        </p>
      )}
      {actionError && (
        <p role="alert" className="text-sm text-red-700">
          {actionError.message}
        </p>
      )}

      {documents.isPending && <p className="text-sm text-gray-500">Loading documents…</p>}
      {documents.isError && (
        <p role="alert" className="text-sm text-red-700">
          Documents could not be loaded.
        </p>
      )}
      {documents.isSuccess && documents.data.length === 0 && (
        <p className="text-sm text-gray-500">No documents yet.</p>
      )}
      {documents.isSuccess && documents.data.length > 0 && (
        <ul className="flex flex-col gap-2">
          {documents.data.map((document) => (
            <li key={document.id} className="rounded border border-gray-200 px-3 py-2">
              <p className="text-sm font-medium">{document.title}</p>
              <DocumentStatus document={document} />
              <DocumentActions
                document={document}
                onDelete={() => {
                  remove.mutate(document)
                }}
                onReindex={() => {
                  reindex.mutate(document)
                }}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function DocumentStatus({ document }: { document: DocumentSummary }): JSX.Element {
  switch (document.status) {
    case 'processing':
      return <p className="text-xs text-gray-500">{document.filename} · Processing…</p>
    case 'failed':
      return (
        <p className="text-xs text-red-700">
          Could not be read: {document.failure_reason ?? 'unknown reason'}
        </p>
      )
    case 'ready':
      return (
        <p className="text-xs text-gray-500">
          {[
            document.filename,
            `${String(document.chunk_count)} passages`,
            ...(document.page_count === null ? [] : [`${String(document.page_count)} pages`]),
          ].join(' · ')}
        </p>
      )
  }
}

interface DocumentActionsProps {
  document: DocumentSummary
  onDelete: () => void
  onReindex: () => void
}

/** Re-index, and delete after an inline confirmation. */
function DocumentActions({ document, onDelete, onReindex }: DocumentActionsProps): JSX.Element {
  const [confirming, setConfirming] = useState(false)
  const button = 'rounded border border-gray-300 px-2 py-0.5 text-xs'

  if (confirming) {
    return (
      <div className="mt-2 flex items-center gap-2 text-xs">
        <span>Delete {document.title}?</span>
        <button
          type="button"
          aria-label={`Confirm deleting ${document.title}`}
          onClick={() => {
            setConfirming(false)
            onDelete()
          }}
          className={`${button} border-red-300 text-red-700`}
        >
          Delete
        </button>
        <button
          type="button"
          onClick={() => {
            setConfirming(false)
          }}
          className={button}
        >
          Cancel
        </button>
      </div>
    )
  }
  return (
    <div className="mt-2 flex gap-2">
      <button
        type="button"
        aria-label={`Re-index ${document.title}`}
        disabled={document.status === 'processing'}
        onClick={onReindex}
        className={button}
      >
        Re-index
      </button>
      <button
        type="button"
        aria-label={`Delete ${document.title}`}
        onClick={() => {
          setConfirming(true)
        }}
        className={button}
      >
        Delete
      </button>
    </div>
  )
}
