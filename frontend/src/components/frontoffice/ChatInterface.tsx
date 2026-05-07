import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Send, Trash2, ChevronDown, ChevronRight, MessageSquare } from 'lucide-react'
import { useChat, type ChatMessage, type ChatSource } from '../../hooks/useChat'
import { useAuth } from '../../hooks/useAuth'

export function ChatInterface() {
  const [input, setInput] = useState('')
  const [expandedSources, setExpandedSources] = useState<Record<number, boolean>>({})
  const { messages, sendQuery, loading, clearHistory } = useChat()
  const { isAdmin } = useAuth()
  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    const nearBottom = distanceFromBottom < 200
    bottomRef.current?.scrollIntoView({ behavior: nearBottom ? 'smooth' : 'auto' })
  }, [messages])

  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    const lineHeight = 24
    const max = lineHeight * 4 + 16
    ta.style.height = Math.min(ta.scrollHeight, max) + 'px'
  }, [input])

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!input.trim() || loading) return
    sendQuery(input.trim())
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const toggleSources = (i: number) => {
    setExpandedSources(prev => ({ ...prev, [i]: !prev[i] }))
  }

  const isStreaming = (msg: ChatMessage) =>
    msg.role === 'assistant' && msg.content === '' && loading

  return (
    <div className="flex flex-col h-full">
      <header className="px-6 py-4 border-b border-slate-700/60 flex items-center justify-between backdrop-blur-sm bg-slate-900/40">
        <div>
          <h1 className="text-base font-semibold text-white">Chat</h1>
          <p className="text-xs text-slate-400">
            Posez vos questions sur vos documents indexés
          </p>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearHistory}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-white hover:bg-slate-700/60 border border-slate-700 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Effacer l'historique
          </button>
        )}
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-6">
          {messages.length === 0 ? (
            <EmptyState />
          ) : (
            <div className="flex flex-col gap-5">
              {messages.map((msg, i) => (
                <MessageBubble
                  key={i}
                  msg={msg}
                  streaming={isStreaming(msg)}
                  expanded={!!expandedSources[i]}
                  onToggle={() => toggleSources(i)}
                  showSources={isAdmin}
                />
              ))}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <form
        onSubmit={handleSubmit}
        className="border-t border-slate-700/60 bg-slate-900/60 backdrop-blur-sm"
      >
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-end gap-3">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Posez votre question..."
              disabled={loading}
              rows={1}
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 disabled:opacity-50 leading-6 max-h-28"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="shrink-0 inline-flex items-center justify-center w-11 h-11 rounded-xl bg-primary-600 hover:bg-primary-500 disabled:bg-slate-700 disabled:text-slate-500 text-white transition-colors shadow-lg shadow-primary-900/30 disabled:shadow-none"
            aria-label="Envoyer"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center text-center py-20 animate-fade-in">
      <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center shadow-xl shadow-primary-900/40 mb-5">
        <MessageSquare className="w-7 h-7 text-white" />
      </div>
      <h2 className="text-xl font-semibold text-white mb-2">
        Posez votre première question
      </h2>
      <p className="text-sm text-slate-400 max-w-sm">
        Interrogez vos documents indexés. Les réponses sont accompagnées des
        sources utilisées.
      </p>
    </div>
  )
}

function MessageBubble({
  msg,
  streaming,
  expanded,
  onToggle,
  showSources,
}: {
  msg: ChatMessage
  streaming: boolean
  expanded: boolean
  onToggle: () => void
  showSources: boolean
}) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex flex-col animate-fade-in ${isUser ? 'items-end' : 'items-start'}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
          isUser
            ? 'bg-primary-600 text-white rounded-br-sm'
            : 'bg-slate-800 border border-slate-700/60 text-slate-100 rounded-bl-sm'
        }`}
      >
        {streaming ? (
          <TypingIndicator />
        ) : isUser ? (
          <p className="whitespace-pre-wrap">{msg.content}</p>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none prose-p:my-2 prose-headings:my-3 prose-pre:bg-slate-900 prose-pre:border prose-pre:border-slate-700 prose-code:text-primary-300 prose-code:before:hidden prose-code:after:hidden prose-a:text-primary-300">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
          </div>
        )}
      </div>

      {!isUser && showSources && msg.sources && msg.sources.length > 0 && (
        <div className="mt-2 max-w-[85%] w-full">
          <button
            onClick={onToggle}
            className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            {expanded ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" />
            )}
            {msg.sources.length} source{msg.sources.length > 1 ? 's' : ''}
          </button>
          {expanded && (
            <div className="mt-2 flex flex-col gap-2 animate-fade-in">
              {msg.sources.map((src, j) => (
                <SourceCard key={j} src={src} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function SourceCard({ src }: { src: ChatSource }) {
  const filename = (src.metadata.source as string | undefined) ?? 'document'
  const heading = src.metadata.h1 as string | undefined
  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-800/40 p-3">
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="text-xs">
          <span className="font-semibold text-slate-200">{filename}</span>
          {heading && <span className="text-slate-400"> — {heading}</span>}
        </div>
        <span className="shrink-0 inline-flex items-center px-1.5 py-0.5 rounded-md bg-primary-500/15 text-primary-300 border border-primary-500/30 text-[10px] font-mono">
          {src.score.toFixed(3)}
        </span>
      </div>
      <p className="text-xs text-slate-400 leading-relaxed line-clamp-3">
        {src.text}
      </p>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex items-center py-1">
      <span className="typing-dot" style={{ animationDelay: '0ms' }} />
      <span className="typing-dot" style={{ animationDelay: '160ms' }} />
      <span className="typing-dot" style={{ animationDelay: '320ms' }} />
    </div>
  )
}
