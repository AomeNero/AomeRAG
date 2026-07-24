import { useEffect, useState } from 'react'
import { AlertTriangle, Check, Loader2, X } from 'lucide-react'
import { streamIngestDir, type IngestEvent } from '../../lib/api'

interface Props {
  onClose: () => void
  onDone: () => void
}

export function IngestModal({ onClose, onDone }: Props) {
  const [events, setEvents] = useState<IngestEvent[]>([])
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        for await (const ev of streamIngestDir()) {
          if (cancelled) break
          setEvents((prev) => [...prev, ev])
          if (ev.type === 'summary') {
            setDone(true)
            onDone()
          }
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [onDone])

  const summary = events.find((e) => e.type === 'summary')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="flex max-h-[80vh] w-full max-w-lg flex-col rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <h2 className="text-base font-semibold text-foreground">导入知识库</h2>
          <button
            onClick={onClose}
            className="rounded-full p-1 text-muted transition hover:bg-hover"
            title="关闭"
          >
            <X className="h-4 w-4" strokeWidth={1.75} />
          </button>
        </div>

        <div className="scrollbar-none flex-1 overflow-y-auto px-5 py-3 text-sm">
          {error && (
            <div className="mb-2 flex items-center gap-2 text-red-600">
              <AlertTriangle className="h-4 w-4" /> {error}
            </div>
          )}
          {events.map((ev, i) => (
            <EventRow key={i} ev={ev} />
          ))}
          {!done && !error && (
            <div className="flex items-center gap-2 py-1 text-muted">
              <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} /> 正在处理…
            </div>
          )}
        </div>

        {summary && summary.type === 'summary' && (
          <div className="border-t border-line px-5 py-3 text-sm text-muted">
            完成：{summary.n_docs} 文档 / {summary.n_chunks} 切片
            {summary.n_failed > 0 ? ` / ${summary.n_failed} 失败` : ''} · 用时{' '}
            {summary.elapsed_s.toFixed(1)}s
          </div>
        )}

        <div className="flex justify-end border-t border-line px-5 py-3">
          <button
            onClick={onClose}
            disabled={!done && !error}
            className="rounded-full bg-brand px-5 py-2 text-sm font-medium text-white transition hover:brightness-95 disabled:opacity-50"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  )
}

function EventRow({ ev }: { ev: IngestEvent }) {
  if (ev.type === 'scan') {
    return (
      <div className="py-1 text-muted">
        扫描 {ev.raw_dir}：发现 {ev.n_files} 个文档{ev.n_skipped > 0 ? `，跳过 ${ev.n_skipped} 个` : ''}
      </div>
    )
  }
  if (ev.type === 'skipped') {
    return (
      <div className="flex items-center gap-2 py-0.5 text-muted">
        <span>⊘</span>
        <span className="truncate">{ev.source_doc}</span>
        <span className="shrink-0 text-xs">（{ev.reason}）</span>
      </div>
    )
  }
  if (ev.type === 'file_done') {
    return (
      <div className="flex items-center gap-2 py-0.5">
        {ev.status === 'ok' ? (
          <Check className="h-4 w-4 shrink-0 text-brand" strokeWidth={2} />
        ) : (
          <AlertTriangle className="h-4 w-4 shrink-0 text-red-500" strokeWidth={2} />
        )}
        <span className="truncate">{ev.source_doc}</span>
        <span className="shrink-0 text-xs text-muted">
          {ev.status === 'ok' ? `${ev.n_chunks} 切片` : ev.error ?? '失败'}
        </span>
      </div>
    )
  }
  // file_start — keep quiet (the file_done right after carries the result)
  return null
}
