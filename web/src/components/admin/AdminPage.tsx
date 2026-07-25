import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Database, FileText, RefreshCw, Trash2, Upload, Wand2 } from 'lucide-react'
import {
  deleteSession,
  getAllSessions,
  getFiles,
  getStats,
  resetStore,
  streamCleanDir,
  streamIngestDir,
  type AdminSession,
  type FileInfo,
  type IngestEvent,
  type SystemStats,
} from '../../lib/api'

const ADMIN_USER_KEY = 'aome_admin_user'

export function AdminPage() {
  const [user, setUser] = useState(() => localStorage.getItem(ADMIN_USER_KEY) || 'admin')
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [readyz, setReadyz] = useState<Record<string, string> | null>(null)
  const [cleanEvents, setCleanEvents] = useState<IngestEvent[]>([])
  const [ingestEvents, setIngestEvents] = useState<IngestEvent[]>([])
  const [busy, setBusy] = useState<'clean' | 'ingest' | null>(null)
  const [files, setFiles] = useState<FileInfo[]>([])
  const [fileType, setFileType] = useState<'raw-data' | 'md-data'>('raw-data')
  const [sessions, setSessions] = useState<AdminSession[]>([])
  const [resetConfirm, setResetConfirm] = useState(false)

  // Set admin user-id for API calls
  useEffect(() => {
    localStorage.setItem('aome_user_id', user)
    localStorage.setItem(ADMIN_USER_KEY, user)
  }, [user])

  const refresh = async () => {
    try {
      setStats(await getStats())
      const r = await fetch('/readyz', { headers: { 'X-User-Id': user } })
      if (r.ok) setReadyz(await r.json())
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    void refresh()
  }, [user])

  const runClean = async () => {
    setBusy('clean')
    setCleanEvents([])
    try {
      for await (const ev of streamCleanDir()) setCleanEvents((p) => [...p, ev])
    } catch {
      // ignore
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
      // ignore
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

  const loadSessions = async () => {
    try {
      setSessions(await getAllSessions())
    } catch {
      // ignore
    }
  }

  const doReset = async () => {
    setResetConfirm(false)
    try {
      await resetStore()
      void refresh()
    } catch {
      // ignore
    }
  }

  const delSession = async (id: string) => {
    try {
      await deleteSession(id)
      void loadSessions()
    } catch {
      // ignore
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6 text-gray-900">
      {/* Header */}
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold">AomeRAG 管理后台</h1>
          <div className="flex items-center gap-3">
            <input
              value={user}
              onChange={(e) => setUser(e.target.value)}
              className="h-8 w-32 rounded border border-gray-300 px-2 text-sm"
              placeholder="user-id"
            />
            <Link to="/" className="text-sm text-blue-600 hover:underline">
              ← 返回聊天
            </Link>
          </div>
        </div>

        {/* ① 数据管线 */}
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
          {cleanEvents.length > 0 && (
            <EventLog title="清洗进度" events={cleanEvents} />
          )}
          {ingestEvents.length > 0 && (
            <EventLog title="切片进度" events={ingestEvents} />
          )}
        </Card>

        {/* ② 系统信息 */}
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
                  className={`rounded-full px-2 py-0.5 ${v === 'ok' || v === 'present' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}
                >
                  {k}: {v}
                </span>
              ))}
            </div>
          )}
        </Card>

        {/* ③ 文件浏览 */}
        <Card title="文件浏览" icon={<FileText className="h-5 w-5" />}>
          <div className="mb-3 flex gap-2">
            <button
              onClick={() => loadFiles('raw-data')}
              className={`rounded px-3 py-1 text-sm ${fileType === 'raw-data' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
            >
              raw-data
            </button>
            <button
              onClick={() => loadFiles('md-data')}
              className={`rounded px-3 py-1 text-sm ${fileType === 'md-data' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
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

        {/* ④ 向量库 */}
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
              <button onClick={doReset} className="rounded bg-red-600 px-3 py-1 text-sm text-white">
                确认清空
              </button>
              <button onClick={() => setResetConfirm(false)} className="rounded bg-gray-300 px-3 py-1 text-sm">
                取消
              </button>
            </div>
          )}
        </Card>

        {/* ⑤ 会话管理 */}
        <Card title="会话管理（跨用户）" icon={<FileText className="h-5 w-5" />}>
          <button
            onClick={loadSessions}
            className="mb-3 rounded bg-blue-600 px-3 py-1 text-sm text-white hover:brightness-95"
          >
            加载全部会话
          </button>
          {sessions.length > 0 && (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="py-1">标题</th>
                  <th className="py-1">用户</th>
                  <th className="py-1">操作</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.id} className="border-b">
                    <td className="py-1 truncate">{s.title || '(无标题)'}</td>
                    <td className="py-1 text-gray-500">{s.user_id}</td>
                    <td className="py-1">
                      <button
                        onClick={() => delSession(s.id)}
                        className="text-red-500 hover:underline"
                      >
                        删除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  )
}

function Card({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="mb-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
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
            {ev.type === 'file_done' && `${ev.status === 'ok' ? '✓' : '✗'} ${ev.source_doc}${ev.n_chunks ? ` (${ev.n_chunks} 切片)` : ''}`}
            {ev.type === 'skipped' && `⊘ ${ev.source_doc}`}
            {ev.type === 'summary' && `📊 完成: ${ev.n_docs} 文档 / ${ev.n_chunks} 切片 / ${ev.elapsed_s}s`}
          </div>
        ))}
      </div>
    </div>
  )
}
