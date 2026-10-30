import type { JSX } from 'react'

import { answerParts } from './answerParts'
import type { ChatCitation } from './chatStream'

interface AnswerTextProps {
  text: string
  citations: ChatCitation[]
  onOpenCitation: (citation: ChatCitation) => void
}

/** The answer, its `[n]` markers buttons that open the cited passage (FR-60, FE-24). */
export function AnswerText({ text, citations, onOpenCitation }: AnswerTextProps): JSX.Element {
  const byNumber = new Map(citations.map((citation) => [citation.number, citation]))
  const parts = answerParts(text, new Set(byNumber.keys()))
  return (
    <p className="text-sm whitespace-pre-line">
      {parts.map((part, position) => {
        if (part.kind === 'text') {
          return <span key={position}>{part.text}</span>
        }
        const citation = byNumber.get(part.number)
        if (!citation) {
          return null
        }
        return (
          <button
            key={position}
            type="button"
            aria-label={`Source ${String(part.number)}`}
            title={citation.document_title}
            onClick={() => {
              onOpenCitation(citation)
            }}
            // At least 24 by 24 pixels, so a marker is easy to hit (WCAG 2.5.8).
            className="mx-0.5 inline-flex min-h-6 min-w-6 items-center justify-center rounded align-baseline text-xs text-blue-700 underline hover:bg-blue-50"
          >
            [{part.number}]
          </button>
        )
      })}
    </p>
  )
}
