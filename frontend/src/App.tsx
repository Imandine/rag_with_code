import { useEffect, useState } from 'react'
import { LogOut, MessageSquare, FileText, Sparkles, ShieldCheck } from 'lucide-react'
import { DocumentList } from './components/backoffice/DocumentList'
import { AdminGate } from './components/backoffice/AdminGate'
import { ChatInterface } from './components/frontoffice/ChatInterface'
import { useAuth } from './hooks/useAuth'

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
  const { isAdmin, authRequired, loading, login, logout } = useAuth()

  useEffect(() => {
    try {
      localStorage.setItem(VIEW_STORAGE_KEY, view)
    } catch {}
  }, [view])

  const showAdminGate = view === 'documents' && authRequired && !isAdmin

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
            adminBadge={authRequired && isAdmin}
            locked={authRequired && !isAdmin}
          />
        </nav>

        <div className="px-3 py-3 border-t border-slate-700/60 flex flex-col gap-2">
          {authRequired && isAdmin && (
            <button
              onClick={() => {
                logout()
                setView('chat')
              }}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-slate-300 hover:text-white hover:bg-slate-700/40 border border-transparent hover:border-slate-700 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
              Déconnexion
            </button>
          )}
          <span className="px-2 text-[10px] text-slate-500">v{__APP_VERSION__}</span>
        </div>
      </aside>

      <main className="flex-1 min-w-0 relative bg-gradient-to-br from-slate-900 via-slate-900 to-slate-950">
        <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_top_right,rgba(99,102,241,0.08),transparent_50%)]" />
        <div className="relative h-full">
          {view === 'chat' ? (
            <ChatInterface />
          ) : showAdminGate ? (
            <AdminGate loading={loading} onLogin={login} />
          ) : (
            <DocumentList />
          )}
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
  adminBadge,
  locked,
}: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
  adminBadge?: boolean
  locked?: boolean
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
      <span className="flex-1 text-left">{label}</span>
      {adminBadge && (
        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" aria-label="Connecté admin" />
      )}
      {locked && (
        <ShieldCheck className="w-3.5 h-3.5 text-slate-500" aria-label="Accès admin requis" />
      )}
    </button>
  )
}
