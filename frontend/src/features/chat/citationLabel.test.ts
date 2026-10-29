import { describe, expect, it } from 'vitest'

import { citationLabel } from './citationLabel'

const NOWHERE = { heading_path: [], article: null, paragraph: null, page: null }

describe('citationLabel', () => {
  it('names the article, paragraph and page', () => {
    expect(citationLabel({ ...NOWHERE, article: '6', paragraph: '2', page: 53 })).toBe(
      'Art. 6(2), p. 53',
    )
  })

  it('names the article and page when the article has no numbered paragraphs', () => {
    expect(citationLabel({ ...NOWHERE, article: '3', page: 41 })).toBe('Art. 3, p. 41')
  })

  it('names the article alone when the document has no pages', () => {
    expect(citationLabel({ ...NOWHERE, article: '13a', paragraph: '1' })).toBe('Art. 13a(1)')
  })

  it('uses the nearest heading and the page when there is no article', () => {
    expect(
      citationLabel({ ...NOWHERE, heading_path: ['Data retention policy', 'Retention'], page: 2 }),
    ).toBe('Retention, p. 2')
  })

  it('uses the page alone when there is nothing else', () => {
    expect(citationLabel({ ...NOWHERE, page: 7 })).toBe('p. 7')
  })

  it('is empty when the location is unknown', () => {
    expect(citationLabel(NOWHERE)).toBe('')
  })
})
