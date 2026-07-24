import { useRef, type KeyboardEvent } from 'react'
import { ArrowUp, Square } from 'lucide-react'
import { cn } from '../../lib/utils'

interface Props {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  onStop: () => void
  streaming: boolean
}

export function Composer({ value, onChange, onSend, onStop, streaming }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null)

  const resize = () => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (streaming) return
      if (value.trim()) onSend()
    }
  }

  const canSend = value.trim().length > 0

  return (
    <div className="mx-auto w-full max-w-[774px] px-4">
      <div className="rounded-[26px] border border-line bg-white p-2 shadow-[0_2px_12px_rgba(0,0,0,0.06)] transition focus-within:border-brand-light-border focus-within:shadow-[0_2px_16px_rgba(57,100,254,0.12)]">
        <textarea
          ref={ref}
          value={value}
          onChange={(e) => {
            onChange(e.target.value)
            resize()
          }}
          onKeyDown={onKeyDown}
          rows={1}
          placeholder="问我任何关于知识库的问题"
          className="scrollbar-none max-h-[200px] w-full resize-none bg-transparent px-3 pt-2 text-[16px] leading-6 text-foreground outline-none placeholder:text-placeholder"
        />
        <div className="flex items-center gap-2 px-1 pt-1">
          {streaming ? (
            <button
              onClick={onStop}
              title="停止生成"
              className="ml-auto flex h-8 w-8 items-center justify-center rounded-full bg-foreground text-white transition hover:brightness-110"
            >
              <Square className="h-3 w-3 fill-current" strokeWidth={0} />
            </button>
          ) : (
            <button
              onClick={onSend}
              disabled={!canSend}
              className={cn(
                'ml-auto flex h-8 w-8 items-center justify-center rounded-full transition',
                canSend ? 'bg-brand text-white hover:brightness-95' : 'bg-line text-muted',
              )}
            >
              <ArrowUp className="h-5 w-5" strokeWidth={2} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
