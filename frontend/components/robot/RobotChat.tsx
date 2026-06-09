'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Plus, Send, Trash2, Settings2, Sparkles, AlertTriangle, Check, X } from 'lucide-react'
import {
  fetchStatus, listConversations, createConversation, getConversation, deleteConversation,
  streamChat, confirmAction, denyAction, saveSettings, fetchInsights,
  type RobotConversation, type RobotMessage, type RobotStatus, type PendingAction, type Insight,
} from '@/lib/robot'

type Msg = { role: string; content: string }

export default function RobotChat() {
  const [status, setStatus] = useState<RobotStatus | null>(null)
  const [convs, setConvs] = useState<RobotConversation[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [pending, setPending] = useState<PendingAction | null>(null)
  const [cost, setCost] = useState(0)
  const [showSettings, setShowSettings] = useState(false)
  const [insights, setInsights] = useState<Insight[]>([])
  const endRef = useRef<HTMLDivElement>(null)

  const refreshConvs = useCallback(() => {
    listConversations().then(setConvs).catch(() => setConvs([]))
  }, [])

  useEffect(() => {
    fetchStatus().then(setStatus).catch(() => setStatus(null))
    refreshConvs()
    fetchInsights().then((d) => setInsights(Array.isArray(d) ? d : [])).catch(() => setInsights([]))
  }, [refreshConvs])

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const openConv = useCallback(async (id: number) => {
    setActiveId(id)
    setPending(null)
    try {
      const { conversation, messages } = await getConversation(id)
      setMessages(messages.map((m: RobotMessage) => ({ role: m.role, content: m.content })))
      setCost(conversation.cost_usd)
    } catch {
      setMessages([])
    }
  }, [])

  const newConv = async () => {
    const c = await createConversation()
    refreshConvs()
    setActiveId(c.id)
    setMessages([])
    setCost(0)
    setPending(null)
  }

  const removeConv = async (id: number) => {
    if (!confirm('Supprimer cette conversation ?')) return
    await deleteConversation(id)
    if (activeId === id) { setActiveId(null); setMessages([]) }
    refreshConvs()
  }

  const send = async () => {
    const text = input.trim()
    if (!text || streaming) return
    let convId = activeId
    if (convId == null) {
      const c = await createConversation()
      convId = c.id
      setActiveId(c.id)
      refreshConvs()
    }
    setInput('')
    setPending(null)
    setMessages((m) => [...m, { role: 'user', content: text }, { role: 'assistant', content: '' }])
    setStreaming(true)
    try {
      await streamChat(convId, text, (e) => {
        if (e.type === 'token') {
          setMessages((m) => {
            const copy = [...m]
            copy[copy.length - 1] = { role: 'assistant', content: copy[copy.length - 1].content + e.text }
            return copy
          })
        } else if (e.type === 'pending_action') {
          setPending({ id: e.id, tool: e.tool, args: e.args })
        } else if (e.type === 'error') {
          toast.error(e.message)
        } else if (e.type === 'done') {
          setCost(e.total_cost)
        }
      })
    } finally {
      setStreaming(false)
      refreshConvs()
    }
  }

  const resolveAction = async (ok: boolean) => {
    if (!pending) return
    try {
      const res = ok ? await confirmAction(pending.id) : await denyAction(pending.id)
      if (ok && res?.result) {
        setMessages((m) => [...m, { role: 'assistant', content: `✅ ${res.result}` }])
      } else if (!ok) {
        setMessages((m) => [...m, { role: 'assistant', content: '❌ Action annulée.' }])
      }
    } catch {
      toast.error('Action impossible.')
    } finally {
      setPending(null)
    }
  }

  return (
    <div className="flex h-[calc(100vh-9rem)] gap-3">
      {/* Sidebar conversations */}
      <aside className="flex w-56 shrink-0 flex-col gap-2">
        <button onClick={() => void newConv()}
          className="flex items-center justify-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90">
          <Plus className="h-4 w-4" /> Nouvelle
        </button>
        <div className="flex-1 space-y-1 overflow-y-auto">
          {convs.map((c) => (
            <div key={c.id}
              className={`group flex items-center gap-1 rounded-md px-2 py-1.5 text-sm ${
                activeId === c.id ? 'bg-[var(--muted)]' : 'hover:bg-[var(--muted)]'}`}>
              <button onClick={() => void openConv(c.id)}
                className="min-w-0 flex-1 truncate text-left">{c.titre}</button>
              <button onClick={() => void removeConv(c.id)}
                aria-label="Supprimer"
                className="shrink-0 text-[var(--muted-foreground)] opacity-0 transition-opacity hover:text-[var(--destructive)] group-hover:opacity-100">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
          {convs.length === 0 && (
            <p className="px-2 py-3 text-xs text-[var(--muted-foreground)]">Aucune conversation.</p>
          )}
        </div>
      </aside>

      {/* Zone principale */}
      <div className="flex min-w-0 flex-1 flex-col rounded-xl border border-[var(--border)] bg-[var(--card)]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-2.5">
          <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
            <span>{status?.model ?? '—'}</span>
            <span>· coût&nbsp;${cost.toFixed(4)}</span>
          </div>
          <button onClick={() => setShowSettings((v) => !v)} aria-label="Réglages"
            className="rounded p-1.5 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]">
            <Settings2 className="h-4 w-4" />
          </button>
        </div>

        {showSettings && status && (
          <SettingsPanel status={status} onSaved={(s) => { setStatus({ ...status, ...s }); setShowSettings(false) }} />
        )}

        {status && !status.api_key_configured && (
          <div className="m-3 flex items-center gap-2 rounded-lg border border-[var(--warning-muted)] bg-[var(--warning-muted)] px-3 py-2 text-xs">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            Clé API Claude absente — renseigne <code className="mx-1">ANTHROPIC_API_KEY</code> pour activer le chat.
          </div>
        )}

        {insights.length > 0 && messages.length === 0 && (
          <div className="m-3 space-y-1.5">
            <p className="flex items-center gap-1.5 text-xs font-medium text-[var(--muted-foreground)]"><Sparkles className="h-3.5 w-3.5" /> Insights</p>
            {insights.map((i, k) => (
              <p key={k} className="rounded-md border border-[var(--border)] px-2.5 py-1.5 text-sm">{i.message}</p>
            ))}
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {messages.length === 0 && (
            <p className="mt-10 text-center text-sm text-[var(--muted-foreground)]">
              Pose une question sur ton budget, tes habitudes, ton agenda…
            </p>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-sm ${
                m.role === 'user'
                  ? 'bg-[var(--primary)] text-[var(--primary-foreground)]'
                  : 'bg-[var(--muted)] text-[var(--foreground)]'}`}>
                {m.content || (streaming && i === messages.length - 1 ? '…' : '')}
              </div>
            </div>
          ))}

          {pending && (
            <div className="rounded-xl border border-[var(--ring)] bg-[color-mix(in_srgb,var(--ring)_8%,transparent)] p-3">
              <p className="mb-2 text-sm font-medium">Confirmer l&apos;action&nbsp;: <span className="font-mono text-xs">{pending.tool}</span></p>
              <pre className="mb-2 overflow-x-auto rounded bg-[var(--background)] p-2 text-xs">{JSON.stringify(pending.args, null, 2)}</pre>
              <div className="flex gap-2">
                <button onClick={() => void resolveAction(true)}
                  className="flex items-center gap-1 rounded-md bg-[var(--success)] px-3 py-1.5 text-sm font-medium text-white hover:opacity-90">
                  <Check className="h-4 w-4" /> Confirmer
                </button>
                <button onClick={() => void resolveAction(false)}
                  className="flex items-center gap-1 rounded-md border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)]">
                  <X className="h-4 w-4" /> Annuler
                </button>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Input */}
        <div className="flex items-end gap-2 border-t border-[var(--border)] p-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send() } }}
            placeholder="Écris ton message… (Entrée pour envoyer)"
            rows={1}
            className="max-h-32 flex-1 resize-none rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          />
          <button onClick={() => void send()} disabled={streaming || !input.trim()}
            aria-label="Envoyer"
            className="rounded-md bg-[var(--primary)] p-2.5 text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50">
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

function SettingsPanel({ status, onSaved }: { status: RobotStatus; onSaved: (s: { model: string; effort: string }) => void }) {
  const [model, setModel] = useState(status.model)
  const [effort, setEffort] = useState(status.effort)
  const save = async () => {
    try {
      const s = await saveSettings({ model, effort })
      toast.success('Réglages enregistrés.')
      onSaved({ model: s.model, effort: s.effort })
    } catch {
      toast.error('Enregistrement impossible.')
    }
  }
  const sel = 'rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]'
  return (
    <div className="flex flex-wrap items-end gap-3 border-b border-[var(--border)] bg-[var(--muted)] px-4 py-3">
      <label className="flex flex-col gap-1 text-xs text-[var(--muted-foreground)]">
        Modèle
        <select value={model} onChange={(e) => setModel(e.target.value)} className={sel}>
          <option value="claude-opus-4-8">Opus 4.8</option>
          <option value="claude-sonnet-4-6">Sonnet 4.6</option>
          <option value="claude-haiku-4-5">Haiku 4.5</option>
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-[var(--muted-foreground)]">
        Effort
        <select value={effort} onChange={(e) => setEffort(e.target.value)} className={sel}>
          <option value="low">low</option>
          <option value="medium">medium</option>
          <option value="high">high</option>
          <option value="max">max</option>
        </select>
      </label>
      <button onClick={() => void save()}
        className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90">
        Enregistrer
      </button>
      <span className="text-[11px] text-[var(--muted-foreground)]">La température n&apos;est pas réglable (retirée sur Opus 4.8).</span>
    </div>
  )
}
