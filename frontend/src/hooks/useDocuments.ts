import { useState, useEffect, useCallback } from 'react'
import { getAuthHeaders } from './useAuth'

export type DocumentStatus =
  | 'uploaded'
  | 'converting'
  | 'markdown_stored'
  | 'chunking'
  | 'embedding'
  | 'indexing'
  | 'done'
  | 'error'

export interface RagDocument {
  doc_id: string
  filename: string
  status: DocumentStatus
  uploaded_at?: string
  chunks?: number
  error?: string
  num_pages?: number | null
  num_words?: number | null
  pages_done?: number | null
  ocr_used?: boolean | null
  format?: string | null
  raw_key?: string
  markdown_key?: string
}

const PROCESSING_STATUSES: DocumentStatus[] = [
  'uploaded',
  'converting',
  'markdown_stored',
  'chunking',
  'embedding',
  'indexing',
]

export function useDocuments(enabled: boolean = true) {
  const [documents, setDocuments] = useState<RagDocument[]>([])
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    if (!enabled) return
    setLoading(true)
    try {
      const res = await fetch('/api/documents/', { headers: getAuthHeaders() })
      if (!res.ok) {
        setDocuments([])
        return
      }
      const data = await res.json()
      setDocuments(data.documents ?? [])
    } finally {
      setLoading(false)
    }
  }, [enabled])

  const deleteDocument = async (docId: string) => {
    await fetch(`/api/documents/${docId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    })
    refresh()
  }

  const deleteDocuments = async (
    docIds: string[],
  ): Promise<{ ok: boolean; deleted: number; error?: string }> => {
    if (docIds.length === 0) return { ok: true, deleted: 0 }
    try {
      const res = await fetch('/api/documents/batch-delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ doc_ids: docIds }),
      })
      if (!res.ok) {
        let err = `HTTP ${res.status}`
        try {
          const data = await res.json()
          err = data.detail ?? err
        } catch {}
        return { ok: false, deleted: 0, error: err }
      }
      const data = await res.json()
      refresh()
      return { ok: true, deleted: data.count ?? 0 }
    } catch (e) {
      return { ok: false, deleted: 0, error: e instanceof Error ? e.message : 'Erreur réseau' }
    }
  }

  const retryDocument = async (docId: string): Promise<{ ok: boolean; error?: string }> => {
    try {
      const res = await fetch(`/api/documents/${docId}/retry`, {
        method: 'POST',
        headers: getAuthHeaders(),
      })
      if (!res.ok) {
        let err = `HTTP ${res.status}`
        try {
          const data = await res.json()
          err = data.detail ?? err
        } catch {}
        return { ok: false, error: err }
      }
      refresh()
      return { ok: true }
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : 'Erreur réseau' }
    }
  }

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    if (!enabled) return
    const processing = documents.some(d => PROCESSING_STATUSES.includes(d.status))
    if (!processing) return
    const timer = setInterval(refresh, 2000)
    return () => clearInterval(timer)
  }, [documents, refresh, enabled])

  return { documents, deleteDocument, deleteDocuments, retryDocument, loading, refresh }
}
