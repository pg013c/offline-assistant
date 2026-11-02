import { act, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { useState, type JSX } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '../../test/render'
import { server } from '../../test/server'
import { ModelSelect } from './ModelSelect'
import { MODELS_REFRESH_MS, type ModelChoice } from './useModels'

const MODELS = [
  { id: 'qwen3.5-9b', is_test_model: false, is_default: true },
  { id: 'fake-extractive', is_test_model: true, is_default: false },
]

describe('ModelSelect', () => {
  it('lists the models with the default chosen and the test model labelled', async () => {
    server.use(http.get('*/api/models', () => HttpResponse.json(MODELS)))

    renderWithQueryClient(<ModelSelect value={undefined} onChange={vi.fn()} />)

    const select = await screen.findByRole('combobox', { name: 'Model' })
    await screen.findByRole('option', { name: 'qwen3.5-9b' })
    expect(select).toHaveValue('qwen3.5-9b')
    expect(screen.getByRole('option', { name: 'fake-extractive (test model)' })).toBeInTheDocument()
  })

  it('reports the model the user picks', async () => {
    server.use(http.get('*/api/models', () => HttpResponse.json(MODELS)))
    const onChange = vi.fn()
    renderWithQueryClient(<ModelSelect value={undefined} onChange={onChange} />)
    await screen.findByRole('option', { name: 'qwen3.5-9b' })

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Model' }),
      'fake-extractive',
    )

    expect(onChange).toHaveBeenCalledWith('fake-extractive')
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  /** Serves `first`, then `then` from the next refresh on. */
  function serveChanging(first: ModelChoice[], then: ModelChoice[]) {
    let served = first
    server.use(http.get('*/api/models', () => HttpResponse.json(served)))
    return () => {
      served = then
    }
  }

  /** The select as the chat holds it: the picked model in state. */
  function Picker({ initial }: { initial?: string }): JSX.Element {
    const [value, setValue] = useState<string | undefined>(initial)
    return <ModelSelect value={value} onChange={setValue} />
  }

  async function refresh() {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(MODELS_REFRESH_MS)
    })
  }

  const CANDIDATE = { id: 'qwen3.6-35b-a3b', is_test_model: false, is_default: false }

  it('returns to the default when the picked model stops answering, and says so', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const change = serveChanging([...MODELS, CANDIDATE], MODELS)
    renderWithQueryClient(<Picker initial="qwen3.6-35b-a3b" />)
    const select = await screen.findByRole('combobox', { name: 'Model' })
    await screen.findByRole('option', { name: 'qwen3.6-35b-a3b' })
    expect(select).toHaveValue('qwen3.6-35b-a3b')

    change()
    await refresh()

    expect(await screen.findByRole('status')).toHaveTextContent(
      'qwen3.6-35b-a3b stopped answering. Questions now go to qwen3.5-9b.',
    )
    expect(select).toHaveValue('qwen3.5-9b')
    expect(screen.queryByRole('option', { name: 'qwen3.6-35b-a3b' })).not.toBeInTheDocument()
  })

  it('moves to the test model when the default stops answering, and says so', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const change = serveChanging(MODELS, MODELS.slice(1))
    renderWithQueryClient(<Picker />)
    const select = await screen.findByRole('combobox', { name: 'Model' })
    await screen.findByRole('option', { name: 'qwen3.5-9b' })

    change()
    await refresh()

    expect(await screen.findByRole('status')).toHaveTextContent(
      'qwen3.5-9b stopped answering. Questions now go to fake-extractive.',
    )
    expect(select).toHaveValue('fake-extractive')
  })

  it('says nothing while the chosen model keeps answering', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    serveChanging(MODELS, MODELS)
    renderWithQueryClient(<Picker />)
    await screen.findByRole('option', { name: 'qwen3.5-9b' })

    await refresh()

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
