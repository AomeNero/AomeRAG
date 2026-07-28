import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Check, Copy, Loader2, RefreshCw, ThumbsDown, ThumbsUp } from 'lucide-react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
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

  // find the preceding user message for a given assistant message
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
  const hits = m.toolEvents?.flatMap((t) => t.details ?? []) ?? []
  const ring = highlight ? 'ring-2 ring-brand rounded-lg' : ''

  // detect "no results": a tool_result with details === [] (empty array, search ran but 0 hits)
  const hadEmptySearch = m.toolEvents?.some(
    (t) => t.status === 'ok' && t.details !== undefined && t.details.length === 0
  ) ?? false

  const rate = async (rating: 'up' | 'down', comment?: string) => {
    if (m.feedback) return
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
    } catch { /* ignore */ }
  }

  const onThumbsUp = () => { void rate('up') }
  const onThumbsDown = () => { setShowDownDialog(true) }
  const submitDown = async () => {
    await rate('down', downComment)  // single call with comment included
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

  return (
    <div data-midx={index} className={`mb-6 p-px ${ring}`}>
      {m.isClarify && (
        <div className="mb-2 inline-flex items-center gap-1 rounded-full bg-brand-light px-2.5 py-1 text-xs font-medium text-brand">
          💬 需要补充信息
        </div>
      )}
      {m.toolEvents?.map((t) => (
        <ToolChip key={t.id} t={t} expanded={showDetails} clickable={!!t.details} onClick={() => setShowDetails((v) => !v)} elapsed={m.turnElapsed} />
      ))}
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
            disabled={!!m.feedback}
            className={cn('rounded-md p-1 transition hover:bg-hover', m.feedback === 'up' && 'text-brand')}
            title="好的回答"
          >
            <ThumbsUp className="h-4 w-4" strokeWidth={1.75} />
          </button>
          <button
            onClick={onThumbsDown}
            disabled={!!m.feedback}
            className={cn('rounded-md p-1 transition hover:bg-hover', m.feedback === 'down' && 'text-red-500')}
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

function ToolChip({
  t,
  expanded,
  clickable,
  onClick,
  elapsed,
}: {
  t: ToolEvent
  expanded: boolean
  clickable: boolean
  onClick: () => void
  elapsed?: number
}) {
  let label = '正在检索'
  let icon: ReactNode = <Loader2 className="h-3.5 w-3.5 animate-spin text-brand" strokeWidth={2} />
  let tone = 'text-muted'
  if (t.status === 'ok') {
    const n = t.details?.length ?? (t.content?.match(/^\[\d+\]/gm) ?? []).length
    const src = t.details?.[0]?.source_doc ?? t.content?.match(/source=([^\s>]+)/)?.[1]
    label = n > 0 ? `知识库检索 · ${n} 条` : '知识库检索完成（0 条）'
    if (elapsed != null) label += ` · 用时 ${elapsed.toFixed(1)} 秒`
    if (src) label += ` · ${src}`
    icon = <Check className="h-3.5 w-3.5 text-brand" strokeWidth={2} />
    tone = 'text-foreground'
  } else if (t.status === 'cancelled') {
    label = '已跳过'
    icon = <span className="text-muted">⊘</span>
    tone = 'text-muted'
  } else if (t.status === 'error') {
    label = '知识库检索失败'
    icon = <span className="text-red-500">⚠</span>
    tone = 'text-red-600'
  }

  const cls = `mb-2 inline-flex items-center gap-1.5 rounded-full bg-field px-2.5 py-1 text-xs ${tone} ${
    clickable ? 'cursor-pointer transition hover:bg-hover' : ''
  }`
  if (!clickable) {
    return (
      <div className={cls}>
        {icon}
        <span>{label}</span>
      </div>
    )
  }
  return (
    <button onClick={onClick} className={cls} title="点击展开/收起检索详情">
      {icon}
      <span>{label}</span>
      <ChevronIcon expanded={expanded} />
    </button>
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

const mdComponents: Components = {
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
    const fixedSrc = src?.startsWith('images/')
      ? `/${src}`
      : src?.startsWith('/images/')
      ? src
      : src
    return <img src={fixedSrc} className="my-2 max-w-full rounded-lg" alt="" {...props} />
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
    return (
      <code className="rounded bg-field px-1 py-0.5 font-mono text-[13px]">{children}</code>
    )
  },
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

function Markdown({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[
        [rehypeHighlight, {
          languages: {
            python: hlPython, javascript: hlJavascript, cpp: hlCpp, c: hlC, csharp: hlCsharp,
            lua: hlLua, bash: hlBash, json: hlJson, xml: hlXml, css: hlCss, markdown: hlMarkdown,
          },
        }],
      ]}
      components={mdComponents}
    >
      {text}
    </ReactMarkdown>
  )
}
