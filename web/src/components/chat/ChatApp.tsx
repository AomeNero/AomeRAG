import { useEffect, useRef, useState } from 'react'
import { PanelLeft } from 'lucide-react'
import { Sidebar } from './Sidebar'
import { Composer } from './Composer'
import { WelcomeScreen } from './WelcomeScreen'
import { MessageList } from './MessageList'
import type { ChatMessage } from '../../data/chat'
import {
  deleteSession as apiDeleteSession,
  generateTitle,
  getMessages,
  getStats,
  listSessions,
  patchSessionTitle,
  streamChat,
  type ChatEvent,
  type Session,
  type SystemStats,
} from '../../lib/api'

const COLLAPSE_KEY = 'aome_sidebar_collapsed'

export function ChatApp() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streamingId, setStreamingId] = useState<string | null>(null)
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [collapsed, setCollapsed] = useState<boolean>(
    () => localStorage.getItem(COLLAPSE_KEY) === '1',
  )
  const [searchQuery, setSearchQuery] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  const currentIdRef = useRef<string | null>(null)
  const turnStartRef = useRef<number | null>(null)
  const counter = useRef(0)
  const nextId = (p: string) => `${p}-${counter.current++}`

  useEffect(() => {
    localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0')
  }, [collapsed])

  const loadSessions = async () => {
    try {
      setSessions(await listSessions())
    } catch {
      // keep sidebar as-is
    }
  }
  const loadStats = async () => {
    try {
      setStats(await getStats())
    } catch {
      // keep last stats
    }
  }

  useEffect(() => {
    void loadSessions()
    void loadStats()
  }, [])

  const selectConv = async (id: string) => {
    if (streamingId) abortRef.current?.abort()
    setCurrentId(id)
    currentIdRef.current = id
    setSearchQuery(null)
    try {
      const history = await getMessages(id)
      setMessages(
        history.map((m, i) => ({
          id: `${id}-${i}`,
          role: m.role,
          content: m.text,
          toolEvents: m.toolEvents,
          isClarify: m.toolEvents?.some((t) => t.name === 'clarify') ?? undefined,
        })),
      )
    } catch {
      setMessages([])
    }
  }

  const onSearchHighlight = async (sessionId: string, query: string) => {
    await selectConv(sessionId)
    setSearchQuery(query)
  }

  const newChat = () => {
    if (streamingId) abortRef.current?.abort()
    setCurrentId(null)
    currentIdRef.current = null
    setMessages([])
    setInput('')
    setSearchQuery(null)
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

  const renameSession = async (id: string, title: string) => {
    try {
      await patchSessionTitle(id, title)
      await loadSessions()
    } catch {
      // ignore
    }
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
        if (!turnStartRef.current) turnStartRef.current = performance.now()
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
                    status: (ev.cancelled ? 'cancelled' : ev.is_error ? 'error' : 'ok') as
                      | 'ok'
                      | 'error'
                      | 'cancelled',
                    content: ev.content,
                    details: ev.details,
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
        if (turnStartRef.current) {
          const elapsed = (performance.now() - turnStartRef.current) / 1000
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, turnElapsed: elapsed } : m)),
          )
          turnStartRef.current = null
        }
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
    const wasNew = currentIdRef.current === null
    setInput('')
    setSearchQuery(null)
    const userMsg: ChatMessage = { id: nextId('u'), role: 'user', content: text }
    const assistantId = nextId('a')
    setMessages((prev) => [
      ...prev,
      userMsg,
      { id: assistantId, role: 'assistant', content: '' },
    ])
    await runTurn(text, assistantId)
    if (wasNew && currentIdRef.current) {
      try {
        await generateTitle(currentIdRef.current)
        await loadSessions()
      } catch {
        // title generation is best-effort
      }
    }
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
      {!collapsed && (
        <Sidebar
          sessions={sessions}
          currentId={currentId}
          stats={stats}
          onSelect={selectConv}
          onNewChat={newChat}
          onDelete={removeSession}
          onRename={renameSession}
          onCollapse={() => setCollapsed(true)}
          onSearchHighlight={onSearchHighlight}
        />
      )}
      <main className="relative flex flex-1 flex-col overflow-hidden">
        {collapsed && (
          <button
            onClick={() => setCollapsed(false)}
            className="absolute left-3 top-3 z-10 rounded-full border border-line bg-white p-2 text-foreground shadow-sm transition hover:bg-hover"
            title="展开侧边栏"
          >
            <PanelLeft className="h-4 w-4" strokeWidth={1.75} />
          </button>
        )}
        {hasCurrent ? (
          <>
            <MessageList
              messages={messages}
              streamingId={streamingId}
              onRegenerate={regenerate}
              searchQuery={searchQuery}
              sessionId={currentId}
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
    </div>
  )
}
