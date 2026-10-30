import { useId, useState, type JSX } from 'react'

import { citationLabel } from '../chat/citationLabel'
import { useNote, useNotes } from './useNotes'

/** The notes the agent saved: a list, and the chosen note as text with its sources (FR-61). */
export function NotesPanel(): JSX.Element {
  const notes = useNotes()
  const [chosen, setChosen] = useState<string | null>(null)

  if (notes.isPending) {
    return <p className="text-sm text-gray-500">Loading notes…</p>
  }
  if (notes.isError) {
    return (
      <p role="alert" className="text-sm text-red-700">
        {notes.error.message}
      </p>
    )
  }
  if (notes.data.length === 0) {
    return <p className="text-sm text-gray-500">No notes yet. Ask the assistant to save one.</p>
  }
  return (
    <div className="flex flex-col gap-3">
      <ul aria-label="Notes" className="flex flex-col gap-1">
        {notes.data.map((note) => (
          <li key={note.id}>
            <button
              type="button"
              aria-pressed={chosen === note.id}
              onClick={() => {
                setChosen(note.id)
              }}
              className="w-full rounded px-2 py-1 text-left text-sm hover:bg-gray-100 aria-pressed:bg-gray-100"
            >
              {note.title}
              <span className="block text-xs text-gray-500">
                {new Date(note.created).toLocaleString()}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {chosen !== null && <NoteView noteId={chosen} />}
    </div>
  )
}

interface NoteViewProps {
  noteId: string
}

function NoteView({ noteId }: NoteViewProps): JSX.Element {
  const note = useNote(noteId)
  const headingId = useId()
  if (!note.data) {
    return <p className="text-sm text-gray-500">{note.isError ? note.error.message : 'Loading…'}</p>
  }
  return (
    <section
      aria-labelledby={headingId}
      className="flex flex-col gap-2 border-t border-gray-100 pt-2"
    >
      <h3 id={headingId} className="text-sm font-semibold">
        {note.data.title}
      </h3>
      <pre className="text-sm whitespace-pre-wrap font-sans">{note.data.content}</pre>
      <ul aria-label="Note sources" className="flex flex-col gap-1 text-xs text-gray-600">
        {note.data.sources.map((source) => (
          <li key={source.number}>
            [{source.number}]{' '}
            {[source.document_title, citationLabel(source.location)].filter(Boolean).join(', ')}
          </li>
        ))}
      </ul>
    </section>
  )
}
