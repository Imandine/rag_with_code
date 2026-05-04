import { useEffect, useState } from 'react'
import { MessageSquare, FileText, Sparkles } from 'lucide-react'
import { DocumentList } from './components/backoffice/DocumentList'
import { ChatInterface } from './components/frontoffice/ChatInterface'

type View = 'chat' | 'documents'
const VIEW_STORAGE_KEY = 'rag_view'

function loadView(): View {
  try {
    const v = localStorage.getItem(VIEW_STORAGE_KEY)
    return v === 'documents' ? 'documents' : 'chat'
  } catch {
    return 'chat'
  }
}

export default function App() {
  const [view, setView] = useState<View>(() => loadView())

  useEffect(() => {
    try {
      localStorage.setItem(VIEW_STORAGE_KEY, view)
    } catch {}
  }, [view])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-900 text-slate-100">
      <aside className="w-60 shrink-0 bg-slate-800/80 border-r border-slate-700 flex flex-col">
        <div className="px-5 py-6 border-b border-slate-700/60">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center shadow-lg shadow-primary-900/40">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div className="flex flex-col leading-tight">
              <span className="text-sm font-semibold text-white">RAG</span>
              <span className="text-xs text-slate-400">Documents intelligents</span>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 flex flex-col gap-1">
          <NavButton
            active={view === 'chat'}
            onClick={() => setView('chat')}
            icon={<MessageSquare className="w-4 h-4" />}
            label="Chat"
          />
          <NavButton
            active={view === 'documents'}
            onClick={() => setView('documents')}
            icon={<FileText className="w-4 h-4" />}
            label="Documents"
          />
        </nav>

        <div className="px-5 py-4 border-t border-slate-700/60 text-xs text-slate-500">
          v0.1.0
        </div>
      </aside>

      <main className="flex-1 min-w-0 relative bg-gradient-to-br from-slate-900 via-slate-900 to-slate-950">
        <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_top_right,rgba(99,102,241,0.08),transparent_50%)]" />
        <div className="relative h-full">
          {view === 'chat' ? <ChatInterface /> : <DocumentList />}
        </div>
      </main>
    </div>
  )
}

function NavButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
        active
          ? 'bg-primary-500/15 text-primary-200 border border-primary-500/30'
          : 'text-slate-300 hover:bg-slate-700/40 border border-transparent'
      }`}
    >
      {icon}
      {label}
    </button>
  )
}
