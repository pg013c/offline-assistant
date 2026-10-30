import { useState, type JSX, type SubmitEvent } from 'react'

import type { ChatCitation } from './chatStream'
import { ModelSelect } from '../models/ModelSelect'
import { useModels } from '../models/useModels'
import { CitationDialog } from './CitationDialog'
import { Turn } from './Turn'
import { useChatThread } from './useChatThread'

export function ChatView(): JSX.Element {
  const { turns, ask } = useChatThread()
  const [question, setQuestion] = useState('')
  const [openCitation, setOpenCitation] = useState<ChatCitation | null>(null)
  const [model, setModel] = useState<string | undefined>(undefined)
  const models = useModels()
  // The model a question goes to: the one picked, else the API's default.
  const chosen = model ?? models.data?.find((choice) => choice.is_default)?.id

  function onSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    // A new question stops an answer still being written (F-08 review #12).
    ask(question.trim(), chosen)
    setQuestion('')
  }

  return (
    <section aria-labelledby="chat-heading" className="flex flex-col gap-4">
      <h2 id="chat-heading" className="text-base font-semibold">
        Ask a question
      </h2>

      {turns.map((turn, position) => (
        <Turn key={position} turn={turn} onOpenCitation={setOpenCitation} />
      ))}

      <form onSubmit={onSubmit} className="flex flex-wrap items-center gap-2">
        <label htmlFor="question" className="sr-only">
          Question
        </label>
        <input
          id="question"
          value={question}
          onChange={(event) => {
            setQuestion(event.target.value)
          }}
          placeholder="What does the policy say about logs?"
          className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <ModelSelect value={model} onChange={setModel} />
        <button
          type="submit"
          disabled={question.trim() === ''}
          className="rounded bg-gray-900 px-4 py-2 text-sm text-white disabled:opacity-40"
        >
          Ask
        </button>
      </form>

      {openCitation && (
        <CitationDialog
          citation={openCitation}
          onClose={() => {
            setOpenCitation(null)
          }}
        />
      )}
    </section>
  )
}
