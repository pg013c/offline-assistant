import type { JSX } from 'react'

import { useModels } from './useModels'

interface ModelSelectProps {
  // The model the user picked; the API's default until they pick one.
  value: string | undefined
  onChange: (model: string) => void
}

/** Chooses the model that answers the next question (FR-62). */
export function ModelSelect({ value, onChange }: ModelSelectProps): JSX.Element {
  const models = useModels()
  const fallback = models.data?.find((model) => model.is_default)?.id
  return (
    <label className="flex items-center gap-2 text-xs text-gray-600">
      Model
      <select
        value={value ?? fallback ?? ''}
        disabled={!models.data}
        onChange={(event) => {
          onChange(event.target.value)
        }}
        className="rounded border border-gray-300 px-2 py-1 text-sm"
      >
        {models.data?.map((model) => (
          <option key={model.id} value={model.id}>
            {model.is_test_model ? `${model.id} (test model)` : model.id}
          </option>
        ))}
      </select>
    </label>
  )
}
