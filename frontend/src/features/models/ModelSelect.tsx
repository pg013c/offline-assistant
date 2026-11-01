import { useEffect, useRef, useState, type JSX } from 'react'

import { useModels } from './useModels'

interface ModelSelectProps {
  // The model the user picked; the API's default until they pick one.
  value: string | undefined
  onChange: (model: string) => void
}

/** Chooses the model that answers the next question (FR-62). */
export function ModelSelect({ value, onChange }: ModelSelectProps): JSX.Element {
  const models = useModels()
  const [notice, setNotice] = useState<string | null>(null)
  // The default, or the first listed model while the default does not answer.
  const fallback = models.data?.find((model) => model.is_default)?.id ?? models.data?.[0]?.id
  const shown = value ?? fallback
  // The model shown before the list last changed.
  const previous = useRef<string | undefined>(undefined)

  useEffect(() => {
    if (!models.data) return
    const before = previous.current
    previous.current = shown
    // A model that stopped answering leaves the list (F-09b); questions go to the fallback.
    if (before === undefined || models.data.some((model) => model.id === before)) return
    if (fallback === undefined) return
    setNotice(`${before} stopped answering. Questions now go to ${fallback}.`)
    previous.current = fallback
    onChange(fallback)
  }, [models.data, shown, fallback, onChange])

  return (
    <div className="flex flex-col gap-1">
      <label className="flex items-center gap-2 text-xs text-gray-600">
        Model
        <select
          value={shown ?? ''}
          disabled={!models.data}
          onChange={(event) => {
            setNotice(null)
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
      {notice && (
        <p role="status" className="text-xs text-amber-700">
          {notice}
        </p>
      )}
    </div>
  )
}
