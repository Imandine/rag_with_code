import { useState, useEffect } from 'react'

export interface ChatSource {
  text: string
  metadata: { source?: string; h1?: string; [k: string]: unknown }
  score: number
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: ChatSource[]
}

const STORAGE_KEY = 'rag_chat_history'

function loadHistory(): ChatMessage[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as ChatMessage[]) : []
  } catch {
    return []
  }
}

function saveHistory(messages: ChatMessage[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
  } catch {}
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadHistory())
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    saveHistory(messages)
  }, [messages])

  const sendQuery = async (query: string) => {
    setLoading(true)
    setMessages(prev => [...prev, { role: 'user', content: query }])
    setMessages(prev => [...prev, { role: 'assistant', content: '', sources: [] }])

    try {
      const response = await fetch('/api/query/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      })

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const lines = decoder.decode(value).split('\n')
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'sources') {
              setMessages(prev => [
                ...prev.slice(0, -1),
                { ...prev[prev.length - 1], sources: data.sources },
              ])
            } else if (data.type === 'token') {
              setMessages(prev => [
                ...prev.slice(0, -1),
                { ...prev[prev.length - 1], content: prev[prev.length - 1].content + data.content },
              ])
            }
          } catch {}
        }
      }
    } finally {
      setLoading(false)
    }
  }

  const clearHistory = () => {
    setMessages([])
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {}
  }

  return { messages, sendQuery, loading, clearHistory }
}
