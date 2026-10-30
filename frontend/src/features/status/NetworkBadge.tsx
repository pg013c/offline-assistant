import type { JSX } from 'react'

import { useApiHealth } from './useApiHealth'

/** Whether anything may leave the machine: "Offline" unless comparison mode is on (ADR 0004). */
export function NetworkBadge(): JSX.Element | null {
  const health = useApiHealth()
  if (!health.data) {
    return null
  }
  return health.data.network ? (
    <p className="rounded bg-amber-100 px-2 py-1 text-xs font-medium text-amber-900">
      Network on: comparison mode may send questions to a cloud model
    </p>
  ) : (
    <p className="rounded bg-green-50 px-2 py-1 text-xs font-medium text-green-800">Offline</p>
  )
}
