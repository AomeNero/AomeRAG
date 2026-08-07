import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Check, Copy, Download, Loader2, RefreshCw, ThumbsDown, ThumbsUp } from 'lucide-react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/atom-one-dark.css'
import hlPython from 'highlight.js/lib/languages/python'
import hlJavascript from 'highlight.js/lib/languages/javascript'
import hlCpp from 'highlight.js/lib/languages/cpp'
import hlC from 'highlight.js/lib/languages/c'
import hlCsharp from 'highlight.js/lib/languages/csharp'
import hlLua from 'highlight.js/lib/languages/lua'
import hlBash from 'highlight.js/lib/languages/bash'
import hlJson from 'highlight.js/lib/languages/json'
import hlXml from 'highlight.js/lib/languages/xml'
import hlCss from 'highlight.js/lib/languages/css'
import hlMarkdown from 'highlight.js/lib/languages/markdown'
import type { ChatMessage, ToolEvent } from '../../data/chat'
import type { RetrievalHit } from '../../lib/api'
import { submitFeedback } from '../../lib/api'
import { cn } from '../../lib/utils'

interface Props {
  messages: ChatMessage[]
  streamingId: string | null
  onRegenerate: () => void
  searchQuery: string | null
  sessionId?: string | null
}

export function MessageList({ messages, streamingId, onRegenerate, searchQuery, sessionId }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [highlightIdx, setHighlightIdx] = useState<number | null>(null)

  useEffect(() => {
    if (searchQuery) return
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, searchQuery])

  useEffect(() => {
    if (!searchQuery) {
      setHighlightIdx(null)
      return
    }
    const q = searchQuery.toLowerCase()
    const idx = messages.findIndex((m) => m.content.toLowerCase().includes(q))
    setHighlightIdx(idx >= 0 ? idx : null)
    if (idx >= 0) {
      const el = scrollRef.current?.querySelector(`[data-midx="${idx}"]`)
      el?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
  }, [messages, searchQuery])

  const lastAssistantId = [...messages].reverse().find((m) => m.role === 'assistant')?.id

  // 查找给定 assistant 消息前一条 user 消息（用于反馈时带上用户提问）
  const getUserQuestion = (idx: number): string => {
    for (let i = idx - 1; i >= 0; i--) {
      if (messages[i].role === 'user') return messages[i].content
    }
    return ''
  }

  return (
    <div ref={scrollRef} className="scrollbar-none flex-1 overflow-y-auto">
      <div className="mx-auto max-w-[774px] px-4 py-6">
        {messages.map((m, i) => (
          <Message
            key={m.id}
            m={m}
            index={i}
            highlight={highlightIdx === i}
            streaming={streamingId === m.id}
            isLast={m.id === lastAssistantId}
            onRegenerate={onRegenerate}
            userQuestion={getUserQuestion(i)}
            sessionId={sessionId}
          />
        ))}
      </div>
    </div>
  )
}

function Message({
  m,
  index,
  highlight,
  streaming,
  isLast,
  onRegenerate,
  userQuestion,
  sessionId,
}: {
  m: ChatMessage
  index: number
  highlight: boolean
  streaming: boolean
  isLast: boolean
  onRegenerate: () => void
  userQuestion: string
  sessionId?: string | null
}) {
  const [showDetails, setShowDetails] = useState(false)
  const [showDownDialog, setShowDownDialog] = useState(false)
  const [downComment, setDownComment] = useState('')
  const [showMissingDialog, setShowMissingDialog] = useState(false)
  const [missingText, setMissingText] = useState('')
  const [rated, setRated] = useState<'up' | 'down' | null>(m.feedback ?? null)
  const hits = m.toolEvents?.flatMap((t) => t.details ?? []) ?? []
  const ring = highlight ? 'ring-2 ring-brand rounded-lg' : ''

  // 判断"检索无结果"：tool_result 的 details === []（空数组 = 检索跑了但 0 命中）。
  // details 对非 kb_search 工具（bash/read/write/edit）可能为 null —— 用 Array.isArray 兜底防崩溃。
  const hadEmptySearch = m.toolEvents?.some(
    (t) => t.status === 'ok' && Array.isArray(t.details) && t.details.length === 0
  ) ?? false

  const rate = async (rating: 'up' | 'down', comment?: string) => {
    if (rated) return
    try {
      await submitFeedback({
        type: 'rating',
        session_id: sessionId ?? undefined,
        message_id: m.id,
        rating,
        user_question: userQuestion,
        ai_answer: m.content,
        comment: comment?.trim() || undefined,
      })
      setRated(rating) // 提交成功后即时变色
    } catch { /* ignore */ }
  }

  const onThumbsUp = () => { void rate('up') }
  const onThumbsDown = () => { setShowDownDialog(true) }
  const submitDown = async () => {
    await rate('down', downComment)  // 一次调用带上评论
    setShowDownDialog(false)
    setDownComment('')
  }

  const submitMissing = async () => {
    if (!missingText.trim()) return
    try {
      await submitFeedback({
        type: 'missing',
        session_id: sessionId ?? undefined,
        user_question: userQuestion,
        comment: missingText.trim(),
      })
    } catch { /* ignore */ }
    setShowMissingDialog(false)
    setMissingText('')
  }

  if (m.role === 'user') {
    return (
      <div data-midx={index} className={`mb-6 flex justify-end p-px ${ring}`}>
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl bg-[#e4edfd] px-4 py-2.5 text-[15px] leading-7 text-foreground">
          {m.content}
        </div>
      </div>
    )
  }

  // 空助手消息（无内容/无错误/非流式/非澄清/非最后一条带工具）不渲染，避免历史里堆空行
  const hasVisible =
    !!m.content.trim() ||
    !!m.error ||
    streaming ||
    !!m.isClarify ||
    (isLast && (m.toolEvents?.length ?? 0) > 0)
  if (!hasVisible) return null

  return (
    <div data-midx={index} className={`mb-6 p-px ${ring}`}>
      {m.isClarify && (
        <div className="mb-2 inline-flex items-center gap-1 rounded-full bg-brand-light px-2.5 py-1 text-xs font-medium text-brand">
          💬 需要补充信息
        </div>
      )}
      {/* 只给最后一条 assistant 消息显示工具状态条；流式进行中即使还没工具事件也显示"正在生成" */}
      {isLast && (streaming || (m.toolEvents?.length ?? 0) > 0) && (
        <StepPanel
          toolEvents={m.toolEvents ?? []}
          elapsed={m.turnElapsed}
          expanded={showDetails}
          streaming={streaming}
          onClick={() => setShowDetails((v) => !v)}
        />
      )}
      {showDetails && hits.length > 0 && <DetailsPanel hits={hits} />}
      <div className="text-[15px] leading-7 text-foreground">
        {m.content ? (
          <Markdown text={m.content} />
        ) : streaming && !m.error ? (
          <ThinkingDots />
        ) : null}
        {streaming && m.content && !m.error && <Cursor />}
      </div>
      {m.error && (
        <div className="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">
          {m.error}
        </div>
      )}

      {/* "no results" feedback button */}
      {hadEmptySearch && !streaming && !m.error && (
        <button
          onClick={() => setShowMissingDialog(true)}
          className="mt-2 rounded-lg border border-line bg-field px-3 py-1.5 text-xs text-brand transition hover:bg-hover"
        >
          📚 知识库没找到？点击补充信息
        </button>
      )}

      {/* 👎 dialog */}
      {showDownDialog && (
        <div className="mt-2 rounded-lg border border-line bg-field p-3">
          <textarea
            autoFocus
            value={downComment}
            onChange={(e) => setDownComment(e.target.value)}
            placeholder="哪里不好？（可选）"
            className="h-16 w-full resize-none rounded border border-line bg-white px-2 py-1 text-sm outline-none focus:border-brand"
          />
          <div className="mt-2 flex justify-end gap-2">
            <button onClick={() => { setShowDownDialog(false); setDownComment('') }} className="rounded px-3 py-1 text-sm text-muted hover:bg-hover">取消</button>
            <button onClick={submitDown} className="rounded bg-brand px-3 py-1 text-sm text-white">提交</button>
          </div>
        </div>
      )}

      {/* missing-info dialog */}
      {showMissingDialog && (
        <div className="mt-2 rounded-lg border border-line bg-field p-3">
          <p className="mb-2 text-sm text-foreground">你期望找到什么信息？我们会记录并改进知识库。</p>
          <textarea
            autoFocus
            value={missingText}
            onChange={(e) => setMissingText(e.target.value)}
            placeholder="描述你需要的知识库内容…"
            className="h-20 w-full resize-none rounded border border-line bg-white px-2 py-1 text-sm outline-none focus:border-brand"
          />
          <div className="mt-2 flex justify-end gap-2">
            <button onClick={() => { setShowMissingDialog(false); setMissingText('') }} className="rounded px-3 py-1 text-sm text-muted hover:bg-hover">取消</button>
            <button onClick={submitMissing} className="rounded bg-brand px-3 py-1 text-sm text-white">提交反馈</button>
          </div>
        </div>
      )}

      {/* action bar */}
      {!streaming && !m.error && m.content.trim() && (
        <div className="mt-2 flex items-center gap-1 text-muted">
          <CopyButton text={m.content} />
          <DownloadButton text={m.content} />
          {isLast && (
            <button
              onClick={onRegenerate}
              className="rounded-md p-1 transition hover:bg-hover"
              title="重新生成"
            >
              <RefreshCw className="h-4 w-4" strokeWidth={1.75} />
            </button>
          )}
          <button
            onClick={onThumbsUp}
            disabled={!!rated}
            className={cn('rounded-md p-1 transition hover:bg-hover', rated === 'up' && 'text-brand')}
            title="好的回答"
          >
            <ThumbsUp className="h-4 w-4" strokeWidth={1.75} />
          </button>
          <button
            onClick={onThumbsDown}
            disabled={!!rated}
            className={cn('rounded-md p-1 transition hover:bg-hover', rated === 'down' && 'text-red-500')}
            title="不好的回答"
          >
            <ThumbsDown className="h-4 w-4" strokeWidth={1.75} />
          </button>
        </div>
      )}
    </div>
  )
}

function ChevronIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`h-3 w-3 opacity-60 transition-transform ${expanded ? 'rotate-180' : ''}`}
    >
      <path
        d="M11.8486 5.5L11.4238 5.92383L8.69727 8.65137C8.44157 8.90706 8.21562 9.13382 8.01172 9.29785C7.79912 9.46883 7.55595 9.61756 7.25 9.66602C7.08435 9.69222 6.91565 9.69222 6.75 9.66602C6.44405 9.61756 6.20088 9.46883 5.98828 9.29785C5.78438 9.13382 5.55843 8.90706 5.30273 8.65137L2.57617 5.92383L2.15137 5.5L3 4.65137L3.42383 5.07617L6.15137 7.80273C6.42595 8.07732 6.59876 8.24849 6.74023 8.3623C6.87291 8.46904 6.92272 8.47813 6.9375 8.48047C6.97895 8.48703 7.02105 8.48703 7.0625 8.48047C7.07728 8.47813 7.12709 8.46904 7.25977 8.3623C7.40124 8.24849 7.57405 8.07732 7.84863 7.80273L10.5762 5.07617L11 4.65137L11.8486 5.5Z"
        fill="currentColor"
      />
    </svg>
  )
}

/** 工具活动名称映射：进行中状态显示具体动作，避免笼统的"正在检索"让用户以为卡死 */
/** 工具动作名（用于步骤列表），如 "读取文件" "生成文件" */
function toolAction(name: string): string {
  switch (name) {
    case 'kb_search': return '检索知识库'
    case 'read': return '读取文件'
    case 'write': return '生成文件'
    case 'edit': return '修改文件'
    case 'bash': return '执行命令'
    case 'load_skill': return '加载技能'
    default: return '处理'
  }
}

/** 取路径最后一段文件名（兼容 / 和 \），并去掉 `#段落` 后缀。如
 *  `@skill/products/references/电测产品履历表.md#GS321I` → `电测产品履历表.md` */
function fileNameOf(p: string): string {
  const noSection = p.split('#')[0]
  const parts = noSection.split(/[/\\]/)
  return parts[parts.length - 1] || p
}

/** 截断长文本（用于命令/查询词预览） */
function truncate(s: string, max = 24): string {
  return s.length > max ? s.slice(0, max) + '…' : s
}

/** 从工具参数里提取展示细节：文件名 / 技能名 / 命令 / 查询词 */
function toolDetail(t: ToolEvent): string | null {
  const args = t.arguments
  if (!args) return null
  switch (t.name) {
    case 'read':
    case 'write':
    case 'edit':
      return typeof args.path === 'string' ? fileNameOf(args.path) : null
    case 'load_skill':
      return typeof args.skill_name === 'string' ? truncate(args.skill_name) : null
    case 'kb_search':
      return typeof args.query === 'string' ? truncate(args.query) : null
    case 'bash':
      return typeof args.command === 'string' ? truncate(args.command) : null
    default:
      return null
  }
}

/** 折叠式执行步骤面板：进行中自动展开显示每步，完成折叠成一行摘要，点击展开明细 */
function StepPanel({
  toolEvents,
  elapsed,
  expanded,
  streaming,
  onClick,
}: {
  toolEvents: ToolEvent[]
  elapsed?: number
  expanded: boolean
  streaming: boolean
  onClick: () => void
}) {
  const [now, setNow] = useState(() => Date.now())
  const [showAllSteps, setShowAllSteps] = useState(false)
  const startedAt = useRef<number | null>(null)
  useEffect(() => {
    if (streaming) {
      if (startedAt.current === null) startedAt.current = Date.now()
      const id = setInterval(() => setNow(Date.now()), 500)
      return () => clearInterval(id)
    }
    startedAt.current = null
  }, [streaming])

  const runningTool = [...toolEvents].reverse().find((t) => t.status === 'running')
  const searches = toolEvents.filter((t) => t.name === 'kb_search')
  const anyError = toolEvents.some((t) => t.status === 'error')
  const hits = toolEvents.flatMap((t) => (Array.isArray(t.details) ? t.details : []))
  // 刷新后 details 缺失，用 content 里的 "[N]" 计数兜底
  const contentCount = toolEvents.reduce(
    (s, t) => s + ((t.content?.match(/^\[\d+\]/gm) ?? []).length),
    0,
  )
  const n = hits.length > 0 ? hits.length : contentCount
  const showSteps = streaming || expanded // 进行中始终展开

  let summaryLabel: string
  let summaryIcon: ReactNode
  let summaryTone = 'text-muted'
  if (streaming) {
    // 整个生成过程都显示明确的"进行中"状态（转圈 + 秒数跳动），避免用户以为卡死
    summaryLabel = runningTool ? `${toolAction(runningTool.name)}…` : '正在生成…'
    summaryIcon = <Loader2 className="h-3.5 w-3.5 animate-spin text-brand" strokeWidth={2} />
    summaryTone = 'text-brand'
  } else if (anyError) {
    summaryLabel = '处理出错'
    summaryIcon = <span className="text-red-500">⚠</span>
    summaryTone = 'text-red-600'
  } else if (searches.length > 0) {
    summaryLabel = n > 0 ? `知识库检索 · ${n} 条` : '知识库检索完成（0 条）'
    summaryIcon = <Check className="h-3.5 w-3.5 text-brand" strokeWidth={2} />
    summaryTone = 'text-foreground'
  } else {
    summaryLabel = `已使用 ${toolEvents.length} 个工具`
    summaryIcon = <Check className="h-3.5 w-3.5 text-brand" strokeWidth={2} />
    summaryTone = 'text-foreground'
  }
  // 进行中实时跳动用时，结束后用最终 turnElapsed
  const shownElapsed = streaming && startedAt.current != null ? (now - startedAt.current) / 1000 : elapsed
  if (shownElapsed != null) summaryLabel += ` · 用时 ${shownElapsed.toFixed(1)} 秒`

  return (
    <div
      className={`mb-2 overflow-hidden rounded-lg border border-line bg-field/60 ${
        showSteps ? '' : 'cursor-pointer transition hover:bg-hover'
      }`}
    >
      <button
        onClick={onClick}
        className={`flex w-full items-center gap-1.5 px-2.5 py-1.5 text-left text-xs ${summaryTone}`}
        title="点击展开/收起执行过程"
      >
        {summaryIcon}
        <span>{summaryLabel}</span>
        {toolEvents.length > 0 && (
          <span className="ml-auto">
            <ChevronIcon expanded={showSteps} />
          </span>
        )}
      </button>
      {showSteps && toolEvents.length > 0 && (
        <div className="border-t border-line px-2.5 py-1.5">
          {/* 默认只显示最近 3 个步骤，更早的收进"显示全部" */}
          {toolEvents.slice(showAllSteps ? 0 : -3).map((t) => (
            <StepRow key={t.id} t={t} />
          ))}
          {!showAllSteps && toolEvents.length > 3 && (
            <button
              onClick={() => setShowAllSteps(true)}
              className="mt-1 w-full rounded px-1 py-0.5 text-left text-xs text-brand transition hover:bg-hover"
            >
              + 显示全部 {toolEvents.length} 个步骤
            </button>
          )}
          {showAllSteps && toolEvents.length > 3 && (
            <button
              onClick={() => setShowAllSteps(false)}
              className="mt-1 w-full rounded px-1 py-0.5 text-left text-xs text-muted transition hover:bg-hover"
            >
              − 收起
            </button>
          )}
        </div>
      )}
    </div>
  )
}

/** 单个工具步骤行：状态图标 + 动作名 + 本步用时 */
function StepRow({ t }: { t: ToolEvent }) {
  let icon: ReactNode
  let tone = 'text-muted'
  switch (t.status) {
    case 'running':
      icon = <Loader2 className="h-3.5 w-3.5 animate-spin text-brand" strokeWidth={2} />
      tone = 'text-brand'
      break
    case 'ok':
      icon = <Check className="h-3.5 w-3.5 text-brand" strokeWidth={2} />
      tone = 'text-foreground'
      break
    case 'error':
      icon = <span className="text-red-500">⚠</span>
      tone = 'text-red-600'
      break
    case 'cancelled':
      icon = <span className="text-muted">⊘</span>
      tone = 'text-muted'
      break
  }
  const detail = toolDetail(t)
  return (
    <div className="flex items-center gap-1.5 py-0.5 text-xs">
      {icon}
      <span className={`truncate ${tone}`}>
        {toolAction(t.name)}
        {detail ? `: ${detail}` : ''}
      </span>
      {t.elapsed != null && <span className="ml-auto shrink-0 text-muted">{t.elapsed.toFixed(1)} 秒</span>}
    </div>
  )
}

function DetailsPanel({ hits }: { hits: RetrievalHit[] }) {
  return (
    <div className="mb-3 rounded-xl border border-line bg-field p-3">
      <div className="mb-2 text-xs font-medium text-muted">检索到 {hits.length} 条</div>
      <div className="scrollbar-none max-h-72 space-y-2 overflow-y-auto">
        {hits.map((h, i) => (
          <HitCard key={i} h={h} />
        ))}
      </div>
    </div>
  )
}

function HitCard({ h }: { h: RetrievalHit }) {
  const [open, setOpen] = useState(false)
  const loc = `📄 ${h.source_doc}${h.heading_path ? ' > ' + h.heading_path : ''}${
    h.page != null ? ' (p.' + h.page + ')' : ''
  }`
  const long = h.text.length > 200
  const text = long && !open ? h.text.slice(0, 200) + '…' : h.text
  return (
    <div className="rounded-lg bg-white p-2 text-xs">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="truncate text-foreground">{loc}</span>
        <span className="shrink-0 text-muted">score {h.score.toFixed(3)}</span>
      </div>
      <p className="whitespace-pre-wrap leading-5 text-muted">{text}</p>
      {long && (
        <button onClick={() => setOpen((o) => !o)} className="mt-1 text-brand hover:underline">
          {open ? '收起' : '展开'}
        </button>
      )}
    </div>
  )
}

function Cursor() {
  return (
    <span className="ml-0.5 inline-block h-[1.05em] w-[3px] translate-y-[2px] animate-pulse rounded-sm bg-brand" />
  )
}

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1 py-1">
      <span className="inline-block h-2 w-2 animate-[bounce_1.4s_infinite] rounded-full bg-brand/40" style={{ animationDelay: '0s' }} />
      <span className="inline-block h-2 w-2 animate-[bounce_1.4s_infinite] rounded-full bg-brand/40" style={{ animationDelay: '0.2s' }} />
      <span className="inline-block h-2 w-2 animate-[bounce_1.4s_infinite] rounded-full bg-brand/40" style={{ animationDelay: '0.4s' }} />
    </div>
  )
}

function CopyButton({ text }: { text: string }) {
  return (
    <button
      onClick={() => navigator.clipboard?.writeText(text).catch(() => {})}
      className="rounded-md p-1 transition hover:bg-hover"
      title="复制"
    >
      <Copy className="h-4 w-4" strokeWidth={1.75} />
    </button>
  )
}

/** Python 风格文件名 `Content_%Y%m%d%H%M%S%f.md`；%f 为 6 位微秒，JS 只有毫秒，用 ms*1000 补零模拟 */
function downloadMarkdown(text: string): void {
  const now = new Date()
  const p = (n: number, w = 2) => String(n).padStart(w, '0')
  const micro = String(now.getMilliseconds() * 1000).padStart(6, '0')
  const stamp =
    `${now.getFullYear()}${p(now.getMonth() + 1)}${p(now.getDate())}` +
    `${p(now.getHours())}${p(now.getMinutes())}${p(now.getSeconds())}${micro}`
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `Content_${stamp}.md`
  a.click()
  URL.revokeObjectURL(url)
}

function DownloadButton({ text }: { text: string }) {
  return (
    <button
      onClick={() => downloadMarkdown(text)}
      className="rounded-md p-1 transition hover:bg-hover"
      title="下载为 Markdown"
    >
      <Download className="h-4 w-4" strokeWidth={1.75} />
    </button>
  )
}

/** If an inline-code string is a KB image path (../images/, images/, /images/ + hash name),
 * return the loadable /images/ URL, else null. */
function imagePathToSrc(text: string): string | null {
  const m = text.trim().match(/^(?:(?:\.\.\/)*images\/|\/images\/)(image_[0-9a-f]{16}\.png)$/)
  return m ? `/images/${m[1]}` : null
}

function buildMdComponents(openImage: (src: string) => void): Components {
  return {
  p: ({ node, ...props }) => <p className="mb-2 leading-7" {...props} />,
  h1: ({ node, ...props }) => <h1 className="mb-2 mt-4 text-xl font-semibold" {...props} />,
  h2: ({ node, ...props }) => <h2 className="mb-2 mt-4 text-lg font-semibold" {...props} />,
  h3: ({ node, ...props }) => <h3 className="mb-1 mt-3 font-semibold" {...props} />,
  ul: ({ node, ...props }) => <ul className="mb-2 list-disc pl-5 leading-7" {...props} />,
  ol: ({ node, ...props }) => <ol className="mb-2 list-decimal pl-5 leading-7" {...props} />,
  a: ({ node, ...props }) => (
    <a className="text-brand underline" target="_blank" rel="noreferrer" {...props} />
  ),
  blockquote: ({ node, ...props }) => (
    <blockquote className="my-2 border-l-2 border-line pl-3 text-muted" {...props} />
  ),
  table: ({ node, ...props }) => (
    <div className="my-3 overflow-x-auto">
      <table className="w-full border-collapse text-sm" {...props} />
    </div>
  ),
  thead: ({ node, ...props }) => <thead className="bg-field" {...props} />,
  th: ({ node, ...props }) => (
    <th className="border border-line px-3 py-1.5 text-left font-semibold" {...props} />
  ),
  td: ({ node, ...props }) => (
    <td className="border border-line px-3 py-1.5" {...props} />
  ),
  img: ({ node, src, ...props }) => {
    // 把 `../images/…` / `images/…` 归一成 `/images/…`，让后端挂载点能正常提供图片
    let s = src ?? ''
    while (s.startsWith('../')) s = s.slice(3)
    const fixedSrc = s.startsWith('images/')
      ? `/${s}`
      : s.startsWith('/images/')
        ? s
        : src
    return (
      <img
        src={fixedSrc}
        className="my-2 max-h-48 max-w-full cursor-pointer rounded-lg object-contain transition hover:opacity-90"
        alt=""
        onClick={() => fixedSrc && openImage(fixedSrc)}
        {...props}
      />
    )
  },
  pre: ({ node, ...props }) => <PreBlock {...props} />,
  code: ({ node, className, children, ...props }) => {
    if (className?.includes('language-')) {
      return (
        <code className={className} {...props}>
          {children}
        </code>
      )
    }
    // 行内代码恰好是知识库图片路径 → 直接渲染成图片
    if (typeof children === 'string') {
      const imgSrc = imagePathToSrc(children)
      if (imgSrc) {
        return (
          <img
            src={imgSrc}
            className="my-2 max-h-48 max-w-full cursor-pointer rounded-lg object-contain transition hover:opacity-90"
            alt=""
            onClick={() => openImage(imgSrc)}
          />
        )
      }
    }
    return (
      <code className="rounded bg-field px-1 py-0.5 font-mono text-[13px]">{children}</code>
    )
  },
  }
}

function ImagePreview({ src, onClose }: { src: string; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div className="relative" onClick={(e) => e.stopPropagation()}>
        <img
          src={src}
          className="max-h-[90vh] max-w-[90vw] rounded-lg object-contain"
          alt=""
        />
        <button
          onClick={onClose}
          className="absolute -right-3 -top-3 flex h-8 w-8 items-center justify-center rounded-full bg-white text-gray-700 shadow hover:bg-gray-100"
        >
          ✕
        </button>
      </div>
    </div>
  )
}

function PreBlock({ children }: { children?: ReactNode }) {
  const ref = useRef<HTMLPreElement>(null)
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard?.writeText(ref.current?.innerText ?? '').catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <div className="group relative my-3 overflow-hidden rounded-lg">
      <button
        onClick={copy}
        className="absolute right-2 top-2 z-10 rounded bg-white/10 px-2 py-0.5 text-xs text-white/70 opacity-0 transition hover:bg-white/20 group-hover:opacity-100"
        title="复制代码"
      >
        {copied ? '已复制' : '复制'}
      </button>
      <pre ref={ref} className="m-0 bg-transparent text-[13px] leading-6">
        {children}
      </pre>
    </div>
  )
}

/** 把裸的 /workspace/ 路径转成可点击的 markdown 链接（已在链接内/代码里的不动），
 *  兜底 agent 有时以纯文本输出下载路径的情况 */
function linkifyWorkspace(text: string): string {
  return text.replace(/(^|[^`\[(])(\/workspace\/[^\s)\]`|，。；;]+)/g, (_m, pre, path) => {
    return `${pre}[${path}](${path})`
  })
}

function Markdown({ text }: { text: string }) {
  const [preview, setPreview] = useState<string | null>(null)
  return (
    <>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[
          rehypeRaw, // 渲染原始 HTML（如 <img src="../images/...">）为真实元素
          [rehypeHighlight, {
            languages: {
              python: hlPython, javascript: hlJavascript, cpp: hlCpp, c: hlC, csharp: hlCsharp,
              lua: hlLua, bash: hlBash, json: hlJson, xml: hlXml, css: hlCss, markdown: hlMarkdown,
            },
          }],
        ]}
        components={buildMdComponents(setPreview)}
      >
        {linkifyWorkspace(text)}
      </ReactMarkdown>
      {preview && <ImagePreview src={preview} onClose={() => setPreview(null)} />}
    </>
  )
}
