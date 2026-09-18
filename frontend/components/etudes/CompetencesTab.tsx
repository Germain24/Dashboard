"use client";

/** Suivi de compétences (skill tree) : niveaux 1-5 et preuves horodatées (#352). */

import { useState } from "react";
import { toast } from "sonner";
import { Plus, Trash2, X, Check, ChevronDown, ChevronUp } from "lucide-react";
import type { Skill } from "@/lib/etudes";
import {
  useAddPreuve, useCreateSkill, useDeleteSkill, useSkills, useSkillsStats,
} from "@/lib/queries/etudes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";

const NIVEAU_MAX = 5;

const CATEGORIES = ["technique", "langue", "soft skill", "autre"];

function NiveauBar({ niveau }: { niveau: number }) {
  return (
    <div className="flex items-center gap-1" aria-label={`Niveau ${niveau} sur ${NIVEAU_MAX}`}>
      {Array.from({ length: NIVEAU_MAX }, (_, i) => (
        <span
          key={i}
          className="h-2 w-4 rounded-[2px]"
          style={{ backgroundColor: i < niveau ? "var(--ring)" : "var(--border)" }}
        />
      ))}
    </div>
  );
}

export function CompetencesTab() {
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ nom: "", categorie: "", niveau: "1" });
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [preuveDraft, setPreuveDraft] = useState<Record<number, string>>({});

  const skillsQ = useSkills();
  const statsQ = useSkillsStats();
  const skills: Skill[] = skillsQ.data ?? [];
  const status: "loading" | "error" | "ready" =
    skillsQ.isLoading || statsQ.isLoading ? "loading"
    : skillsQ.isError || statsQ.isError ? "error" : "ready";

  const createMutation = useCreateSkill();
  const deleteMutation = useDeleteSkill();
  const preuveMutation = useAddPreuve();

  const add = () => {
    if (!form.nom.trim() || !form.categorie.trim()) return;
    createMutation.mutate(
      { nom: form.nom, categorie: form.categorie, niveau: Number(form.niveau) },
      {
        onSuccess: () => {
          setForm({ nom: "", categorie: "", niveau: "1" });
          setAdding(false);
        },
        onError: () => toast.error("Impossible de créer la compétence."),
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

  const addPreuve = (id: number) => {
    const texte = (preuveDraft[id] ?? "").trim();
    if (!texte) return;
    preuveMutation.mutate(
      { id, texte },
      {
        onSuccess: () => setPreuveDraft((d) => ({ ...d, [id]: "" })),
        onError: () => toast.error("Impossible d'ajouter la preuve."),
      },
    );
  };

  if (status === "loading") return <Skeleton lines={6} />;

  if (status === "error") {
    return (
      <div className="flex flex-col items-start gap-2 py-2">
        <p className="text-sm text-[var(--muted-foreground)]">Compétences indisponibles pour le moment.</p>
        <Button variant="secondary" size="sm" onClick={() => { void skillsQ.refetch(); void statsQ.refetch(); }}>
          Réessayer
        </Button>
      </div>
    );
  }

  const stats = statsQ.data;
  const parCategorie = stats?.par_categorie ?? {};

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-[var(--muted-foreground)]">
          {stats ? (
            <>Niveau moyen {stats.global.niveau_moyen.toFixed(1)}/5 · {stats.global.nb_competences} compétence{stats.global.nb_competences > 1 ? "s" : ""} · {stats.global.nb_preuves_total} preuve{stats.global.nb_preuves_total > 1 ? "s" : ""}</>
          ) : null}
        </p>
        <Button variant="secondary" size="sm" onClick={() => setAdding((a) => !a)}>
          {adding ? <X className="h-4 w-4" aria-hidden="true" /> : <Plus className="h-4 w-4" aria-hidden="true" />}
          {adding ? "Annuler" : "Compétence"}
        </Button>
      </div>

      {adding && (
        <Card className="space-y-2 p-3">
          <Input
            placeholder="Nom de la compétence"
            value={form.nom}
            onChange={(e) => setForm((f) => ({ ...f, nom: e.target.value }))}
          />
          <div className="flex items-center gap-2">
            <Input
              list="competences-categories"
              placeholder="Catégorie (ex. technique, langue…)"
              value={form.categorie}
              onChange={(e) => setForm((f) => ({ ...f, categorie: e.target.value }))}
            />
            <datalist id="competences-categories">
              {CATEGORIES.map((c) => <option key={c} value={c} />)}
            </datalist>
            <select
              aria-label="Niveau initial"
              className="h-8 rounded-[var(--radius)] border border-[var(--border)] bg-transparent px-2 text-sm text-[var(--foreground)] focus:border-[var(--ring)] focus:outline-none"
              value={form.niveau}
              onChange={(e) => setForm((f) => ({ ...f, niveau: e.target.value }))}
            >
              {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>Niveau {n}</option>)}
            </select>
            <Button size="sm" onClick={() => void add()} disabled={!form.nom.trim() || !form.categorie.trim()}>
              Ajouter
            </Button>
          </div>
        </Card>
      )}

      {/* Regroupement par catégorie */}
      {Object.keys(parCategorie).length > 0 && (
        <div className="space-y-1.5">
          <h3 className="text-xs font-semibold text-[var(--muted-foreground)]">Par catégorie</h3>
          {Object.entries(parCategorie).map(([categorie, info]) => (
            <div key={categorie} className="flex items-center gap-2 text-sm">
              <div className="w-32 truncate" title={categorie}>{categorie}</div>
              <div className="flex-1 h-3 bg-[var(--border)] rounded overflow-hidden">
                <div
                  className="h-full bg-[var(--ring)] bar-fill"
                  style={{ width: `${(info.niveau_moyen / NIVEAU_MAX) * 100}%` }}
                />
              </div>
              <div className="w-24 text-right text-xs text-[var(--muted-foreground)] tabular-nums">
                {info.niveau_moyen.toFixed(1)}/5 · {info.nb_competences}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Liste des compétences */}
      {skills.length === 0 ? (
        <EmptyState
          title="Aucune compétence"
          description="Ajoute une compétence pour suivre ta progression au fil des preuves."
        />
      ) : (
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-[var(--muted-foreground)]">Toutes les compétences</h3>
          {skills.map((s) => {
            const isExpanded = expanded === s.id;
            const visiblePreuves = isExpanded ? s.preuves : s.preuves.slice(0, 2);
            return (
              <Card key={s.id} className="space-y-2 p-3">
                <div className="flex items-center gap-2">
                  <span className="flex-1 truncate text-sm font-medium text-[var(--foreground)]" title={s.nom}>
                    {s.nom}
                  </span>
                  <span className="shrink-0 rounded-full bg-[var(--muted)] px-2 py-0.5 text-xs text-[var(--muted-foreground)]">
                    {s.categorie}
                  </span>
                  <NiveauBar niveau={s.niveau} />
                  {confirmId === s.id ? (
                    <span className="flex shrink-0 items-center gap-1">
                      <button
                        type="button"
                        onClick={() => void remove(s.id)}
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
                      onClick={() => setConfirmId(s.id)}
                      aria-label={`Supprimer la compétence « ${s.nom} »`}
                      className="shrink-0 rounded p-0.5 text-[var(--muted-foreground)] transition-colors hover:text-[var(--destructive)]"
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                  )}
                </div>

                {s.preuves.length > 0 && (
                  <div className="space-y-1">
                    {visiblePreuves.map((p, i) => (
                      <div key={i} className="flex items-start gap-2 text-xs text-[var(--muted-foreground)]">
                        <span className="shrink-0 tabular-nums">{p.date}</span>
                        <span className="truncate">{p.texte}</span>
                      </div>
                    ))}
                    {s.preuves.length > 2 && (
                      <button
                        type="button"
                        onClick={() => setExpanded(isExpanded ? null : s.id)}
                        className="flex items-center gap-1 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                      >
                        {isExpanded ? <ChevronUp className="h-3 w-3" aria-hidden="true" /> : <ChevronDown className="h-3 w-3" aria-hidden="true" />}
                        {isExpanded ? "Réduire" : `Voir tout (${s.preuves.length})`}
                      </button>
                    )}
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <Input
                    placeholder="Ajouter une preuve (ex. « Cours X terminé »)"
                    value={preuveDraft[s.id] ?? ""}
                    onChange={(e) => setPreuveDraft((d) => ({ ...d, [s.id]: e.target.value }))}
                    className="h-8 text-xs"
                  />
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => void addPreuve(s.id)}
                    disabled={!(preuveDraft[s.id] ?? "").trim()}
                  >
                    Ajouter
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
