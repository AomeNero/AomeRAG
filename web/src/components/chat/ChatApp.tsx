import { useEffect, useRef, useState } from 'react'
import { Sidebar } from './Sidebar'
import { Composer } from './Composer'
import { WelcomeScreen } from './WelcomeScreen'
import { MessageList } from './MessageList'
import { IngestModal } from './IngestModal'
import type { ChatMessage } from '../../data/chat'
import {
  deleteSession as apiDeleteSession,
  getMessages,
  listSessions,
  streamChat,
  type ChatEvent,
  type Session,
} from '../../lib/api'

export function ChatApp() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streamingId, setStreamingId] = useState<string | null>(null)
  const [ingestOpen, setIngestOpen] = useState(false)

  const abortRef = useRef<AbortController | null>(null)
  const currentIdRef = useRef<string | null>(null)
  const counter = useRef(0)
  const nextId = (p: string) => `${p}-${counter.current++}`

  const loadSessions = async () => {
    try {
      setSessions(await listSessions())
    } catch {
      // keep sidebar as-is
    }
  }

  useEffect(() => {
    void loadSessions()
  }, [])

  const selectConv = async (id: string) => {
    if (streamingId) abortRef.current?.abort()
    setCurrentId(id)
    currentIdRef.current = id
    try {
      const history = await getMessages(id)
      setMessages(
        history.map((m, i) => ({ id: `${id}-${i}`, role: m.role, content: m.text })),
      )
    } catch {
      setMessages([])
    }
  }

  const newChat = () => {
    if (streamingId) abortRef.current?.abort()
    setCurrentId(null)
    currentIdRef.current = null
    setMessages([])
    setInput('')
  }

  const removeSession = async (id: string) => {
    try {
      await apiDeleteSession(id)
    } catch {
      // ignore
    }
    if (currentIdRef.current === id) newChat()
    void loadSessions()
  }

  const stop = () => abortRef.current?.abort()

  const applyEvent = (assistantId: string, ev: ChatEvent) => {
    switch (ev.type) {
      case 'session':
        if (!currentIdRef.current) {
          currentIdRef.current = ev.session_id
          setCurrentId(ev.session_id)
        }
        break
      case 'token':
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + ev.text } : m)),
        )
        break
      case 'tool_start':
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  toolEvents: [
                    ...(m.toolEvents ?? []),
                    { id: ev.tool_call_id, name: ev.name, status: 'running' as const },
                  ],
                }
              : m,
          ),
        )
        break
      case 'tool_result':
        setMessages((prev) =>
          prev.map((m) => {
            if (m.id !== assistantId) return m
            const toolEvents = (m.toolEvents ?? []).map((t) =>
              t.id === ev.tool_call_id
                ? {
                    ...t,
                    status: (ev.is_error ? 'error' : 'ok') as 'ok' | 'error',
                    content: ev.content,
                  }
                : t,
            )
            return { ...m, toolEvents }
          }),
        )
        break
      case 'clarify':
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: ev.question, isClarify: true } : m,
          ),
        )
        break
      case 'error':
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, error: ev.message } : m)),
        )
        break
      case 'final':
        break
    }
  }

  const runTurn = async (text: string, assistantId: string) => {
    setStreamingId(assistantId)
    const controller = new AbortController()
    abortRef.current = controller
    try {
      for await (const ev of streamChat(
        { message: text, session_id: currentIdRef.current ?? undefined },
        controller.signal,
      )) {
        applyEvent(assistantId, ev)
      }
    } catch (e) {
      if (!(e instanceof Error && e.name === 'AbortError')) {
        const msg = e instanceof Error ? e.message : '生成失败'
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, error: msg } : m)),
        )
      }
    } finally {
      setStreamingId(null)
      abortRef.current = null
      void loadSessions()
    }
  }

  const send = async () => {
    const text = input.trim()
    if (!text || streamingId) return
    setInput('')
    const userMsg: ChatMessage = { id: nextId('u'), role: 'user', content: text }
    const assistantId = nextId('a')
    setMessages((prev) => [
      ...prev,
      userMsg,
      { id: assistantId, role: 'assistant', content: '' },
    ])
    await runTurn(text, assistantId)
  }

  const regenerate = async () => {
    if (streamingId) return
    const lastUser = [...messages].reverse().find((m) => m.role === 'user')
    if (!lastUser) return
    const cut = messages.findIndex((m) => m.id === lastUser.id) + 1
    const assistantId = nextId('a')
    setMessages((prev) => [
      ...prev.slice(0, cut),
      { id: assistantId, role: 'assistant', content: '' },
    ])
    await runTurn(lastUser.content, assistantId)
  }

  const hasCurrent = messages.length > 0

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-foreground">
      <Sidebar
        sessions={sessions}
        currentId={currentId}
        onSelect={selectConv}
        onNewChat={newChat}
        onIngest={() => setIngestOpen(true)}
        onDelete={removeSession}
      />
      <main className="flex flex-1 flex-col overflow-hidden">
        {hasCurrent ? (
          <>
            <MessageList
              messages={messages}
              streamingId={streamingId}
              onRegenerate={regenerate}
            />
            <div className="pb-4 pt-2">
              <Composer
                value={input}
                onChange={setInput}
                onSend={send}
                onStop={stop}
                streaming={streamingId !== null}
              />
            </div>
          </>
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center pb-[10vh]">
            <WelcomeScreen />
            <div className="w-full pt-8">
              <Composer
                value={input}
                onChange={setInput}
                onSend={send}
                onStop={stop}
                streaming={streamingId !== null}
              />
            </div>
          </div>
        )}
      </main>
      {ingestOpen && (
        <IngestModal onClose={() => setIngestOpen(false)} onDone={() => void loadSessions()} />
      )}
    </div>
  )
}
