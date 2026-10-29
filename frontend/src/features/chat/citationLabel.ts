import type { components } from '../../api/schema'

export type CitationLocation = components['schemas']['CitationLocation']

/** Where a cited passage is, for people: "Art. 6(2), p. 53". */
export function citationLabel(location: CitationLocation): string {
  const { article, paragraph, page, heading_path: headings } = location
  const where =
    article === null
      ? headings.at(-1)
      : `Art. ${article}${paragraph === null ? '' : `(${paragraph})`}`
  return [where, page === null ? undefined : `p. ${String(page)}`]
    .filter((part) => part !== undefined)
    .join(', ')
}
