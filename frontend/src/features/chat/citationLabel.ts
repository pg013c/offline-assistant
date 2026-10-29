import type { components } from '../../api/schema'

export type CitationLocation = components['schemas']['CitationLocation']

/** Where a cited passage is, for people: "Art. 6(2), p. 53". */
export function citationLabel(location: CitationLocation): string {
  throw new Error(`not implemented: ${JSON.stringify(location)}`)
}
