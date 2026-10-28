import { useState, type JSX, type SubmitEvent } from 'react'

import { CitationDialog } from './CitationDialog'
import { useChatStream, type ChatCitation } from './useChatStream'

// Models that only stand in for a real one until F-06; their answers must not look like AI answers.
const TEST_MODELS = new Set(['fake-extractive'])

export function ChatView(): JSX.Element {
  const { answer, ask } = useChatStream()
  const [question, setQuestion] = useState('')
  const [openCitation, setOpenCitation] = useState<ChatCitation | null>(null)

  function onSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    ask(question.trim())
  }

  return (
    <section aria-labelledby="chat-heading" className="flex flex-col gap-4">
      <h2 id="chat-heading" className="text-base font-semibold">
        Ask a question
      </h2>

      <form onSubmit={onSubmit} className="flex gap-2">
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
        <button
          type="submit"
          disabled={question.trim() === '' || answer.status === 'streaming'}
          className="rounded bg-gray-900 px-4 py-2 text-sm text-white disabled:opacity-40"
        >
          Ask
        </button>
      </form>

      {answer.status === 'error' && (
        <p role="alert" className="text-sm text-red-700">
          {answer.error ?? 'The answer failed.'}
        </p>
      )}

      {answer.status !== 'idle' && answer.status !== 'error' && (
        <article aria-live="polite" className="flex flex-col gap-3">
          <p className="text-sm whitespace-pre-line">{answer.text}</p>
          {answer.modelId && (
            <p className="text-xs text-gray-500">
              Answered by {answer.modelId}
              {TEST_MODELS.has(answer.modelId) && ' (test model, not AI: it quotes the best match)'}
            </p>
          )}
          {answer.citations.length > 0 && (
            <ul aria-label="Sources" className="flex flex-wrap gap-2">
              {answer.citations.map((citation) => (
                <li key={citation.chunk_id}>
                  <button
                    type="button"
                    onClick={() => {
                      setOpenCitation(citation)
                    }}
                    className="rounded border border-gray-300 px-2 py-1 text-xs"
                  >
                    {citation.document_title}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </article>
      )}

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
