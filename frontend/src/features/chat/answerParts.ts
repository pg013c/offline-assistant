export type AnswerPart = { kind: 'text'; text: string } | { kind: 'citation'; number: number }

// A marker as the answer prompt asks for it: passage numbers in brackets, e.g. [2] or [1, 3].
const MARKER = /\[(\d+(?:\s*,\s*\d+)*)\]/g

/**
 * The answer text with its `[n]` markers split out where a citation has that number (F-08).
 * Brackets that are not markers, and numbers no citation has, stay text.
 */
export function answerParts(text: string, cited: ReadonlySet<number>): AnswerPart[] {
  const parts: AnswerPart[] = []
  let pending = ''
  let last = 0
  for (const match of text.matchAll(MARKER)) {
    const numbers = (match[1] ?? '').split(',').map((number) => Number(number.trim()))
    if (!numbers.some((number) => cited.has(number))) {
      continue
    }
    pending += text.slice(last, match.index)
    if (pending) {
      parts.push({ kind: 'text', text: pending })
      pending = ''
    }
    for (const number of numbers) {
      parts.push(
        cited.has(number)
          ? { kind: 'citation', number }
          : { kind: 'text', text: `[${String(number)}]` },
      )
    }
    last = match.index + match[0].length
  }
  pending += text.slice(last)
  if (pending) {
    parts.push({ kind: 'text', text: pending })
  }
  return parts
}
