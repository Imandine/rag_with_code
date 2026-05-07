import { useCallback, useEffect, useState } from 'react'

const TOKEN_STORAGE_KEY = 'rag_admin_token'

export interface AuthState {
  isAdmin: boolean
  authRequired: boolean
  loading: boolean
  token: string | null
}

interface AuthStatusResponse {
  authenticated: boolean
  auth_required: boolean
}

function loadToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

function saveToken(t: string | null) {
  try {
    if (t) localStorage.setItem(TOKEN_STORAGE_KEY, t)
    else localStorage.removeItem(TOKEN_STORAGE_KEY)
  } catch {}
}

/**
 * Construit les headers d'auth à attacher aux fetches admin.
 * Exporté en dehors du hook pour pouvoir l'utiliser depuis n'importe où sans devoir
 * faire remonter useAuth dans tous les composants/hooks.
 */
export function getAuthHeaders(): Record<string, string> {
  const t = loadToken()
  return t ? { Authorization: `Bearer ${t}` } : {}
}

export function useAuth() {
  const [token, setToken] = useState<string | null>(() => loadToken())
  const [isAdmin, setIsAdmin] = useState(false)
  const [authRequired, setAuthRequired] = useState(true)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const headers: Record<string, string> = {}
      const t = loadToken()
      if (t) headers.Authorization = `Bearer ${t}`
      const res = await fetch('/api/auth/status', { headers })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: AuthStatusResponse = await res.json()
      setAuthRequired(data.auth_required)
      setIsAdmin(data.authenticated)
      // Si le serveur dit que le token n'est plus valide, on le purge
      if (data.auth_required && !data.authenticated && t) {
        saveToken(null)
        setToken(null)
      }
    } catch {
      // backend indisponible : on suppose auth requise et non connecté
      setAuthRequired(true)
      setIsAdmin(false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const login = useCallback(
    async (rawToken: string): Promise<{ ok: boolean; error?: string }> => {
      const trimmed = rawToken.trim()
      if (!trimmed) return { ok: false, error: 'Jeton vide' }
      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: trimmed }),
        })
        if (!res.ok) {
          let err = `HTTP ${res.status}`
          try {
            const data = await res.json()
            err = data.detail ?? err
          } catch {}
          return { ok: false, error: err }
        }
        saveToken(trimmed)
        setToken(trimmed)
        setIsAdmin(true)
        setAuthRequired(true)
        return { ok: true }
      } catch (e) {
        return { ok: false, error: e instanceof Error ? e.message : 'Erreur réseau' }
      }
    },
    [],
  )

  const logout = useCallback(() => {
    saveToken(null)
    setToken(null)
    setIsAdmin(false)
  }, [])

  return { token, isAdmin, authRequired, loading, login, logout, refresh }
}
