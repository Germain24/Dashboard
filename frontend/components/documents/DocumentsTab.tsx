'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Plus, FileText, Pencil, Trash2, X, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { type DocType, type Document, ALL_TYPES, TYPE_LABELS } from '@/lib/documents'
import { useAddDocument, useDeleteDocument, useDocuments, useUpdateDocument } from '@/lib/queries/documents'
import { Skeleton } from '@/components/ui/skeleton'

const EXPIRY_CONFIG = {
  ok:       { label: 'Valide',   color: 'text-green-500', icon: CheckCircle2 },
  warning:  { label: 'Expire bientôt', color: 'text-amber-500', icon: AlertTriangle },
  expired:  { label: 'Expiré',  color: 'text-red-500',   icon: AlertTriangle },
  no_date:  { label: '—',       color: 'text-[var(--muted-foreground)]', icon: FileText },
}

const FILTER_ALL = '__all__' as const

function AddModal({ onClose }: { onClose: () => void }) {
  const [titre, setTitre] = useState('')
  const [type, setType] = useState<DocType>('autre')
  const [organisme, setOrganisme] = useState('')
  const [dateExpiration, setDateExpiration] = useState('')
  const [dateEmission, setDateEmission] = useState('')
  const [notes, setNotes] = useState('')
  const add = useAddDocument()

  const submit = () => {
    if (!titre.trim()) return
    add.mutate(
      {
        titre: titre.trim(),
        type,
        organisme: organisme.trim(),
        notes: notes.trim(),
        date_expiration: dateExpiration || null,
        date_emission: dateEmission || null,
      } as any,
      {
        onSuccess: () => { toast.success('Document ajouté'); onClose() },
        onError: () => toast.error('Erreur ajout'),
      }
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-6 w-full max-w-md shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-base">Ajouter un document</h2>
          <button onClick={onClose}><X size={18} /></button>
        </div>
        <div className="space-y-3">
          <input
            className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-sm"
            placeholder="Titre du document *"
            value={titre}
            onChange={e => setTitre(e.target.value)}
            autoFocus
          />
          <select
            className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-sm"
            value={type}
            onChange={e => setType(e.target.value as DocType)}
          >
            {ALL_TYPES.map(t => (
              <option key={t} value={t}>{TYPE_LABELS[t]}</option>
            ))}
          </select>
          <input
            className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-sm"
            placeholder="Organisme (ex: Mairie, Banque…)"
            value={organisme}
            onChange={e => setOrganisme(e.target.value)}
          />
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs text-[var(--muted-foreground)] block mb-1">Émission</label>
              <input
                type="date"
                className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-sm"
                value={dateEmission}
                onChange={e => setDateEmission(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-[var(--muted-foreground)] block mb-1">Expiration</label>
              <input
                type="date"
                className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-sm"
                value={dateExpiration}
                onChange={e => setDateExpiration(e.target.value)}
              />
            </div>
          </div>
          <textarea
            className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-sm resize-none"
            placeholder="Notes (optionnel)"
            rows={2}
            value={notes}
            onChange={e => setNotes(e.target.value)}
          />
        </div>
        <div className="flex gap-2 mt-4">
          <button
            onClick={submit}
            disabled={!titre.trim() || add.isPending}
            className="flex-1 py-2 rounded-lg bg-[var(--primary)] text-[var(--primary-foreground)] text-sm font-medium disabled:opacity-40"
          >
            {add.isPending ? 'Ajout…' : 'Ajouter'}
          </button>
          <button onClick={onClose} className="flex-1 py-2 rounded-lg border border-[var(--border)] text-sm">
            Annuler
          </button>
        </div>
      </div>
    </div>
  )
}

function DocCard({ doc }: { doc: Document }) {
  const update = useUpdateDocument()
  const del = useDeleteDocument()
  const [editing, setEditing] = useState(false)
  const [titre, setTitre] = useState(doc.titre)

  const expiry = EXPIRY_CONFIG[doc.statut_expiration]
  const ExpiryIcon = expiry.icon

  const save = () => {
    if (!titre.trim()) return
    update.mutate(
      { id: doc.id, patch: { titre: titre.trim() } },
      {
        onSuccess: () => setEditing(false),
        onError: () => toast.error('Erreur modification'),
      }
    )
  }

  return (
    <div className="flex items-start gap-3 p-3 rounded-xl border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--accent)] transition-colors group">
      <div className="mt-0.5 p-1.5 rounded-lg bg-[var(--accent)]">
        <FileText size={14} className="text-[var(--muted-foreground)]" />
      </div>
      <div className="flex-1 min-w-0">
        {editing ? (
          <input
            autoFocus
            className="w-full px-2 py-0.5 rounded border border-[var(--border)] bg-[var(--background)] text-sm font-medium"
            value={titre}
            onChange={e => setTitre(e.target.value)}
            onBlur={save}
            onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setEditing(false) }}
          />
        ) : (
          <p className="text-sm font-medium truncate">{doc.titre}</p>
        )}
        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
          <span className="text-xs text-[var(--muted-foreground)]">{TYPE_LABELS[doc.type as DocType]}</span>
          {doc.organisme && (
            <span className="text-xs text-[var(--muted-foreground)]">· {doc.organisme}</span>
          )}
          {doc.date_expiration && (
            <span className={`flex items-center gap-1 text-xs ${expiry.color}`}>
              <ExpiryIcon size={11} />
              {new Date(doc.date_expiration).toLocaleDateString('fr-FR')}
            </span>
          )}
        </div>
      </div>
      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={() => setEditing(true)}
          className="p-1.5 rounded-lg hover:bg-[var(--accent)] text-[var(--muted-foreground)]"
        >
          <Pencil size={13} />
        </button>
        <button
          onClick={() => del.mutate(doc.id, { onSuccess: () => toast.success('Supprimé'), onError: () => toast.error('Erreur') })}
          className="p-1.5 rounded-lg hover:bg-red-500/10 text-red-500"
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  )
}

export default function DocumentsTab() {
  const [typeFilter, setTypeFilter] = useState<DocType | typeof FILTER_ALL>(FILTER_ALL)
  const [showAdd, setShowAdd] = useState(false)
  const { data: docs, isLoading } = useDocuments(
    typeFilter !== FILTER_ALL ? { type: typeFilter } : undefined
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setTypeFilter(FILTER_ALL)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              typeFilter === FILTER_ALL
                ? 'bg-[var(--primary)] text-[var(--primary-foreground)]'
                : 'bg-[var(--accent)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
            }`}
          >
            Tous
          </button>
          {ALL_TYPES.map(t => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                typeFilter === t
                  ? 'bg-[var(--primary)] text-[var(--primary-foreground)]'
                  : 'bg-[var(--accent)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
              }`}
            >
              {TYPE_LABELS[t]}
            </button>
          ))}
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--primary)] text-[var(--primary-foreground)] text-xs font-medium"
        >
          <Plus size={14} /> Ajouter
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
      ) : !docs?.length ? (
        <div className="text-center py-12 text-[var(--muted-foreground)]">
          <FileText size={32} className="mx-auto mb-2 opacity-30" />
          <p className="text-sm">Aucun document enregistré</p>
        </div>
      ) : (
        <div className="space-y-2">
          {docs.map(doc => <DocCard key={doc.id} doc={doc} />)}
        </div>
      )}

      {showAdd && <AddModal onClose={() => setShowAdd(false)} />}
    </div>
  )
}
