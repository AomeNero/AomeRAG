import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { MessageSquare, ThumbsDown, ThumbsUp } from 'lucide-react'
import { getAllFeedback, type FeedbackItem } from '../../lib/api'

export function FeedbackPage() {
  const [items, setItems] = useState<FeedbackItem[]>([])
  const [loading, setLoading] = useState(false)

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
          {items.map((f) => (
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
              </div>

              {f.user_question && (
                <div className="mb-1 text-sm">
                  <span className="text-gray-400">问: </span>
                  <span className="text-gray-700">{f.user_question.slice(0, 200)}</span>
                </div>
              )}
              {f.ai_answer && (
                <div className="mb-1 text-sm">
                  <span className="text-gray-400">答: </span>
                  <span className="text-gray-600">{f.ai_answer.slice(0, 300)}</span>
                  {f.ai_answer.length > 300 && '…'}
                </div>
              )}
              {f.comment && (
                <div className="mt-1 rounded bg-gray-50 px-3 py-1.5 text-sm text-gray-700">
                  💬 {f.comment}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
