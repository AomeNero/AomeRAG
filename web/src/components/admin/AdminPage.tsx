import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Database,
  FileText,
  MessageSquare,
  RefreshCw,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  Upload,
  Wand2,
} from 'lucide-react'
import {
  deleteFeedback,
  deleteSession,
  getAdminMessages,
  getAllFeedback,
  getAllSessions,
  getFiles,
  getStats,
  resetStore,
  streamCleanDir,
  streamIngestDir,
  type AdminSession,
  type FeedbackItem,
  type FileInfo,
  type HistoryMessage,
  type IngestEvent,
  type SystemStats,
} from '../../lib/api'
import { cn } from '../../lib/utils'

// ─── Tab definitions ──────────────────────────────────────────────

type Tab = 'sessions' | 'feedback' | 'system'

const TABS: { key: Tab; label: string }[] = [
  { key: 'sessions', label: '会话管理' },
  { key: 'feedback', label: '反馈管理' },
  { key: 'system', label: '系统运维' },
]

// ─── Main page ────────────────────────────────────────────────────

export function AdminPage() {
  const [tab, setTab] = useState<Tab>('sessions')

  return (
    <div className="min-h-screen bg-gray-50 p-6 text-gray-900">
      <div className="mx-auto max-w-5xl">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold">AomeRAG 管理后台</h1>
          <Link to="/" className="text-sm text-blue-600 hover:underline">
            ← 返回聊天
          </Link>
        </div>

        {/* Tabs */}
        <div className="mb-6 flex gap-1 rounded-lg bg-gray-200 p-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                'flex-1 rounded-md px-4 py-2 text-sm font-medium transition',
                tab === t.key
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700',
              )}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {tab === 'sessions' && <SessionsTab />}
        {tab === 'feedback' && <FeedbackTab />}
        {tab === 'system' && <SystemTab />}
      </div>
    </div>
  )
}

// ─── Sessions Tab ─────────────────────────────────────────────────

function SessionsTab() {
  const [sessions, setSessions] = useState<AdminSession[]>([])
  const [userFilter, setUserFilter] = useState<string>('')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [messages, setMessages] = useState<HistoryMessage[]>([])
  const [loadingMsg, setLoadingMsg] = useState(false)

  const load = async () => {
    try {
      setSessions(await getAllSessions())
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const users = [...new Set(sessions.map((s) => s.user_id))].sort()

  const filtered = userFilter
    ? sessions.filter((s) => s.user_id === userFilter)
    : sessions

  const toggleExpand = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null)
      setMessages([])
      return
    }
    setExpandedId(id)
    setMessages([])
    setLoadingMsg(true)
    try {
      setMessages(await getAdminMessages(id))
    } catch {
      setMessages([])
    }
    setLoadingMsg(false)
  }

  const del = async (id: string) => {
    try {
      await deleteSession(id)
      if (expandedId === id) {
        setExpandedId(null)
        setMessages([])
      }
      void load()
    } catch {
      /* ignore */
    }
  }

  return (
    <div>
      {/* Toolbar */}
      <div className="mb-4 flex items-center gap-3">
        <select
          value={userFilter}
          onChange={(e) => setUserFilter(e.target.value)}
          className="h-8 rounded border border-gray-300 bg-white px-2 text-sm"
        >
          <option value="">全部用户 ({sessions.length})</option>
          {users.map((u) => (
            <option key={u} value={u}>
              {u} ({sessions.filter((s) => s.user_id === u).length})
            </option>
          ))}
        </select>
        <button
          onClick={load}
          className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:brightness-95"
        >
          刷新
        </button>
        <span className="text-sm text-gray-400">
          共 {filtered.length} 条会话
        </span>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="px-4 py-2 w-8" />
              <th className="px-4 py-2">标题</th>
              <th className="px-4 py-2 w-40">用户</th>
              <th className="px-4 py-2 w-40">更新时间</th>
              <th className="px-4 py-2 w-16">操作</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s) => (
              <SessionRow
                key={s.id}
                s={s}
                expanded={expandedId === s.id}
                messages={messages}
                loadingMsg={loadingMsg}
                onToggle={() => toggleExpand(s.id)}
                onDelete={() => del(s.id)}
              />
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
                  暂无会话记录
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SessionRow({
  s,
  expanded,
  messages,
  loadingMsg,
  onToggle,
  onDelete,
}: {
  s: AdminSession
  expanded: boolean
  messages: HistoryMessage[]
  loadingMsg: boolean
  onToggle: () => void
  onDelete: () => void
}) {
  const time = new Date(s.updated_at * 1000).toLocaleString('zh-CN')

  return (
    <>
      <tr className="border-b transition hover:bg-gray-50">
        <td className="px-4 py-2">
          <button onClick={onToggle} className="text-gray-400 hover:text-gray-600">
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </td>
        <td className="px-4 py-2 truncate max-w-xs">{s.title || '(无标题)'}</td>
        <td className="px-4 py-2 text-gray-500 font-mono text-xs">{s.user_id}</td>
        <td className="px-4 py-2 text-gray-400">{time}</td>
        <td className="px-4 py-2">
          <button
            onClick={onDelete}
            className="text-red-500 hover:underline text-xs"
          >
            删除
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={5} className="bg-gray-50 px-8 py-4">
            {loadingMsg ? (
              <p className="text-sm text-gray-400">加载消息中…</p>
            ) : messages.length === 0 ? (
              <p className="text-sm text-gray-400">无消息记录</p>
            ) : (
              <div className="max-h-80 space-y-3 overflow-y-auto">
                {messages.map((m, i) => (
                  <div key={i} className="flex gap-3">
                    <span
                      className={cn(
                        'mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-xs font-medium',
                        m.role === 'user'
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-gray-200 text-gray-600',
                      )}
                    >
                      {m.role === 'user' ? '用户' : 'AI'}
                    </span>
                    <p className="whitespace-pre-wrap text-sm leading-6 text-gray-700">
                      {m.text}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  )
}

// ─── Feedback Tab ─────────────────────────────────────────────────

function FeedbackTab() {
  const [items, setItems] = useState<FeedbackItem[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const load = async () => {
    setLoading(true)
    try {
      setItems(await getAllFeedback())
    } catch {
      setItems([])
    }
    setLoading(false)
  }

  useEffect(() => {
    void load()
  }, [])

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const del = async (id: string) => {
    try {
      await deleteFeedback(id)
      setItems((prev) => prev.filter((f) => f.id !== id))
    } catch {
      /* ignore */
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <button
          onClick={load}
          className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:brightness-95"
        >
          刷新
        </button>
        {loading && <span className="text-sm text-gray-400">加载中…</span>}
        <span className="text-sm text-gray-400">共 {items.length} 条反馈</span>
      </div>

      {items.length === 0 && !loading && (
        <p className="text-gray-400">暂无反馈记录</p>
      )}

      <div className="space-y-3">
        {items.map((f) => {
          const isExpanded = expanded.has(f.id)
          return (
            <div
              key={f.id}
              className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
            >
              <div className="mb-2 flex items-center gap-2 text-sm">
                {f.type === 'rating' && f.rating === 'up' && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-green-700">
                    <ThumbsUp className="h-3 w-3" /> 赞
                  </span>
                )}
                {f.type === 'rating' && f.rating === 'down' && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-red-700">
                    <ThumbsDown className="h-3 w-3" /> 踩
                  </span>
                )}
                {f.type === 'missing' && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-amber-700">
                    <MessageSquare className="h-3 w-3" /> 知识库缺失
                  </span>
                )}
                <span className="text-gray-400">
                  {new Date(f.created_at * 1000).toLocaleString('zh-CN')}
                </span>
                <span className="text-gray-400">用户: {f.user_id}</span>
                <button
                  onClick={() => del(f.id)}
                  className="ml-auto flex items-center gap-1 rounded px-2 py-0.5 text-red-500 transition hover:bg-red-50"
                  title="删除"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>

              {f.user_question && (
                <div className="mb-1 text-sm">
                  <span className="text-gray-400">问: </span>
                  <span className="text-gray-700">
                    {isExpanded ? f.user_question : f.user_question.slice(0, 200)}
                    {!isExpanded && f.user_question.length > 200 && '…'}
                  </span>
                </div>
              )}
              {f.ai_answer && (
                <div className="mb-1 text-sm">
                  <span className="text-gray-400">答: </span>
                  <span className="whitespace-pre-wrap text-gray-600">
                    {isExpanded ? f.ai_answer : f.ai_answer.slice(0, 300)}
                    {!isExpanded && f.ai_answer.length > 300 && '…'}
                  </span>
                </div>
              )}
              {f.comment && (
                <div className="mt-1 rounded bg-gray-50 px-3 py-1.5 text-sm text-gray-700">
                  💬 {f.comment}
                </div>
              )}

              <button
                onClick={() => toggle(f.id)}
                className="mt-2 flex items-center gap-1 text-xs text-blue-600 hover:underline"
              >
                {isExpanded ? (
                  <>
                    <ChevronUp className="h-3 w-3" /> 收起
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-3 w-3" /> 查看详情
                  </>
                )}
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── System Tab ───────────────────────────────────────────────────

function SystemTab() {
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [readyz, setReadyz] = useState<Record<string, string> | null>(null)
  const [cleanEvents, setCleanEvents] = useState<IngestEvent[]>([])
  const [ingestEvents, setIngestEvents] = useState<IngestEvent[]>([])
  const [busy, setBusy] = useState<'clean' | 'ingest' | null>(null)
  const [files, setFiles] = useState<FileInfo[]>([])
  const [fileType, setFileType] = useState<'raw-data' | 'md-data'>('raw-data')
  const [resetConfirm, setResetConfirm] = useState(false)

  const refresh = async () => {
    try {
      setStats(await getStats())
      const r = await fetch('/readyz')
      if (r.ok) setReadyz(await r.json())
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const runClean = async () => {
    setBusy('clean')
    setCleanEvents([])
    try {
      for await (const ev of streamCleanDir()) setCleanEvents((p) => [...p, ev])
    } catch {
      /* ignore */
    }
    setBusy(null)
    void refresh()
  }

  const runIngest = async () => {
    setBusy('ingest')
    setIngestEvents([])
    try {
      for await (const ev of streamIngestDir()) setIngestEvents((p) => [...p, ev])
    } catch {
      /* ignore */
    }
    setBusy(null)
    void refresh()
  }

  const loadFiles = async (t: 'raw-data' | 'md-data') => {
    setFileType(t)
    try {
      const r = await getFiles(t)
      setFiles(r.files)
    } catch {
      setFiles([])
    }
  }

  const doReset = async () => {
    setResetConfirm(false)
    try {
      await resetStore()
      void refresh()
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="space-y-4">
      {/* 数据管线 */}
      <Card title="数据管线" icon={<Database className="h-5 w-5" />}>
        <div className="flex gap-3">
          <ActionBtn
            onClick={runClean}
            disabled={busy !== null}
            icon={<Wand2 className="h-4 w-4" />}
            label={busy === 'clean' ? '清洗中…' : '清洗 (raw-data → md-data)'}
          />
          <ActionBtn
            onClick={runIngest}
            disabled={busy !== null}
            icon={<Upload className="h-4 w-4" />}
            label={busy === 'ingest' ? '切片中…' : '切片入库 (md-data → 索引)'}
          />
        </div>
        {cleanEvents.length > 0 && <EventLog title="清洗进度" events={cleanEvents} />}
        {ingestEvents.length > 0 && <EventLog title="切片进度" events={ingestEvents} />}
      </Card>

      {/* 系统信息 */}
      <Card title="系统信息" icon={<RefreshCw className="h-5 w-5" />}>
        <button
          onClick={refresh}
          className="mb-3 rounded bg-blue-600 px-3 py-1 text-sm text-white hover:brightness-95"
        >
          刷新
        </button>
        {stats && (
          <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
            <Stat label="资料片段" value={String(stats.n_chunks)} />
            <Stat label="LLM" value={stats.llm_model} />
            <Stat label="Embed" value={`${stats.embed_model} · ${stats.embed_dim}d`} />
            <Stat label="检索" value={`top_k=${stats.top_k}`} />
            <Stat label="Collection" value={stats.collection} />
          </div>
        )}
        {readyz && (
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            {Object.entries(readyz).map(([k, v]) => (
              <span
                key={k}
                className={`rounded-full px-2 py-0.5 ${
                  v === 'ok' || v === 'present'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-red-100 text-red-700'
                }`}
              >
                {k}: {v}
              </span>
            ))}
          </div>
        )}
      </Card>

      {/* 文件浏览 */}
      <Card title="文件浏览" icon={<FileText className="h-5 w-5" />}>
        <div className="mb-3 flex gap-2">
          <button
            onClick={() => loadFiles('raw-data')}
            className={`rounded px-3 py-1 text-sm ${
              fileType === 'raw-data' ? 'bg-blue-600 text-white' : 'bg-gray-200'
            }`}
          >
            raw-data
          </button>
          <button
            onClick={() => loadFiles('md-data')}
            className={`rounded px-3 py-1 text-sm ${
              fileType === 'md-data' ? 'bg-blue-600 text-white' : 'bg-gray-200'
            }`}
          >
            md-data
          </button>
        </div>
        {files.length > 0 ? (
          <ul className="max-h-48 divide-y divide-gray-100 overflow-y-auto text-sm">
            {files.map((f) => (
              <li key={f.name} className="flex justify-between py-1">
                <span className="truncate">{f.name}</span>
                <span className="shrink-0 text-gray-400">{(f.size / 1024).toFixed(1)} KB</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-gray-400">点击上方按钮加载文件列表</p>
        )}
      </Card>

      {/* 向量库 */}
      <Card title="向量库" icon={<Database className="h-5 w-5" />}>
        {!resetConfirm ? (
          <button
            onClick={() => setResetConfirm(true)}
            className="flex items-center gap-2 rounded bg-red-600 px-4 py-2 text-sm text-white hover:brightness-95"
          >
            <Trash2 className="h-4 w-4" />
            清空向量库
          </button>
        ) : (
          <div className="flex items-center gap-3 rounded-lg border border-red-300 bg-red-50 p-3">
            <AlertTriangle className="h-5 w-5 text-red-600" />
            <span className="text-sm text-red-700">确认清空所有向量？不可恢复！</span>
            <button
              onClick={doReset}
              className="rounded bg-red-600 px-3 py-1 text-sm text-white"
            >
              确认清空
            </button>
            <button
              onClick={() => setResetConfirm(false)}
              className="rounded bg-gray-300 px-3 py-1 text-sm"
            >
              取消
            </button>
          </div>
        )}
      </Card>
    </div>
  )
}

// ─── Shared components ────────────────────────────────────────────

function Card({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="mb-3 flex items-center gap-2 font-semibold">
        {icon}
        {title}
      </h2>
      {children}
    </div>
  )
}

function ActionBtn({
  onClick,
  disabled,
  icon,
  label,
}: {
  onClick: () => void
  disabled: boolean
  icon: React.ReactNode
  label: string
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:brightness-95 disabled:opacity-50"
    >
      {icon}
      {label}
    </button>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-gray-50 px-3 py-2">
      <div className="text-xs text-gray-400">{label}</div>
      <div className="truncate font-medium">{value}</div>
    </div>
  )
}

function EventLog({ title, events }: { title: string; events: IngestEvent[] }) {
  return (
    <div className="mt-3 rounded-lg bg-gray-900 p-3 text-xs text-gray-300">
      <div className="mb-1 font-medium text-gray-400">{title}</div>
      <div className="max-h-40 space-y-0.5 overflow-y-auto">
        {events.map((ev, i) => (
          <div key={i}>
            {ev.type === 'scan' && `📂 扫描 ${ev.n_files} 个文件`}
            {ev.type === 'file_done' &&
              `${ev.status === 'ok' ? '✓' : '✗'} ${ev.source_doc}${ev.n_chunks ? ` (${ev.n_chunks} 切片)` : ''}`}
            {ev.type === 'skipped' && `⊘ ${ev.source_doc}`}
            {ev.type === 'summary' &&
              `📊 完成: ${ev.n_docs} 文档 / ${ev.n_chunks} 切片 / ${ev.elapsed_s}s`}
          </div>
        ))}
      </div>
    </div>
  )
}
