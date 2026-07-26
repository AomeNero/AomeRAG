import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, ChevronUp, MessageSquare, ThumbsDown, ThumbsUp, Trash2 } from 'lucide-react'
import { deleteFeedback, getAllFeedback, type FeedbackItem } from '../../lib/api'

export function FeedbackPage() {
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
    <div className="min-h-screen bg-gray-50 p-6 text-gray-900">
      <div className="mx-auto max-w-5xl">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold">反馈管理</h1>
          <div className="flex items-center gap-3">
            <button
              onClick={load}
              className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:brightness-95"
            >
              刷新
            </button>
            <Link to="/admin" className="text-sm text-blue-600 hover:underline">
              ← 管理后台
            </Link>
            <Link to="/" className="text-sm text-blue-600 hover:underline">
              聊天
            </Link>
          </div>
        </div>

        {loading && <p className="text-gray-400">加载中…</p>}
        {!loading && items.length === 0 && (
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
                    <><ChevronUp className="h-3 w-3" /> 收起</>
                  ) : (
                    <><ChevronDown className="h-3 w-3" /> 查看详情</>
                  )}
                </button>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
