import { useState } from 'react'
import { KeyRound, Loader2, ShieldCheck } from 'lucide-react'

interface Props {
  loading: boolean
  onLogin: (token: string) => Promise<{ ok: boolean; error?: string }>
}

export function AdminGate({ loading, onLogin }: Props) {
  const [token, setToken] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (submitting || !token.trim()) return
    setSubmitting(true)
    setError(null)
    const res = await onLogin(token)
    if (!res.ok) {
      setError(res.error ?? 'Authentification refusée')
    }
    setSubmitting(false)
  }

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="w-6 h-6 text-slate-400 animate-spin" />
      </div>
    )
  }

  return (
    <div className="h-full flex items-center justify-center px-6">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-2xl border border-slate-700/60 bg-slate-800/60 backdrop-blur p-6 flex flex-col gap-5 shadow-2xl"
      >
        <div className="flex flex-col items-center gap-2">
          <div className="w-12 h-12 rounded-xl bg-primary-500/15 border border-primary-500/30 flex items-center justify-center">
            <ShieldCheck className="w-6 h-6 text-primary-300" />
          </div>
          <h2 className="text-base font-semibold text-white">Espace administrateur</h2>
          <p className="text-xs text-slate-400 text-center">
            Saisissez le jeton d'administration pour gérer les documents indexés.
          </p>
        </div>

        <label className="flex flex-col gap-1.5">
          <span className="text-xs text-slate-300">Jeton</span>
          <div className="relative">
            <KeyRound className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="password"
              autoComplete="off"
              autoFocus
              value={token}
              onChange={e => setToken(e.target.value)}
              className="w-full pl-9 pr-3 py-2 rounded-lg bg-slate-900/80 border border-slate-700 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-primary-500/60"
              placeholder="••••••••••••"
            />
          </div>
        </label>

        {error && (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting || !token.trim()}
          className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-primary-500 hover:bg-primary-400 text-white text-sm font-medium transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
          Se connecter
        </button>
      </form>
    </div>
  )
}
