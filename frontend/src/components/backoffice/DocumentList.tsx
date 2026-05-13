import { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Trash2,
  Eye,
  Copy,
  Check,
  X,
  FileText,
  Loader2,
  Inbox,
  RotateCcw,
  Square,
  CheckSquare,
} from 'lucide-react'
import { useDocuments, type RagDocument } from '../../hooks/useDocuments'
import { getAuthHeaders } from '../../hooks/useAuth'
import { DocumentUpload } from './DocumentUpload'
import { StatusPill, PipelineDots, PipelineProgress, PageProgress } from '../StatusPill'

function fileExtension(filename: string): string {
  const idx = filename.lastIndexOf('.')
  return idx >= 0 ? filename.slice(idx + 1).toUpperCase() : 'FILE'
}

export function DocumentList() {
  const { documents, deleteDocument, deleteDocuments, retryDocument, refresh, loading } =
    useDocuments()
  const [previewDoc, setPreviewDoc] = useState<RagDocument | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [bulkBusy, setBulkBusy] = useState(false)

  // Nettoyage : si un doc disparaît (suppression externe), on le retire de la sélection.
  const validIds = useMemo(() => new Set(documents.map(d => d.doc_id)), [documents])
  useEffect(() => {
    setSelected(prev => {
      const next = new Set<string>()
      for (const id of prev) if (validIds.has(id)) next.add(id)
      return next.size === prev.size ? prev : next
    })
  }, [validIds])

  const toggleSelect = (docId: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(docId)) next.delete(docId)
      else next.add(docId)
      return next
    })
  }

  const allSelected = documents.length > 0 && selected.size === documents.length
  const toggleSelectAll = () => {
    if (allSelected) setSelected(new Set())
    else setSelected(new Set(documents.map(d => d.doc_id)))
  }

  const handleDelete = (doc: RagDocument) => {
    if (window.confirm(`Supprimer « ${doc.filename} » ?`)) {
      deleteDocument(doc.doc_id)
    }
  }

  const handleRetry = async (doc: RagDocument) => {
    const res = await retryDocument(doc.doc_id)
    if (!res.ok) {
      window.alert(`Impossible de relancer l'indexation : ${res.error ?? 'erreur inconnue'}`)
    }
  }

  const handleBulkDelete = async () => {
    if (selected.size === 0 || bulkBusy) return
    if (!window.confirm(`Supprimer les ${selected.size} documents sélectionnés ?`)) return
    setBulkBusy(true)
    try {
      const res = await deleteDocuments(Array.from(selected))
      if (!res.ok) {
        window.alert(`Suppression groupée échouée : ${res.error ?? 'erreur inconnue'}`)
      } else {
        setSelected(new Set())
      }
    } finally {
      setBulkBusy(false)
    }
  }

  return (
    <div className="h-full flex flex-col">
      <header className="px-6 py-4 border-b border-slate-700/60 flex items-center justify-between backdrop-blur-sm bg-slate-900/40">
        <div>
          <h1 className="text-base font-semibold text-white">Documents</h1>
          <p className="text-xs text-slate-400">
            Téléversez et gérez la base documentaire indexée
          </p>
        </div>
        <span className="text-xs text-slate-400">
          {documents.length} document{documents.length > 1 ? 's' : ''}
        </span>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto px-6 py-6 flex flex-col gap-6">
          <DocumentUpload onUpload={refresh} />

          {documents.length > 0 && (
            <div className="flex items-center justify-between rounded-xl border border-slate-700/60 bg-slate-800/40 px-4 py-2.5">
              <button
                onClick={toggleSelectAll}
                className="inline-flex items-center gap-2 text-xs font-medium text-slate-200 hover:text-white"
              >
                {allSelected ? (
                  <CheckSquare className="w-4 h-4 text-primary-300" />
                ) : (
                  <Square className="w-4 h-4 text-slate-400" />
                )}
                {allSelected ? 'Tout désélectionner' : 'Tout sélectionner'}
                {selected.size > 0 && (
                  <span className="ml-1 text-slate-400">({selected.size})</span>
                )}
              </button>
              <button
                onClick={handleBulkDelete}
                disabled={selected.size === 0 || bulkBusy}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-rose-300 hover:text-rose-200 hover:bg-rose-500/10 border border-rose-500/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent"
              >
                {bulkBusy ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Trash2 className="w-3.5 h-3.5" />
                )}
                Supprimer la sélection
              </button>
            </div>
          )}

          {documents.length === 0 ? (
            <EmptyDocs loading={loading} />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {documents.map(doc => (
                <DocumentCard
                  key={doc.doc_id}
                  doc={doc}
                  selected={selected.has(doc.doc_id)}
                  onToggleSelect={() => toggleSelect(doc.doc_id)}
                  onDelete={() => handleDelete(doc)}
                  onPreview={() => setPreviewDoc(doc)}
                  onRetry={() => handleRetry(doc)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {previewDoc && (
        <MarkdownModal doc={previewDoc} onClose={() => setPreviewDoc(null)} />
      )}
    </div>
  )
}

function EmptyDocs({ loading }: { loading: boolean }) {
  return (
    <div className="rounded-2xl border border-slate-700/60 bg-slate-800/30 px-6 py-16 flex flex-col items-center text-center animate-fade-in">
      <div className="w-12 h-12 rounded-xl bg-slate-700/60 flex items-center justify-center mb-3">
        {loading ? (
          <Loader2 className="w-6 h-6 text-slate-300 animate-spin" />
        ) : (
          <Inbox className="w-6 h-6 text-slate-300" />
        )}
      </div>
      <p className="text-sm font-medium text-white">
        {loading ? 'Chargement…' : 'Aucun document indexé'}
      </p>
      <p className="text-xs text-slate-400 mt-1">
        Téléversez votre premier document pour commencer
      </p>
    </div>
  )
}

function DocumentCard({
  doc,
  selected,
  onToggleSelect,
  onDelete,
  onPreview,
  onRetry,
}: {
  doc: RagDocument
  selected: boolean
  onToggleSelect: () => void
  onDelete: () => void
  onPreview: () => void
  onRetry: () => void | Promise<void>
}) {
  const [copied, setCopied] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const ext = fileExtension(doc.filename)
  const canRetry = doc.status === 'error' && Boolean(doc.raw_key)

  const handleRetryClick = async () => {
    if (retrying) return
    setRetrying(true)
    try {
      await onRetry()
    } finally {
      setRetrying(false)
    }
  }

  const copyError = async () => {
    if (!doc.error) return
    try {
      await navigator.clipboard.writeText(doc.error)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {}
  }

  return (
    <div
      className={`rounded-xl border bg-slate-800/40 p-4 flex flex-col gap-3 transition-colors animate-fade-in ${
        selected
          ? 'border-primary-500/60 bg-primary-500/5'
          : 'border-slate-700/60 hover:border-slate-600/80'
      }`}
    >
      <div className="flex items-start gap-3">
        <button
          onClick={onToggleSelect}
          aria-label={selected ? 'Désélectionner' : 'Sélectionner'}
          className="shrink-0 mt-1 text-slate-400 hover:text-primary-300 transition-colors"
        >
          {selected ? (
            <CheckSquare className="w-4 h-4 text-primary-300" />
          ) : (
            <Square className="w-4 h-4" />
          )}
        </button>
        <div className="shrink-0 w-10 h-10 rounded-lg bg-slate-900/60 border border-slate-700 flex items-center justify-center">
          <FileText className="w-5 h-5 text-slate-300" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-white truncate" title={doc.filename}>
              {doc.filename}
            </span>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-900/60 text-slate-400 border border-slate-700">
              {ext}
            </span>
            {typeof doc.num_pages === 'number' && doc.num_pages > 0 ? (
              <span className="text-[10px] text-slate-500">
                {doc.num_pages} page{doc.num_pages > 1 ? 's' : ''}
              </span>
            ) : typeof doc.num_words === 'number' && doc.num_words > 0 ? (
              <span className="text-[10px] text-slate-500">
                {doc.num_words.toLocaleString('fr-FR')} mots
              </span>
            ) : null}
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <StatusPill status={doc.status} />
        {(doc.status === 'done' || doc.status === 'error') && (
          <PipelineDots status={doc.status} />
        )}
      </div>

      {!['done', 'error'].includes(doc.status) && (
        typeof doc.num_pages === 'number' && doc.num_pages > 0 ? (
          <PageProgress
            pagesDone={doc.pages_done ?? 0}
            totalPages={doc.num_pages}
            ocrUsed={doc.ocr_used}
          />
        ) : (
          <PipelineProgress status={doc.status} />
        )
      )}

      {doc.status === 'done' && typeof doc.chunks === 'number' && (
        <div className="text-xs text-slate-400">
          <span className="font-medium text-slate-200">{doc.chunks}</span> chunks indexés
        </div>
      )}

      {doc.status === 'error' && doc.error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-2.5 text-xs text-rose-200">
          <div className="flex items-start justify-between gap-2">
            <p className="flex-1 break-words">{doc.error}</p>
            <button
              onClick={copyError}
              className="shrink-0 p-1 rounded hover:bg-rose-500/20 text-rose-300"
              aria-label="Copier l'erreur"
            >
              {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 mt-1">
        {doc.markdown_key && (
          <button
            onClick={onPreview}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-200 bg-slate-700/40 hover:bg-slate-700 border border-slate-700 transition-colors"
          >
            <Eye className="w-3.5 h-3.5" />
            Voir le markdown
          </button>
        )}
        {canRetry && (
          <button
            onClick={handleRetryClick}
            disabled={retrying}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-primary-200 bg-primary-500/15 hover:bg-primary-500/25 border border-primary-500/30 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            title="Relancer l'indexation depuis le fichier source"
          >
            {retrying ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <RotateCcw className="w-3.5 h-3.5" />
            )}
            Réindexer
          </button>
        )}
        <button
          onClick={onDelete}
          className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-rose-300 hover:text-rose-200 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/30 transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
          Supprimer
        </button>
      </div>
    </div>
  )
}

function MarkdownModal({ doc, onClose }: { doc: RagDocument; onClose: () => void }) {
  const [content, setContent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch(`/api/documents/${doc.doc_id}/markdown`, { headers: getAuthHeaders() })
      .then(async res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.text()
      })
      .then(text => {
        if (!cancelled) setContent(text)
      })
      .catch(err => {
        if (!cancelled) setError(err.message ?? 'Erreur de chargement')
      })
    return () => {
      cancelled = true
    }
  }, [doc.doc_id])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in"
      onClick={onClose}
    >
      <div
        className="bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-700/80">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-white truncate">{doc.filename}</h3>
            <p className="text-xs text-slate-400">Aperçu Markdown</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
            aria-label="Fermer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {error ? (
            <p className="text-sm text-rose-300">Erreur : {error}</p>
          ) : content === null ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 text-slate-400 animate-spin" />
            </div>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none prose-pre:bg-slate-950 prose-pre:border prose-pre:border-slate-700 prose-code:text-primary-300 prose-code:before:hidden prose-code:after:hidden">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
