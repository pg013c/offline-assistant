export type AnswerPart = { kind: 'text'; text: string } | { kind: 'citation'; number: number }

/** The answer text with its `[n]` markers split out where a citation has that number (F-08). */
export function answerParts(text: string, cited: ReadonlySet<number>): AnswerPart[] {
  throw new Error(`not implemented: ${text} ${String(cited.size)}`)
}
