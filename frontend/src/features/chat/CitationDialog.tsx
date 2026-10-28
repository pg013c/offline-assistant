import { useId, type JSX } from 'react'

import type { ChatCitation } from './useChatStream'

interface CitationDialogProps {
  citation: ChatCitation
  onClose: () => void
}

export function CitationDialog({ citation, onClose }: CitationDialogProps): JSX.Element {
  const titleId = useId()
  return (
    <dialog
      open
      aria-labelledby={titleId}
      className="fixed inset-0 m-auto max-w-lg rounded border border-gray-300 bg-white p-6 shadow-lg"
    >
      <h3 id={titleId} className="text-base font-semibold">
        {citation.document_title}
      </h3>
      <blockquote className="mt-3 border-l-4 border-gray-300 pl-3 text-sm whitespace-pre-line">
        {citation.quote}
      </blockquote>
      <button
        type="button"
        onClick={onClose}
        className="mt-4 rounded border border-gray-300 px-3 py-1 text-sm"
      >
        Close
      </button>
    </dialog>
  )
}
