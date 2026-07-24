import { useEffect, useRef, type ReactNode } from 'react'
import { Check, Copy, Loader2, RefreshCw } from 'lucide-react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage, ToolEvent } from '../../data/chat'

interface Props {
  messages: ChatMessage[]
  streamingId: string | null
  onRegenerate: () => void
}

export function MessageList({ messages, streamingId, onRegenerate }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  const lastAssistantId = [...messages].reverse().find((m) => m.role === 'assistant')?.id

  return (
    <div ref={scrollRef} className="scrollbar-none flex-1 overflow-y-auto">
      <div className="mx-auto max-w-[774px] px-4 py-6">
        {messages.map((m) => (
          <Message
            key={m.id}
            m={m}
            streaming={streamingId === m.id}
            isLast={m.id === lastAssistantId}
            onRegenerate={onRegenerate}
          />
        ))}
      </div>
    </div>
  )
}

function Message({
  m,
  streaming,
  isLast,
  onRegenerate,
}: {
  m: ChatMessage
  streaming: boolean
  isLast: boolean
  onRegenerate: () => void
}) {
  if (m.role === 'user') {
    return (
      <div className="mb-6 flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl bg-field px-4 py-2.5 text-[15px] leading-7 text-foreground">
          {m.content}
        </div>
      </div>
    )
  }

  return (
    <div className="mb-6">
      {m.isClarify && (
        <div className="mb-2 inline-flex items-center gap-1 rounded-full bg-brand-light px-2.5 py-1 text-xs font-medium text-brand">
          💬 需要补充信息
        </div>
      )}
      {m.toolEvents?.map((t) => <ToolChip key={t.id} t={t} />)}
      <div className="text-[15px] leading-7 text-foreground">
        {m.content ? <Markdown text={m.content} /> : null}
        {streaming && !m.error && <Cursor />}
      </div>
      {m.error && (
        <div className="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">
          {m.error}
        </div>
      )}
      {!streaming && !m.error && (
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
        </div>
      )}
    </div>
  )
}

function ToolChip({ t }: { t: ToolEvent }) {
  let label = '检索知识库'
  let icon: ReactNode = <Loader2 className="h-3.5 w-3.5 animate-spin text-brand" strokeWidth={2} />
  let tone = 'text-muted'
  if (t.status === 'ok') {
    const hits = (t.content?.match(/^\[\d+\]/gm) ?? []).length
    const src = t.content?.match(/source=([^\s>]+)/)?.[1]
    label = hits > 0 ? `知识库检索 · ${hits} 条` : '知识库检索完成'
    if (src) label += ` · ${src}`
    icon = <Check className="h-3.5 w-3.5 text-brand" strokeWidth={2} />
    tone = 'text-foreground'
  } else if (t.status === 'error') {
    label = '知识库检索失败'
    icon = <span className="text-red-500">⚠</span>
    tone = 'text-red-600'
  }
  return (
    <div className={`mb-2 inline-flex items-center gap-1.5 rounded-full bg-field px-2.5 py-1 text-xs ${tone}`}>
      {icon}
      <span>{label}</span>
    </div>
  )
}

function Cursor() {
  return (
    <span className="ml-0.5 inline-block h-[1.05em] w-[3px] translate-y-[2px] animate-pulse rounded-sm bg-brand" />
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
  pre: ({ node, ...props }) => (
    <pre
      className="my-3 overflow-x-auto rounded-lg bg-[#0f1115] p-3 text-[13px] leading-6 text-[#e6e6e6]"
      {...props}
    />
  ),
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

function Markdown({ text }: { text: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
      {text}
    </ReactMarkdown>
  )
}
