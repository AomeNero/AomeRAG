import { PanelLeft, Plus, Search, Trash2, Upload } from 'lucide-react'
import type { Session } from '../../lib/api'
import { cn } from '../../lib/utils'

interface Props {
  sessions: Session[]
  currentId: string | null
  onSelect: (id: string) => void
  onNewChat: () => void
  onIngest: () => void
  onDelete: (id: string) => void
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

export function Sidebar({ sessions, currentId, onSelect, onNewChat, onIngest, onDelete }: Props) {
  const groups = groupSessions(sessions)
  return (
    <aside className="flex h-full w-[261px] shrink-0 flex-col bg-field px-3 pb-2.5 pt-1.5">
      <div className="flex h-12 items-center justify-between pb-2.5 pl-1 pt-[15px]">
        <span className="pl-1 text-base font-semibold text-foreground">AomeRAG</span>
        <div className="flex items-center gap-[18px] text-muted">
          <button className="rounded-full p-1 transition hover:bg-hover" title="搜索">
            <Search className="h-4 w-4" strokeWidth={1.75} />
          </button>
          <button className="rounded-full p-1 transition hover:bg-hover" title="折叠侧边栏">
            <PanelLeft className="h-4 w-4" strokeWidth={1.75} />
          </button>
        </div>
      </div>

      <button
        onClick={onNewChat}
        className="flex h-10 items-center justify-center gap-2 rounded-full bg-white px-4 text-sm font-medium text-foreground transition hover:shadow-sm"
      >
        <Plus className="h-4 w-4" strokeWidth={2} />
        <span>开启新对话</span>
      </button>
      <button
        onClick={onIngest}
        className="mt-2 flex h-10 w-full items-center justify-center gap-2 rounded-full border border-line px-4 text-sm font-medium text-foreground transition hover:bg-hover"
        title="切片并导入 raw 目录的知识库文档"
      >
        <Upload className="h-4 w-4" strokeWidth={1.75} />
        <span>导入知识库</span>
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
                <button onClick={() => onSelect(s.id)} className="flex-1 truncate text-left">
                  {s.title || '新对话'}
                </button>
                <button
                  onClick={() => onDelete(s.id)}
                  className="shrink-0 rounded p-1 text-muted opacity-0 transition hover:text-red-500 group-hover:opacity-100"
                  title="删除"
                >
                  <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
                </button>
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className="flex h-11 items-center gap-2 rounded-xl px-2 text-sm text-muted">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand text-xs font-medium text-white">
          我
        </span>
        <span>本地用户</span>
      </div>
    </aside>
  )
}
