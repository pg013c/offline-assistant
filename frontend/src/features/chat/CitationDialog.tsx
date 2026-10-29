import { useEffect, useId, useRef, type JSX } from 'react'

import { citationLabel } from './citationLabel'
import type { ChatCitation } from './useChatStream'

interface CitationDialogProps {
  citation: ChatCitation
  onClose: () => void
}

/** The quoted source of an answer, as a modal dialog that can be used from the keyboard (FE-24). */
export function CitationDialog({ citation, onClose }: CitationDialogProps): JSX.Element {
  const titleId = useId()
  const label = citationLabel(citation.location)
  const dialog = useRef<HTMLDialogElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  // The latest onClose, so the effect below runs once per opening and not on every render.
  const close = useRef(onClose)
  useEffect(() => {
    close.current = onClose
  })

  useEffect(() => {
    const element = dialog.current
    if (!element) {
      return
    }
    // Return focus to whatever opened the dialog once it closes.
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    if (!element.open) {
      // Browsers make the rest of the page inert with showModal; jsdom does not implement it.
      if (typeof element.showModal === 'function') {
        element.showModal()
      } else {
        element.setAttribute('open', '')
      }
    }
    closeButton.current?.focus()

    // Escape: browsers fire `cancel` on a modal dialog; the keydown listener covers the rest.
    function onCancel(event: Event) {
      event.preventDefault()
      close.current()
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onCancel(event)
      }
    }
    element.addEventListener('cancel', onCancel)
    element.addEventListener('keydown', onKeyDown)
    return () => {
      element.removeEventListener('cancel', onCancel)
      element.removeEventListener('keydown', onKeyDown)
      opener?.focus()
    }
  }, [])

  return (
    <dialog
      ref={dialog}
      aria-labelledby={titleId}
      className="m-auto max-w-lg rounded border border-gray-300 bg-white p-6 shadow-lg backdrop:bg-black/30"
    >
      <h3 id={titleId} className="text-base font-semibold">
        {citation.document_title}
      </h3>
      {label && <p className="text-sm text-gray-600">{label}</p>}
      <blockquote className="mt-3 border-l-4 border-gray-300 pl-3 text-sm whitespace-pre-line">
        {citation.quote}
      </blockquote>
      <button
        ref={closeButton}
        type="button"
        onClick={onClose}
        className="mt-4 rounded border border-gray-300 px-3 py-1 text-sm"
      >
        Close
      </button>
    </dialog>
  )
}
