import type { JSX } from 'react'

import { useApiHealth } from './useApiHealth'

export function ApiStatus(): JSX.Element {
  const health = useApiHealth()

  if (health.isPending) {
    return <StatusText tone="neutral">API: checking</StatusText>
  }
  if (health.isError) {
    return <StatusText tone="error">API: unavailable</StatusText>
  }
  return <StatusText tone="ok">{`API: ok · v${health.data.version}`}</StatusText>
}

const TONE_CLASSES = {
  neutral: 'text-gray-500',
  ok: 'text-green-700',
  error: 'text-red-700',
} as const

interface StatusTextProps {
  tone: keyof typeof TONE_CLASSES
  children: string
}

function StatusText({ tone, children }: StatusTextProps): JSX.Element {
  return (
    <p role="status" className={`text-sm ${TONE_CLASSES[tone]}`}>
      {children}
    </p>
  )
}
