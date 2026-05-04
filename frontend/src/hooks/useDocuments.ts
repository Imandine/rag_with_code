import { useState, useEffect, useCallback } from 'react'

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

export function useDocuments() {
  const [documents, setDocuments] = useState<RagDocument[]>([])
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/documents/')
      const data = await res.json()
      setDocuments(data.documents ?? [])
    } finally {
      setLoading(false)
    }
  }, [])

  const deleteDocument = async (docId: string) => {
    await fetch(`/api/documents/${docId}`, { method: 'DELETE' })
    refresh()
  }

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    const processing = documents.some(d => PROCESSING_STATUSES.includes(d.status))
    if (!processing) return
    const timer = setInterval(refresh, 2000)
    return () => clearInterval(timer)
  }, [documents, refresh])

  return { documents, deleteDocument, loading, refresh }
}
