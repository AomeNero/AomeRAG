import { useEffect, useState, type KeyboardEvent } from 'react'
import { Check, PanelLeft, Pencil, Plus, Search, Trash2, X } from 'lucide-react'
import { searchSessions, type Session, type SessionHit, type SystemStats } from '../../lib/api'
import { cn } from '../../lib/utils'

interface Props {
  sessions: Session[]
  currentId: string | null
  stats: SystemStats | null
  onSelect: (id: string) => void
  onNewChat: () => void
  onDelete: (id: string) => void
  onRename: (id: string, title: string) => void
  onCollapse: () => void
  onSearchHighlight: (sessionId: string, query: string) => void
}

const DAY = 86400000

function groupSessions(sessions: Session[]): { label: string; items: Session[] }[] {
  const now = Date.now()
  const buckets: { label: string; items: Session[] }[] = [
    { label: '今天', items: [] },
    { label: '7 天内', items: [] },
    { label: '30 天内', items: [] },
    { label: '更早', items: [] },
  ]
  for (const s of [...sessions].sort((a, b) => b.updated_at - a.updated_at)) {
    const age = now - s.updated_at * 1000
    if (age < DAY) buckets[0].items.push(s)
    else if (age < 7 * DAY) buckets[1].items.push(s)
    else if (age < 30 * DAY) buckets[2].items.push(s)
    else buckets[3].items.push(s)
  }
  return buckets.filter((b) => b.items.length > 0)
}

export function Sidebar({
  sessions,
  currentId,
  stats,
  onSelect,
  onNewChat,
  onDelete,
  onRename,
  onCollapse,
  onSearchHighlight,
}: Props) {
  const groups = groupSessions(sessions)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')

  const [searchOpen, setSearchOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SessionHit[]>([])

  useEffect(() => {
    const q = query.trim()
    if (!q) {
      setResults([])
      return
    }
    let cancelled = false
    const t = setTimeout(async () => {
      try {
        const r = await searchSessions(q)
        if (!cancelled) setResults(r)
      } catch {
        if (!cancelled) setResults([])
      }
    }, 300)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [query])

  const startEdit = (id: string, title: string) => {
    setEditingId(id)
    setDraft(title)
  }
  const commitEdit = () => {
    if (editingId && draft.trim()) onRename(editingId, draft.trim())
    setEditingId(null)
  }
  const onDraftKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') commitEdit()
    if (e.key === 'Escape') setEditingId(null)
  }
  const pickResult = (h: SessionHit) => {
    onSearchHighlight(h.session_id, query.trim())
    setSearchOpen(false)
  }

  return (
    <aside className="flex h-full w-[261px] shrink-0 flex-col bg-field px-3 pb-2 pt-1.5">
      <div className="flex h-12 items-center justify-between pb-2.5 pl-1 pt-[15px]">
        <div className="flex items-center gap-2 pl-1">
          <img src="/assets/logo.svg" alt="AomeRAG" className="h-6 w-6" />
          <span className="text-base font-semibold text-foreground">AomeRAG</span>
        </div>
        <div className="flex items-center gap-3 text-muted">
          <button
            onClick={() => {
              setSearchOpen((v) => !v)
              setQuery('')
            }}
            className="rounded-full p-1 transition hover:bg-hover"
            title="搜索会话内容"
          >
            <Search className="h-4 w-4" strokeWidth={1.75} />
          </button>
          <button onClick={onCollapse} className="rounded-full p-1 transition hover:bg-hover" title="折叠侧边栏">
            <PanelLeft className="h-4 w-4" strokeWidth={1.75} />
          </button>
        </div>
      </div>

      {searchOpen && (
        <div className="mb-2">
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索会话内容…"
            className="h-9 w-full rounded-lg border border-line bg-white px-2.5 text-sm outline-none focus:border-brand"
          />
          <div className="scrollbar-none mt-1 max-h-64 overflow-y-auto">
            {results.map((h, i) => (
              <button
                key={`${h.session_id}-${i}`}
                onClick={() => pickResult(h)}
                className="block w-full rounded-lg px-2 py-1.5 text-left transition hover:bg-hover"
              >
                <div className="truncate text-sm text-foreground">{h.title}</div>
                <div className="truncate text-xs text-muted">{h.snippet}</div>
              </button>
            ))}
            {query.trim() && results.length === 0 && (
              <div className="px-2 py-2 text-xs text-muted">无匹配</div>
            )}
          </div>
        </div>
      )}

      <button
        onClick={onNewChat}
        className="flex h-10 items-center justify-center gap-2 rounded-full bg-white px-4 text-sm font-medium text-foreground transition hover:shadow-sm"
      >
        <Plus className="h-4 w-4" strokeWidth={2} />
        <span>开启新对话</span>
      </button>
      <div className="scrollbar-none mt-4 flex-1 overflow-y-auto">
        {groups.map((group) => (
          <div key={group.label} className="mb-1">
            <div className="sticky top-0 bg-field px-2.5 py-0.5 text-xs font-medium text-muted">
              {group.label}
            </div>
            {group.items.map((s) => (
              <div
                key={s.id}
                className={cn(
                  'group flex h-10 items-center rounded-xl px-2.5 text-sm transition',
                  currentId === s.id ? 'bg-hover text-foreground' : 'text-foreground hover:bg-hover',
                )}
              >
                {editingId === s.id ? (
                  <div className="flex flex-1 items-center gap-1">
                    <input
                      autoFocus
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={onDraftKey}
                      className="min-w-0 flex-1 rounded border border-brand bg-white px-1.5 py-0.5 text-sm outline-none"
                    />
                    <button onClick={commitEdit} className="rounded p-0.5 text-brand hover:bg-hover" title="保存">
                      <Check className="h-3.5 w-3.5" strokeWidth={2} />
                    </button>
                    <button onClick={() => setEditingId(null)} className="rounded p-0.5 text-muted hover:bg-hover" title="取消">
                      <X className="h-3.5 w-3.5" strokeWidth={2} />
                    </button>
                  </div>
                ) : (
                  <>
                    <button onClick={() => onSelect(s.id)} className="min-w-0 flex-1 truncate text-left">
                      {s.title || '新对话'}
                    </button>
                    <div className="flex shrink-0 items-center opacity-0 transition group-hover:opacity-100">
                      <button
                        onClick={() => startEdit(s.id, s.title || '')}
                        className="rounded p-1 text-muted hover:text-brand"
                        title="重命名"
                      >
                        <Pencil className="h-3.5 w-3.5" strokeWidth={1.75} />
                      </button>
                      <button
                        onClick={() => onDelete(s.id)}
                        className="rounded p-1 text-muted hover:text-red-500"
                        title="删除"
                      >
                        <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>

      <SystemPanel stats={stats} />
    </aside>
  )
}

function SystemPanel({ stats }: { stats: SystemStats | null }) {
  return (
    <div className="mt-2 shrink-0 rounded-xl border border-line bg-white/60 px-3 py-2.5 text-xs text-muted">
      <div className="mb-1.5 text-[11px] font-semibold tracking-wide text-foreground/60">系统信息</div>
      {!stats ? (
        <div>加载中…</div>
      ) : (
        <div className="space-y-1">
          <InfoRow
            icon="📚"
            label="资料片段"
            value={stats.n_chunks === 0 ? '0（先点上方导入）' : String(stats.n_chunks)}
          />
          <InfoRow icon="🤖" label="LLM" value={stats.llm_model} />
          <InfoRow icon="🔢" label="Embed" value={`${stats.embed_model} · ${stats.embed_dim}d`} />
          <InfoRow icon="🔎" label="检索" value={`top_k=${stats.top_k} · dense+FTS`} />
          <InfoRow icon="🗄️" label="库" value={stats.collection} />
        </div>
      )}
    </div>
  )
}

function InfoRow({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="shrink-0">{icon}</span>
      <span className="shrink-0 text-foreground/60">{label}</span>
      <span className="ml-auto truncate" title={value}>
        {value}
      </span>
    </div>
  )
}
