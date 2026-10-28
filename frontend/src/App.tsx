import { ApiStatus } from './features/status/ApiStatus'

export function App() {
  return (
    <div className="min-h-screen bg-white text-gray-900">
      <header className="flex items-center justify-between border-b border-gray-200 px-6 py-3">
        <h1 className="text-lg font-semibold">Offline Assistant</h1>
        <ApiStatus />
      </header>
      <main className="mx-auto max-w-3xl p-6" />
    </div>
  )
}
