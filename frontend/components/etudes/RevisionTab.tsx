"use client";

/** Révision espacée (spaced repetition, SM-2) sur fiches (#99). */

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Clock, Trash2, Check, X, Sparkles } from "lucide-react";
import type { Cours, RevisionCard } from "@/lib/etudes";
import {
  useAddRevisionCard, useCours, useDeleteRevisionCard,
  useReviewRevisionCard, useRevisionCards,
} from "@/lib/queries/etudes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";

// Notation SM-2 mappée sur l'échelle sémantique du design system (thème-aware).
const GRADES = [
  { q: 1, label: "Raté", tone: "destructive" },
  { q: 3, label: "Difficile", tone: "warning" },
  { q: 4, label: "Bien", tone: "success" },
  { q: 5, label: "Facile", tone: "info" },
] as const;

const GRADE_CLASS: Record<(typeof GRADES)[number]["tone"], string> = {
  destructive: "bg-[var(--destructive-muted)] text-[var(--destructive-foreground)] hover:border-[var(--destructive)]",
  warning: "bg-[var(--warning-muted)] text-[var(--warning-foreground)] hover:border-[var(--warning)]",
  success: "bg-[var(--success-muted)] text-[var(--success-foreground)] hover:border-[var(--success)]",
  info: "bg-[var(--info-muted)] text-[var(--info-foreground)] hover:border-[var(--info)]",
};

export function RevisionTab() {
  const [idx, setIdx] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ recto: "", verso: "", cours_id: "" });
  const [confirmId, setConfirmId] = useState<number | null>(null);
  // Deck figé localement : on n'avance dans la pile qu'à la fin (invalidation).
  const [deck, setDeck] = useState<RevisionCard[] | null>(null);

  const allQ = useRevisionCards(false);
  const dueQ = useRevisionCards(true);
  const coursQ = useCours();
  const cards: RevisionCard[] = allQ.data ?? [];
  const cours: Cours[] = coursQ.data ?? [];
  const status: "loading" | "error" | "ready" =
    allQ.isLoading || dueQ.isLoading || coursQ.isLoading ? "loading"
    : allQ.isError || dueQ.isError || coursQ.isError ? "error" : "ready";

  useEffect(() => {
    if (dueQ.data) {
      setDeck(dueQ.data);
      setIdx(0);
      setRevealed(false);
      setConfirmId(null);
    }
  }, [dueQ.data]);

  const due = deck ?? [];
  const reviewMutation = useReviewRevisionCard();
  const addMutation = useAddRevisionCard();
  const deleteMutation = useDeleteRevisionCard();

  const current = due[idx];

  const grade = (q: number) => {
    if (!current) return;
    const last = idx + 1 >= due.length;
    reviewMutation.mutate({ id: current.id, quality: q }, {
      onSuccess: () => {
        // Avance localement ; la dernière carte laisse l'invalidation recharger le deck.
        if (!last) { setIdx(idx + 1); setRevealed(false); }
      },
      onError: () => toast.error("Échec de l'enregistrement de la révision."),
    });
  };

  const add = () => {
    if (!form.recto.trim() || !form.verso.trim()) return;
    addMutation.mutate(
      { recto: form.recto, verso: form.verso, coursId: form.cours_id ? Number(form.cours_id) : undefined },
      {
        onSuccess: () => {
          setForm({ recto: "", verso: "", cours_id: "" });
          setAdding(false);
        },
        onError: () => toast.error("Impossible de créer la fiche."),
      },
    );
  };

  const remove = (id: number) => {
    deleteMutation.mutate(id, {
      onError: () => {
        setConfirmId(null);
        toast.error("Suppression impossible.");
      },
    });
  };

  if (status === "loading") return <Skeleton lines={6} />;

  if (status === "error") {
    return (
      <div className="flex flex-col items-start gap-2 py-2">
        <p className="text-sm text-[var(--muted-foreground)]">Fiches indisponibles pour le moment.</p>
        <Button variant="secondary" size="sm" onClick={() => { void allQ.refetch(); void dueQ.refetch(); void coursQ.refetch(); }}>Réessayer</Button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-[var(--muted-foreground)]">
          {due.length} à réviser aujourd&apos;hui · {cards.length} fiche{cards.length > 1 ? "s" : ""}
        </p>
        <Button variant="secondary" size="sm" onClick={() => setAdding((a) => !a)}>
          {adding ? <X className="h-4 w-4" aria-hidden="true" /> : <Plus className="h-4 w-4" aria-hidden="true" />}
          {adding ? "Annuler" : "Fiche"}
        </Button>
      </div>

      {adding && (
        <Card className="space-y-2 p-3">
          <Input
            placeholder="Recto (question)"
            value={form.recto}
            onChange={(e) => setForm((f) => ({ ...f, recto: e.target.value }))}
          />
          <Textarea
            placeholder="Verso (réponse)"
            rows={2}
            value={form.verso}
            onChange={(e) => setForm((f) => ({ ...f, verso: e.target.value }))}
          />
          <div className="flex items-center gap-2">
            <select
              aria-label="Cours associé"
              className="h-8 flex-1 rounded-[var(--radius)] border border-[var(--border)] bg-transparent px-2 text-sm text-[var(--foreground)] focus:border-[var(--ring)] focus:outline-none"
              value={form.cours_id}
              onChange={(e) => setForm((f) => ({ ...f, cours_id: e.target.value }))}
            >
              <option value="">— cours (optionnel) —</option>
              {cours.map((c) => <option key={c.id} value={c.id}>{c.code}</option>)}
            </select>
            <Button size="sm" onClick={() => void add()} disabled={!form.recto.trim() || !form.verso.trim()}>
              Ajouter la fiche
            </Button>
          </div>
        </Card>
      )}

      {/* Mode révision */}
      {current ? (
        <Card className="space-y-4 p-6 text-center">
          <p className="text-xs text-[var(--muted-foreground)]">Fiche {idx + 1} / {due.length}</p>
          <p className="min-h-[2rem] text-lg font-medium text-[var(--foreground)]">{current.recto}</p>
          {revealed ? (
            <>
              <p className="border-t border-[var(--border)] pt-3 text-[var(--muted-foreground)]">{current.verso}</p>
              <div className="flex flex-wrap justify-center gap-2">
                {GRADES.map(({ q, label, tone }) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => void grade(q)}
                    className={`rounded-[var(--radius)] border border-transparent px-3 py-1.5 text-sm font-medium transition-colors ${GRADE_CLASS[tone]}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </>
          ) : (
            <Button variant="secondary" onClick={() => setRevealed(true)}>Révéler la réponse</Button>
          )}
        </Card>
      ) : cards.length === 0 ? (
        <EmptyState
          title="Aucune fiche"
          description="Crée une fiche recto/verso pour commencer à réviser en répétition espacée."
        />
      ) : (
        <Card className="flex flex-col items-center gap-2 p-6 text-center">
          <Sparkles className="h-6 w-6 text-[var(--success)]" aria-hidden="true" />
          <p className="text-sm text-[var(--muted-foreground)]">Rien à réviser aujourd&apos;hui. Reviens demain.</p>
        </Card>
      )}

      {/* Liste des fiches */}
      {cards.length > 0 && (
        <div className="space-y-1">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
            Toutes les fiches
          </h3>
          {cards.map((c) => (
            <div
              key={c.id}
              className="flex items-center gap-2 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--card)] px-2 py-1.5 text-xs"
            >
              <span className="flex-1 truncate text-[var(--foreground)]" title={c.recto}>{c.recto}</span>
              <span className="flex shrink-0 items-center gap-1 tabular-nums text-[var(--muted-foreground)]">
                <Clock className="h-3 w-3" aria-hidden="true" />
                {c.due}
              </span>
              {confirmId === c.id ? (
                <span className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    onClick={() => void remove(c.id)}
                    aria-label="Confirmer la suppression"
                    className="rounded p-0.5 text-[var(--destructive)] transition-colors hover:bg-[var(--destructive-muted)]"
                  >
                    <Check className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmId(null)}
                    aria-label="Annuler la suppression"
                    className="rounded p-0.5 text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)]"
                  >
                    <X className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => setConfirmId(c.id)}
                  aria-label={`Supprimer la fiche « ${c.recto} »`}
                  className="shrink-0 rounded p-0.5 text-[var(--muted-foreground)] transition-colors hover:text-[var(--destructive)]"
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
