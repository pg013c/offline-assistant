import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { renderWithQueryClient } from '../../test/render'
import { server } from '../../test/server'
import { ModelSelect } from './ModelSelect'

const MODELS = [
  { id: 'qwen3-8b', is_test_model: false, is_default: true },
  { id: 'fake-extractive', is_test_model: true, is_default: false },
]

describe('ModelSelect', () => {
  it('lists the models with the default chosen and the test model labelled', async () => {
    server.use(http.get('*/api/models', () => HttpResponse.json(MODELS)))

    renderWithQueryClient(<ModelSelect value={undefined} onChange={vi.fn()} />)

    const select = await screen.findByRole('combobox', { name: 'Model' })
    await screen.findByRole('option', { name: 'qwen3-8b' })
    expect(select).toHaveValue('qwen3-8b')
    expect(screen.getByRole('option', { name: 'fake-extractive (test model)' })).toBeInTheDocument()
  })

  it('reports the model the user picks', async () => {
    server.use(http.get('*/api/models', () => HttpResponse.json(MODELS)))
    const onChange = vi.fn()
    renderWithQueryClient(<ModelSelect value={undefined} onChange={onChange} />)
    await screen.findByRole('option', { name: 'qwen3-8b' })

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Model' }),
      'fake-extractive',
    )

    expect(onChange).toHaveBeenCalledWith('fake-extractive')
  })
})
