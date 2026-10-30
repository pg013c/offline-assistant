import type { JSX } from 'react'

interface ModelSelectProps {
  value: string | undefined
  onChange: (model: string) => void
}

export function ModelSelect({ value }: ModelSelectProps): JSX.Element {
  throw new Error(`not implemented: ${String(value)}`)
}
