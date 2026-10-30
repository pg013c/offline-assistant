import type { JSX } from 'react'

import { AnswerText } from './AnswerText'
import type { ChatCitation } from './chatStream'
import { citationLabel } from './citationLabel'
import { toolStep } from './toolStep'
import type { ChatTurn } from './useChatThread'

interface TurnProps {
  turn: ChatTurn
  onOpenCitation: (citation: ChatCitation) => void
}

/** One question of the thread with its answer: steps, text, model and sources. */
export function Turn({ turn, onOpenCitation }: TurnProps): JSX.Element {
  const { answer } = turn
  return (
    <article aria-live="polite" className="flex flex-col gap-3 border-t border-gray-100 pt-4">
      <p className="text-sm font-medium">{turn.question}</p>
      {answer.tools.length + answer.notes.length > 0 && (
        <ol aria-label="Steps" className="flex flex-col gap-1 text-xs text-gray-500">
          {answer.tools.map((tool, position) => (
            <li key={position}>{toolStep(tool)}</li>
          ))}
          {answer.notes.map((note) => (
            <li key={note.id}>Saved note: {note.title}</li>
          ))}
        </ol>
      )}
      {answer.status === 'error' && (
        <p role="alert" className="text-sm text-red-700">
          {answer.error ?? 'The answer failed.'}
        </p>
      )}
      {answer.status === 'done' && answer.found === false && (
        <p role="note" className="rounded bg-gray-100 px-3 py-2 text-sm text-gray-700">
          No answer in the uploaded documents.
        </p>
      )}
      {answer.status !== 'error' && (
        <AnswerText
          text={answer.text}
          citations={answer.citations}
          onOpenCitation={onOpenCitation}
        />
      )}
      {answer.status === 'stopped' && (
        <p className="text-xs text-gray-500">Stopped for the next question.</p>
      )}
      {answer.modelId && (
        <p className="text-xs text-gray-500">
          Answered by {answer.modelId}
          {answer.isTestModel && ' (test model, not AI: it quotes the best match)'}
        </p>
      )}
      {answer.citations.length > 0 && (
        <ul aria-label="Sources" className="flex flex-wrap gap-2">
          {answer.citations.map((citation) => (
            <li key={citation.chunk_id}>
              <button
                type="button"
                onClick={() => {
                  onOpenCitation(citation)
                }}
                className="rounded border border-gray-300 px-2 py-1 text-xs"
              >
                {[citation.document_title, citationLabel(citation.location)]
                  .filter(Boolean)
                  .join(' · ')}
              </button>
            </li>
          ))}
        </ul>
      )}
    </article>
  )
}
