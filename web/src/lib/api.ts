// API client for the AomeRAG backend. SSE is read via fetch + ReadableStream (not EventSource)
// so we can send the custom X-User-Id header.

export type ChatEvent =
  | { type: 'session'; session_id: string }
  | { type: 'token'; text: string }
  | { type: 'tool_start'; tool_call_id: string; name: string; arguments: Record<string, unknown> }
  | { type: 'tool_result'; tool_call_id: string; name: string; is_error: boolean; content: string; details?: RetrievalHit[]; cancelled?: boolean }
  | { type: 'clarify'; question: string }
  | { type: 'final' }
  | { type: 'error'; code: string; message: string }

export type Session = {
  id: string
  title: string | null
  created_at: number
  updated_at: number
}

export type HistoryMessage = {
  role: 'user' | 'assistant'
  text: string
  toolEvents?: { id: string; name: string; status: 'ok' | 'error'; content: string }[]
}

export type RetrievalHit = {
  source_doc: string
  heading_path: string
  page: number | null
  score: number
  text: string
}

const USER_KEY = 'aome_user_id'

/** UUID v4 — uses crypto.randomUUID when available (HTTPS/localhost),
 * falls back to Math.random for non-secure contexts (e.g. cpolar HTTP tunnels). */
function uuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

function getUserId(): string {
  let id = localStorage.getItem(USER_KEY)
  if (!id) {
    id = uuid()
    localStorage.setItem(USER_KEY, id)
  }
  return id
}

function authHeaders(json = false): Record<string, string> {
  const h: Record<string, string> = { 'X-User-Id': getUserId() }
  if (json) h['Content-Type'] = 'application/json'
  return h
}

/** Parse an SSE response body into a stream of decoded JSON event objects. */
async function* sseEvents(response: Response): AsyncGenerator<Record<string, unknown>> {
  const reader = response.body?.getReader()
  if (!reader) return
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep: number
    while ((sep = buffer.indexOf('\n\n')) >= 0) {
      const raw = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      const dataLine = raw.split('\n').find((l) => l.startsWith('data:'))
      if (!dataLine) continue
      const payload = dataLine.slice(5).trim()
      if (!payload) continue
      try {
        yield JSON.parse(payload) as Record<string, unknown>
      } catch {
        // skip malformed keep-alive / partial
      }
    }
  }
}

export async function* streamChat(
  body: { message: string; session_id?: string },
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const resp = await fetch('/chat', {
    method: 'POST',
    headers: authHeaders(true),
    body: JSON.stringify({ ...body, stream: true }),
    signal,
  })
  if (!resp.ok) throw new Error(`/chat failed: ${resp.status}`)
  for await (const ev of sseEvents(resp)) yield ev as unknown as ChatEvent
}

export async function listSessions(): Promise<Session[]> {
  const r = await fetch('/sessions', { headers: authHeaders() })
  if (!r.ok) throw new Error(`/sessions failed: ${r.status}`)
  return (await r.json()) as Session[]
}

export async function getMessages(sessionId: string): Promise<HistoryMessage[]> {
  const r = await fetch(`/sessions/${sessionId}/messages`, { headers: authHeaders() })
  if (!r.ok) throw new Error(`/sessions/{id}/messages failed: ${r.status}`)
  return (await r.json()) as HistoryMessage[]
}

export async function deleteSession(sessionId: string): Promise<void> {
  const r = await fetch(`/sessions/${sessionId}`, { method: 'DELETE', headers: authHeaders() })
  if (!r.ok) throw new Error(`/sessions delete failed: ${r.status}`)
}

export type SystemStats = {
  n_chunks: number
  llm_model: string
  embed_model: string
  embed_dim: number
  collection: string
  top_k: number
}

export async function getStats(): Promise<SystemStats> {
  const r = await fetch('/stats', { headers: authHeaders() })
  if (!r.ok) throw new Error(`/stats failed: ${r.status}`)
  return (await r.json()) as SystemStats
}

export async function generateTitle(sessionId: string): Promise<string> {
  const r = await fetch(`/sessions/${sessionId}/title`, { method: 'POST', headers: authHeaders() })
  if (!r.ok) throw new Error(`/title failed: ${r.status}`)
  return ((await r.json()) as { title: string }).title
}

export async function patchSessionTitle(sessionId: string, title: string): Promise<void> {
  const r = await fetch(`/sessions/${sessionId}`, {
    method: 'PATCH',
    headers: authHeaders(true),
    body: JSON.stringify({ title }),
  })
  if (!r.ok) throw new Error(`PATCH session failed: ${r.status}`)
}

export type SessionHit = {
  session_id: string
  title: string
  role: 'user' | 'assistant'
  snippet: string
}

export async function searchSessions(q: string): Promise<SessionHit[]> {
  const r = await fetch(`/sessions/search?q=${encodeURIComponent(q)}`, { headers: authHeaders() })
  if (!r.ok) throw new Error(`/sessions/search failed: ${r.status}`)
  return (await r.json()) as SessionHit[]
}

// ---- Admin API ----

export async function* streamCleanDirInc(signal?: AbortSignal): AsyncGenerator<CleanEvent> {
  const resp = await fetch('/clean/dir/inc', { method: 'POST', headers: authHeaders(), signal })
  if (!resp.ok) throw new Error(`/clean/dir/inc failed: ${resp.status}`)
  for await (const ev of sseEvents(resp)) yield ev as CleanEvent
}

// Loose shape for /update/dir events (clean scan/file_done/deleted/summary + ingest events).
export type CleanEvent = {
  type: string
  source_doc?: string
  raw_dir?: string
  n_files?: number
  n_skipped?: number
  n_cleaned?: number
  n_deleted?: number
  n_docs?: number
  n_chunks?: number
  n_failed?: number
  status?: string
  error?: string
  reason?: string
  errors?: string[]
  elapsed_s?: number
}

export async function* streamIngestDirInc(signal?: AbortSignal): AsyncGenerator<CleanEvent> {
  const resp = await fetch('/ingest/dir/inc', { method: 'POST', headers: authHeaders(), signal })
  if (!resp.ok) throw new Error(`/ingest/dir/inc failed: ${resp.status}`)
  for await (const ev of sseEvents(resp)) yield ev as CleanEvent
}

export type FileInfo = { name: string; size: number }
export type AdminSession = {
  id: string
  user_id: string
  title: string | null
  created_at: number
  updated_at: number
}

export async function getFiles(
  type: 'raw-data' | 'md-data',
): Promise<{ dir: string; n_files: number; files: FileInfo[] }> {
  const r = await fetch(`/admin/files?type=${type}`, { headers: authHeaders() })
  if (!r.ok) throw new Error(`/admin/files failed: ${r.status}`)
  return (await r.json()) as { dir: string; n_files: number; files: FileInfo[] }
}

export async function resetStore(): Promise<void> {
  const r = await fetch('/admin/reset', { method: 'POST', headers: authHeaders() })
  if (!r.ok) throw new Error(`/admin/reset failed: ${r.status}`)
}

export async function getAllSessions(): Promise<AdminSession[]> {
  const r = await fetch('/admin/sessions', { headers: authHeaders() })
  if (!r.ok) throw new Error(`/admin/sessions failed: ${r.status}`)
  return (await r.json()) as AdminSession[]
}

export async function getAdminMessages(sessionId: string): Promise<HistoryMessage[]> {
  const r = await fetch(`/admin/sessions/${sessionId}/messages`, { headers: authHeaders() })
  if (!r.ok) throw new Error(`/admin/sessions/${sessionId}/messages failed: ${r.status}`)
  return (await r.json()) as HistoryMessage[]
}

// ---- KB management (知识库管理) ----

export type KbDocStatus = 'ok' | 'orphan' | 'unsliced'

export type KbDoc = {
  source_doc: string
  file_exists: boolean
  n_chunks: number
  status: KbDocStatus
}

export type KbDocsResponse = {
  total: number
  page: number
  page_size: number
  items: KbDoc[]
}

export type KbChunk = {
  id: string
  source_doc: string
  chunk_index: number
  heading_path: string
  text_preview: string
  created_at: number
}

export async function listKbDocs(
  page: number,
  pageSize: number,
  q = '',
  filter = '',
): Promise<KbDocsResponse> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (q) params.set('q', q)
  if (filter) params.set('filter', filter)
  const r = await fetch(`/admin/kb/docs?${params}`, { headers: authHeaders() })
  if (!r.ok) throw new Error(`/admin/kb/docs failed: ${r.status}`)
  return (await r.json()) as KbDocsResponse
}

export async function getKbDocChunks(sourceDoc: string): Promise<KbChunk[]> {
  const r = await fetch(`/admin/kb/chunks?source_doc=${encodeURIComponent(sourceDoc)}`, {
    headers: authHeaders(),
  })
  if (!r.ok) throw new Error(`/admin/kb/chunks failed: ${r.status}`)
  return ((await r.json()) as { chunks: KbChunk[] }).chunks
}

export async function deleteKbFile(sourceDoc: string): Promise<void> {
  const r = await fetch(`/admin/kb/file?source_doc=${encodeURIComponent(sourceDoc)}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!r.ok) throw new Error(`/admin/kb/file failed: ${r.status}`)
}

export async function deleteKbDocChunks(sourceDoc: string): Promise<void> {
  const r = await fetch(`/admin/kb/doc-chunks?source_doc=${encodeURIComponent(sourceDoc)}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!r.ok) throw new Error(`/admin/kb/doc-chunks failed: ${r.status}`)
}

export async function deleteKbChunk(chunkId: string): Promise<void> {
  const r = await fetch(`/admin/kb/chunk?id=${encodeURIComponent(chunkId)}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!r.ok) throw new Error(`/admin/kb/chunk failed: ${r.status}`)
}

export async function reingestKbDoc(sourceDoc: string): Promise<{ n_chunks: number }> {
  const r = await fetch(`/admin/kb/reingest?source_doc=${encodeURIComponent(sourceDoc)}`, {
    method: 'POST',
    headers: authHeaders(true),
  })
  if (!r.ok) throw new Error(`/admin/kb/reingest failed: ${r.status}`)
  return (await r.json()) as { n_chunks: number }
}

export async function syncKbMeta(): Promise<{ n_docs: number; n_chunks: number; n_skipped: number }> {
  const r = await fetch('/admin/kb/sync', { method: 'POST', headers: authHeaders() })
  if (!r.ok) throw new Error(`/admin/kb/sync failed: ${r.status}`)
  return (await r.json()) as { n_docs: number; n_chunks: number; n_skipped: number }
}

export async function clearCleanState(): Promise<void> {
  const r = await fetch('/admin/kb/clean-state/clear', { method: 'POST', headers: authHeaders() })
  if (!r.ok) throw new Error(`/admin/kb/clean-state/clear failed: ${r.status}`)
}

export async function clearIngestState(): Promise<void> {
  const r = await fetch('/admin/kb/ingest-state/clear', { method: 'POST', headers: authHeaders() })
  if (!r.ok) throw new Error(`/admin/kb/ingest-state/clear failed: ${r.status}`)
}

// ---- Feedback API ----

export type FeedbackBody = {
  type: 'rating' | 'missing'
  session_id?: string
  message_id?: string
  rating?: 'up' | 'down'
  user_question?: string
  ai_answer?: string
  comment?: string
}

export type FeedbackItem = {
  id: string
  type: string
  session_id: string | null
  user_id: string
  message_id: string | null
  rating: string | null
  user_question: string | null
  ai_answer: string | null
  comment: string | null
  created_at: number
}

export async function submitFeedback(body: FeedbackBody): Promise<void> {
  const r = await fetch('/feedback', {
    method: 'POST',
    headers: authHeaders(true),
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`/feedback failed: ${r.status}`)
}

export async function getAllFeedback(): Promise<FeedbackItem[]> {
  const r = await fetch('/admin/feedback/all', { headers: authHeaders() })
  if (!r.ok) throw new Error(`/admin/feedback failed: ${r.status}`)
  return (await r.json()) as FeedbackItem[]
}

export async function deleteFeedback(id: string): Promise<void> {
  const r = await fetch(`/admin/feedback/${id}`, { method: 'DELETE', headers: authHeaders() })
  if (!r.ok) throw new Error(`delete feedback failed: ${r.status}`)
}
