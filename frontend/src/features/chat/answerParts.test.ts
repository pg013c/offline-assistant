import { describe, expect, it } from 'vitest'

import { answerParts } from './answerParts'

describe('answerParts', () => {
  it('splits an answer into text and the markers that have a citation', () => {
    expect(answerParts('Kept [1]. Also [2].', new Set([1, 2]))).toEqual([
      { kind: 'text', text: 'Kept ' },
      { kind: 'citation', number: 1 },
      { kind: 'text', text: '. Also ' },
      { kind: 'citation', number: 2 },
      { kind: 'text', text: '.' },
    ])
  })

  it('gives a marker of several passages one part per passage', () => {
    expect(answerParts('Kept [1, 3].', new Set([1, 3]))).toEqual([
      { kind: 'text', text: 'Kept ' },
      { kind: 'citation', number: 1 },
      { kind: 'citation', number: 3 },
      { kind: 'text', text: '.' },
    ])
  })

  it('leaves brackets that are not markers, and markers without a citation, as text', () => {
    expect(answerParts('He wrote [sic] in [2018], see [4].', new Set([1]))).toEqual([
      { kind: 'text', text: 'He wrote [sic] in [2018], see [4].' },
    ])
  })

  it('keeps the numbers of a marker that have a citation and writes the rest as text', () => {
    expect(answerParts('Both [1, 9].', new Set([1]))).toEqual([
      { kind: 'text', text: 'Both ' },
      { kind: 'citation', number: 1 },
      { kind: 'text', text: '[9]' },
      { kind: 'text', text: '.' },
    ])
  })
})
