// Frontend message model (mapped from backend SSE events / session history).

import type { RetrievalHit } from '../lib/api'

export type Role = 'user' | 'assistant'

export type ToolEvent = {
  id: string // tool_call_id
  name: string
  status: 'running' | 'ok' | 'error' | 'cancelled'
  content?: string
  details?: RetrievalHit[] // structured hits for the details panel (kb_search)
  elapsed?: number // 本步骤用时（秒，实时流式计算）
  arguments?: Record<string, unknown> // 工具调用参数（path/skill_name/command/query，供步骤详情显示）
}

export type ChatMessage = {
  id: string
  role: Role
  content: string
  toolEvents?: ToolEvent[]
  isClarify?: boolean
  error?: string
  feedback?: 'up' | 'down' | null  // user's rating on this message
  turnElapsed?: number // total seconds from first tool_start to final (set once on completion)
}
