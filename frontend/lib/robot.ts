const BASE = '/api/robot'

export type RobotConversation = {
  id: number
  titre: string
  model: string
  created_at: string
  updated_at: string
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_creation_tokens: number
  cost_usd: number
}

export type RobotMessage = { id: number; role: string; content: string; created_at: string }
export type RobotPrefs = { model: string; effort: string; max_tokens: number }
export type RobotStatus = RobotPrefs & { api_key_configured: boolean; tools: string[] }
export type Insight = { level: string; message: string }
export type Recap = { date: string; sections: Record<string, string> }
export type PendingAction = { id: number; tool: string; args: Record<string, unknown> }

const json = (r: Response) => r.json()
const H = { 'Content-Type': 'application/json' }

export const fetchStatus = (): Promise<RobotStatus> => fetch(`${BASE}/status`).then(json)
export const fetchSettings = (): Promise<RobotPrefs> => fetch(`${BASE}/settings`).then(json)
export const saveSettings = (p: Partial<RobotPrefs>): Promise<RobotPrefs> =>
  fetch(`${BASE}/settings`, { method: 'POST', headers: H, body: JSON.stringify(p) }).then(json)

export const listConversations = (): Promise<RobotConversation[]> =>
  fetch(`${BASE}/conversations`).then(json)
export const createConversation = (titre = ''): Promise<RobotConversation> =>
  fetch(`${BASE}/conversations`, { method: 'POST', headers: H, body: JSON.stringify({ titre }) }).then(json)
export const getConversation = (id: number): Promise<{ conversation: RobotConversation; messages: RobotMessage[] }> =>
  fetch(`${BASE}/conversations/${id}`).then(json)
export const deleteConversation = (id: number) =>
  fetch(`${BASE}/conversations/${id}`, { method: 'DELETE' })

export const confirmAction = (id: number) => fetch(`${BASE}/actions/${id}/confirm`, { method: 'POST' }).then(json)
export const denyAction = (id: number) => fetch(`${BASE}/actions/${id}/deny`, { method: 'POST' }).then(json)

export const fetchRecap = (): Promise<Recap> => fetch(`${BASE}/recap`).then(json)
export const fetchInsights = (): Promise<Insight[]> => fetch(`${BASE}/insights`).then(json)

export type ChatEvent =
  | { type: 'token'; text: string }
  | { type: 'pending_action'; id: number; tool: string; args: Record<string, unknown> }
  | { type: 'error'; message: string }
  | { type: 'done'; cost: number; total_cost: number }

/** Lit le flux SSE de /chat et appelle onEvent pour chaque évènement. */
export async function streamChat(
  conversationId: number,
  message: string,
  onEvent: (e: ChatEvent) => void,
): Promise<void> {
  const resp = await fetch(`${BASE}/chat`, {
    method: 'POST', headers: H,
    body: JSON.stringify({ conversation_id: conversationId, message }),
  })
  if (!resp.ok || !resp.body) {
    onEvent({ type: 'error', message: `Erreur réseau (${resp.status}).` })
    return
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''
    for (const chunk of chunks) {
      const line = chunk.split('\n').find((l) => l.startsWith('data:'))
      if (!line) continue
      try {
        onEvent(JSON.parse(line.slice(5).trim()) as ChatEvent)
      } catch {
        // ignore les lignes non-JSON
      }
    }
  }
}
