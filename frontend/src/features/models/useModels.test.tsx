import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { server } from '../../test/server'
import { MODELS_REFRESH_MS, useModels } from './useModels'

describe('useModels', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('fetches the list again on an interval, so a model that stops answering leaves it', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let requests = 0
    server.use(
      http.get('*/api/models', () => {
        requests += 1
        return HttpResponse.json([{ id: 'qwen3.5-9b', is_test_model: false, is_default: true }])
      }),
    )
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )

    const { result } = renderHook(() => useModels(), { wrapper })
    await waitFor(() => {
      expect(result.current.data).toBeDefined()
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(MODELS_REFRESH_MS)
    })

    await waitFor(() => {
      expect(requests).toBe(2)
    })
    expect(MODELS_REFRESH_MS).toBeLessThanOrEqual(15_000)
  })
})
