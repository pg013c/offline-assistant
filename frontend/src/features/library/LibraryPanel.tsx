import { useRef, useState, type JSX, type KeyboardEvent } from 'react'

import { DocumentPanel } from '../documents/DocumentPanel'
import { NotesPanel } from '../notes/NotesPanel'

const TABS = [
  { id: 'documents', label: 'Documents' },
  { id: 'notes', label: 'Notes' },
] as const

type TabId = (typeof TABS)[number]['id']

/** The documents and the saved notes, as tabs that also work from the keyboard (FE-24). */
export function LibraryPanel(): JSX.Element {
  const [active, setActive] = useState<TabId>('documents')
  const buttons = useRef<Partial<Record<TabId, HTMLButtonElement | null>>>({})

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') {
      return
    }
    const position = TABS.findIndex((tab) => tab.id === active)
    const step = event.key === 'ArrowRight' ? 1 : TABS.length - 1
    const next = TABS[(position + step) % TABS.length]
    if (next) {
      setActive(next.id)
      buttons.current[next.id]?.focus()
    }
  }

  return (
    <section aria-label="Library" className="flex flex-col gap-3">
      <div role="tablist" aria-label="Library" className="flex gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            ref={(element) => {
              buttons.current[tab.id] = element
            }}
            type="button"
            role="tab"
            id={`library-tab-${tab.id}`}
            aria-selected={active === tab.id}
            aria-controls={`library-panel-${tab.id}`}
            tabIndex={active === tab.id ? 0 : -1}
            onKeyDown={onKeyDown}
            onClick={() => {
              setActive(tab.id)
            }}
            className="rounded px-3 py-1 text-sm aria-selected:bg-gray-900 aria-selected:text-white"
          >
            {tab.label}
          </button>
        ))}
      </div>
      {/* Both panels stay mounted, so an upload in progress survives a look at the notes. */}
      {TABS.map((tab) => (
        <div
          key={tab.id}
          role="tabpanel"
          id={`library-panel-${tab.id}`}
          aria-labelledby={`library-tab-${tab.id}`}
          hidden={active !== tab.id}
        >
          {tab.id === 'documents' ? <DocumentPanel /> : <NotesPanel />}
        </div>
      ))}
    </section>
  )
}
