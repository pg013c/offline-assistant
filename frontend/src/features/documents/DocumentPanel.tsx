import type { ChangeEvent, JSX } from 'react'

import { useDocuments, useUploadDocument } from './useDocuments'

interface DocumentPanelProps {
  /** How often the list refreshes while a document is processing. */
  pollIntervalMs?: number
}

export function DocumentPanel(props: DocumentPanelProps = {}): JSX.Element {
  console.debug('not implemented', props.pollIntervalMs)
  const documents = useDocuments()
  const upload = useUploadDocument()

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
        <span>Upload a document (.txt or .md)</span>
        <input
          type="file"
          accept=".txt,.md,text/plain,text/markdown"
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
              <p className="text-xs text-gray-500">
                {document.filename} · {document.chunk_count} passages
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
