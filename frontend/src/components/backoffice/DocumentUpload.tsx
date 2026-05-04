import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { UploadCloud, Loader2 } from 'lucide-react'

const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/html': ['.html'],
}

interface PendingUpload {
  name: string
  status: 'uploading' | 'done' | 'error'
}

export function DocumentUpload({ onUpload }: { onUpload: () => void }) {
  const [pending, setPending] = useState<PendingUpload[]>([])

  const onDrop = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return
      setPending(files.map(f => ({ name: f.name, status: 'uploading' })))

      await Promise.all(
        files.map(async (file, idx) => {
          const formData = new FormData()
          formData.append('file', file)
          try {
            const res = await fetch('/api/documents/upload', {
              method: 'POST',
              body: formData,
            })
            setPending(prev =>
              prev.map((p, i) =>
                i === idx ? { ...p, status: res.ok ? 'done' : 'error' } : p,
              ),
            )
          } catch {
            setPending(prev =>
              prev.map((p, i) => (i === idx ? { ...p, status: 'error' } : p)),
            )
          }
        }),
      )

      onUpload()
      setTimeout(() => setPending([]), 1500)
    },
    [onUpload],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    multiple: true,
  })

  const uploading = pending.some(p => p.status === 'uploading')

  return (
    <div className="flex flex-col gap-3">
      <div
        {...getRootProps()}
        className={`relative rounded-2xl border-2 border-dashed transition-colors cursor-pointer p-10 text-center ${
          isDragActive
            ? 'border-primary-500 bg-primary-500/10'
            : 'border-slate-700 bg-slate-800/40 hover:border-slate-600 hover:bg-slate-800/60'
        }`}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-3">
          <div
            className={`w-12 h-12 rounded-xl flex items-center justify-center ${
              isDragActive
                ? 'bg-primary-500/20 text-primary-300'
                : 'bg-slate-700/60 text-slate-300'
            }`}
          >
            {uploading ? (
              <Loader2 className="w-6 h-6 animate-spin" />
            ) : (
              <UploadCloud className="w-6 h-6" />
            )}
          </div>
          <div>
            <p className="text-sm font-medium text-white">
              {isDragActive
                ? 'Déposez les fichiers ici'
                : 'Glissez vos documents ou cliquez pour parcourir'}
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Formats supportés : PDF, DOCX, HTML — multiples fichiers acceptés
            </p>
          </div>
        </div>
      </div>

      {pending.length > 0 && (
        <div className="flex flex-col gap-1.5 animate-fade-in">
          {pending.map((p, i) => (
            <div
              key={i}
              className="flex items-center justify-between text-xs px-3 py-2 rounded-lg bg-slate-800/60 border border-slate-700"
            >
              <span className="text-slate-200 truncate">{p.name}</span>
              <span
                className={
                  p.status === 'uploading'
                    ? 'text-amber-300'
                    : p.status === 'done'
                      ? 'text-emerald-300'
                      : 'text-rose-300'
                }
              >
                {p.status === 'uploading'
                  ? 'Téléversement…'
                  : p.status === 'done'
                    ? 'Envoyé'
                    : 'Erreur'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
