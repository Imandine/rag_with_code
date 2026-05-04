import {
  CheckCircle2,
  AlertCircle,
  Upload,
  FileText,
  Scissors,
  Sparkles,
  Database,
  Loader2,
} from 'lucide-react'
import type { DocumentStatus } from '../hooks/useDocuments'

interface StatusConfig {
  label: string
  classes: string
  Icon: typeof CheckCircle2
  pulse: boolean
}

const STATUS_MAP: Record<DocumentStatus, StatusConfig> = {
  uploaded: {
    label: 'Téléversé',
    classes: 'bg-slate-700/60 text-slate-200 border-slate-600',
    Icon: Upload,
    pulse: true,
  },
  converting: {
    label: 'Conversion',
    classes: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    Icon: FileText,
    pulse: true,
  },
  markdown_stored: {
    label: 'Markdown prêt',
    classes: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    Icon: FileText,
    pulse: true,
  },
  chunking: {
    label: 'Découpage',
    classes: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    Icon: Scissors,
    pulse: true,
  },
  embedding: {
    label: 'Embeddings',
    classes: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    Icon: Sparkles,
    pulse: true,
  },
  indexing: {
    label: 'Indexation',
    classes: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    Icon: Database,
    pulse: true,
  },
  done: {
    label: 'Indexé',
    classes: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    Icon: CheckCircle2,
    pulse: false,
  },
  error: {
    label: 'Erreur',
    classes: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    Icon: AlertCircle,
    pulse: false,
  },
}

export function StatusPill({ status }: { status: DocumentStatus }) {
  const cfg = STATUS_MAP[status] ?? STATUS_MAP.uploaded
  const { label, classes, Icon, pulse } = cfg

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium ${classes}`}
    >
      {pulse ? (
        <Loader2 className="w-3 h-3 animate-spin" />
      ) : (
        <Icon className="w-3 h-3" />
      )}
      {label}
    </span>
  )
}

const PIPELINE_STEPS: { status: DocumentStatus; label: string }[] = [
  { status: 'uploaded',        label: 'Réception' },
  { status: 'converting',      label: 'Conversion' },
  { status: 'chunking',        label: 'Découpage' },
  { status: 'embedding',       label: 'Embeddings' },
  { status: 'indexing',        label: 'Indexation' },
]

function stageIndex(status: DocumentStatus): number {
  if (status === 'done') return PIPELINE_STEPS.length
  if (status === 'markdown_stored') return 2
  const idx = PIPELINE_STEPS.findIndex(s => s.status === status)
  return idx >= 0 ? idx : 0
}

export const PIPELINE_STAGES = PIPELINE_STEPS.map(s => s.status)

export function PipelineDots({ status }: { status: DocumentStatus }) {
  const currentIndex = stageIndex(status)
  const isError = status === 'error'

  return (
    <div className="flex gap-1 items-center">
      {PIPELINE_STEPS.map((_, i) => (
        <span
          key={i}
          className={`w-1.5 h-1.5 rounded-full transition-colors ${
            isError
              ? 'bg-rose-500/60'
              : i < currentIndex
                ? i === currentIndex - 1 && status !== 'done'
                  ? 'bg-primary-400 animate-pulse-dot'
                  : 'bg-primary-500'
                : 'bg-slate-600'
          }`}
        />
      ))}
    </div>
  )
}

export function PipelineProgress({ status }: { status: DocumentStatus }) {
  const currentIndex = stageIndex(status)
  // +1 au numérateur pour que le premier statut affiche ~17% et non 0%
  const pct = Math.round(((currentIndex + 1) / (PIPELINE_STEPS.length + 1)) * 100)
  const currentLabel = PIPELINE_STEPS[currentIndex]?.label ?? ''

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between text-[10px] text-slate-400">
        <span className="flex items-center gap-1">
          <Loader2 className="w-3 h-3 animate-spin text-primary-400" />
          <span className="text-primary-300 font-medium">{currentLabel}</span>
        </span>
        <span>{pct}%</span>
      </div>
      <div className="relative h-1 rounded-full bg-slate-700/80 overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-primary-500 transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-primary-400/50 blur-sm transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex justify-between">
        {PIPELINE_STEPS.map((step, i) => (
          <span
            key={step.status}
            className={`text-[9px] transition-colors ${
              i < currentIndex
                ? 'text-primary-400'
                : i === currentIndex
                  ? 'text-primary-300 font-medium'
                  : 'text-slate-600'
            }`}
          >
            {step.label}
          </span>
        ))}
      </div>
    </div>
  )
}
