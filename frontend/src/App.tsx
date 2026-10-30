import { ChatView } from './features/chat/ChatView'
import { LibraryPanel } from './features/library/LibraryPanel'
import { ApiStatus } from './features/status/ApiStatus'
import { NetworkBadge } from './features/status/NetworkBadge'

export function App() {
  return (
    <div className="min-h-screen bg-white text-gray-900">
      <header className="flex items-center justify-between border-b border-gray-200 px-6 py-3">
        <h1 className="text-lg font-semibold">Offline Assistant</h1>
        <div className="flex items-center gap-3">
          <NetworkBadge />
          <ApiStatus />
        </div>
      </header>
      <main className="mx-auto grid max-w-5xl gap-8 p-6 md:grid-cols-[1fr_2fr]">
        <LibraryPanel />
        <ChatView />
      </main>
    </div>
  )
}
