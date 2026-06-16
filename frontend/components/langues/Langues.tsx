"use client";

import { useState } from "react";
import { Languages, Plane, Trash2 } from "lucide-react";
import type { ProjetInternational, VocabEntry } from "@/lib/langues";
import {
  useCreateProjet,
  useCreateVocab,
  useDeleteProjet,
  useDeleteVocab,
  useProjets,
  useUpdateProjet,
  useUpdateVocab,
  useVocab,
  useVocabStats,
} from "@/lib/queries/langues";
import { ModuleHeader } from "@/components/layout";
import { EmptyState } from "@/components/ui/empty-state";

const inputCls =
  "w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]";

const PROJET_TYPES: Record<ProjetInternational["type"], string> = {
  semestre: "Semestre",
  visa: "Visa",
  voyage: "Voyage",
  autre: "Autre",
};

const PROJET_STATUTS: Record<ProjetInternational["statut"], string> = {
  idee: "Idée",
  planifie: "Planifié",
  en_cours: "En cours",
  fait: "Fait",
};

type Onglet = "japonais" | "projets";

export function Langues() {
  const [onglet, setOnglet] = useState<Onglet>("japonais");

  return (
    <div className="space-y-0 animate-fade-in">
      <ModuleHeader
        title="Langues & International"
        subtitle="Japonais (vocabulaire, kanjis) & masterplan Asie"
        tabs={[
          { id: "japonais", label: "Japonais" },
          { id: "projets", label: "Projets internationaux" },
        ]}
        active={onglet}
        onChange={(id) => setOnglet(id as Onglet)}
      />

      <div className="p-6 animate-fade-in-up">{onglet === "japonais" ? <JaponaisTab /> : <ProjetsTab />}</div>
    </div>
  );
}

function JaponaisTab() {
  const [filtre, setFiltre] = useState<string | undefined>(undefined);
  const vocabQ = useVocab(filtre);
  const statsQ = useVocabStats();
  const createM = useCreateVocab();
  const updateM = useUpdateVocab();
  const deleteM = useDeleteVocab();

  const [form, setForm] = useState({ terme: "", lecture: "", traduction: "", type: "vocab", tags: "" });

  if (vocabQ.isLoading) {
    return <div className="h-20 rounded-xl border border-[var(--border)] bg-[var(--card)] skeleton-shimmer" />;
  }
  if (vocabQ.isError) return <div className="text-[var(--destructive)]">⚠ {(vocabQ.error).message}</div>;

  const entries = vocabQ.data ?? [];
  const stats = statsQ.data;

  const submit = () => {
    if (!form.terme.trim() || !form.traduction.trim()) return;
    createM.mutate(
      {
        terme: form.terme.trim(),
        lecture: form.lecture.trim() || null,
        traduction: form.traduction.trim(),
        type: form.type as VocabEntry["type"],
        tags: form.tags.trim() || null,
      },
      { onSuccess: () => setForm({ terme: "", lecture: "", traduction: "", type: form.type, tags: "" }) },
    );
  };

  return (
    <div className="space-y-6">
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:max-w-xs">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <p className="text-xs text-[var(--muted-foreground)]">Vocabulaire</p>
            <p className="mt-1 text-lg font-semibold tabular-nums">{stats.vocab.total}</p>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <p className="text-xs text-[var(--muted-foreground)]">Kanjis</p>
            <p className="mt-1 text-lg font-semibold tabular-nums">{stats.kanji.total}</p>
          </div>
        </div>
      )}

      {/* Nouvelle entrée */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
        <p className="text-sm font-semibold">Nouvelle entrée</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Terme</span>
            <input value={form.terme} onChange={(e) => setForm({ ...form, terme: e.target.value })} placeholder="水, 食べる…" className={inputCls} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Lecture</span>
            <input value={form.lecture} onChange={(e) => setForm({ ...form, lecture: e.target.value })} placeholder="みず" className={inputCls} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Traduction</span>
            <input value={form.traduction} onChange={(e) => setForm({ ...form, traduction: e.target.value })} placeholder="eau" className={inputCls} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Type</span>
            <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className={inputCls}>
              <option value="vocab">Vocabulaire</option>
              <option value="kanji">Kanji</option>
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Tags</span>
            <input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} placeholder="JLPT N5" className={inputCls} />
          </label>
        </div>
        <div className="flex justify-end">
          <button
            type="button"
            onClick={submit}
            disabled={!form.terme.trim() || !form.traduction.trim() || createM.isPending}
            className="rounded-md bg-[var(--foreground)] px-3 py-1.5 text-sm font-medium text-[var(--background)] disabled:opacity-50"
          >
            Ajouter
          </button>
        </div>
      </div>

      {/* Filtre */}
      <div className="flex gap-2">
        {[
          [undefined, "Tout"],
          ["vocab", "Vocabulaire"],
          ["kanji", "Kanjis"],
        ].map(([v, l]) => (
          <button
            key={String(v)}
            type="button"
            onClick={() => setFiltre(v)}
            aria-pressed={filtre === v}
            className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
              filtre === v ? "border-[var(--ring)] bg-[var(--muted)]" : "border-[var(--border)] hover:bg-[var(--muted)]"
            }`}
          >
            {l as string}
          </button>
        ))}
      </div>

      {entries.length === 0 ? (
        <EmptyState
          icon={<Languages className="h-6 w-6" />}
          title="Aucune entrée"
          description="Ajoute ton vocabulaire et tes kanjis pour suivre ta progression en japonais."
        />
      ) : (
        <ul className="space-y-1.5">
          {entries.map((v) => (
            <li key={v.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm card-hover">
              <span className="text-base font-medium">{v.terme}</span>
              {v.lecture && <span className="text-[var(--muted-foreground)]">{v.lecture}</span>}
              <span>{v.traduction}</span>
              <span className="rounded-md bg-[var(--muted)] px-1.5 py-0.5 text-xs">{v.type === "kanji" ? "Kanji" : "Vocab"}</span>
              {v.tags && <span className="text-xs text-[var(--muted-foreground)]">{v.tags}</span>}
              <div className="ml-auto flex items-center gap-1" role="group" aria-label="Maîtrise">
                {[0, 1, 2, 3, 4, 5].map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => updateM.mutate({ id: v.id, patch: { maitrise: n } })}
                    aria-label={`Maîtrise ${n}`}
                    className={`h-2.5 w-2.5 rounded-full transition-colors ${
                      n <= v.maitrise && v.maitrise > 0 ? "bg-[var(--ring)]" : "bg-[var(--muted)] hover:bg-[var(--border)]"
                    }`}
                  />
                ))}
              </div>
              <button
                type="button"
                onClick={() => deleteM.mutate(v.id)}
                aria-label="Supprimer"
                className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ProjetsTab() {
  const projetsQ = useProjets();
  const createM = useCreateProjet();
  const updateM = useUpdateProjet();
  const deleteM = useDeleteProjet();

  const [form, setForm] = useState({ titre: "", type: "voyage", echeance: "", budget_estime: "", notes: "" });

  if (projetsQ.isLoading) {
    return <div className="h-20 rounded-xl border border-[var(--border)] bg-[var(--card)] skeleton-shimmer" />;
  }
  if (projetsQ.isError) return <div className="text-[var(--destructive)]">⚠ {(projetsQ.error).message}</div>;

  const projets = projetsQ.data ?? [];

  const submit = () => {
    if (!form.titre.trim()) return;
    const budget = parseFloat(form.budget_estime);
    createM.mutate(
      {
        titre: form.titre.trim(),
        type: form.type as ProjetInternational["type"],
        echeance: form.echeance || null,
        budget_estime: Number.isNaN(budget) ? null : budget,
        notes: form.notes.trim() || null,
      },
      { onSuccess: () => setForm({ titre: "", type: "voyage", echeance: "", budget_estime: "", notes: "" }) },
    );
  };

  return (
    <div className="space-y-6">
      {/* Nouveau projet */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
        <p className="text-sm font-semibold">Nouveau projet</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Titre</span>
            <input value={form.titre} onChange={(e) => setForm({ ...form, titre: e.target.value })} placeholder="Semestre à Tokyo…" className={inputCls} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Type</span>
            <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className={inputCls}>
              {Object.entries(PROJET_TYPES).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Échéance</span>
            <input type="date" value={form.echeance} onChange={(e) => setForm({ ...form, echeance: e.target.value })} className={inputCls} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Budget (€)</span>
            <input type="number" min={0} value={form.budget_estime} onChange={(e) => setForm({ ...form, budget_estime: e.target.value })} className={inputCls} />
          </label>
        </div>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Notes</span>
          <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Logistique, documents, itinéraire…" className={inputCls} />
        </label>
        <div className="flex justify-end">
          <button
            type="button"
            onClick={submit}
            disabled={!form.titre.trim() || createM.isPending}
            className="rounded-md bg-[var(--foreground)] px-3 py-1.5 text-sm font-medium text-[var(--background)] disabled:opacity-50"
          >
            Ajouter
          </button>
        </div>
      </div>

      {projets.length === 0 ? (
        <EmptyState
          icon={<Plane className="h-6 w-6" />}
          title="Aucun projet"
          description="Planifie ton masterplan Asie : semestre d'études, visas, itinéraires de voyage."
        />
      ) : (
        <ul className="space-y-2">
          {projets.map((p) => (
            <li key={p.id} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-1 card-hover">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{p.titre}</span>
                <span className="rounded-md bg-[var(--muted)] px-2 py-0.5 text-xs">{PROJET_TYPES[p.type]}</span>
                {p.echeance && <span className="text-xs text-[var(--muted-foreground)] tabular-nums">Échéance {p.echeance}</span>}
                {p.budget_estime != null && (
                  <span className="text-xs text-[var(--muted-foreground)] tabular-nums">~{p.budget_estime.toFixed(0)} €</span>
                )}
                <select
                  value={p.statut}
                  onChange={(e) => updateM.mutate({ id: p.id, patch: { statut: e.target.value as ProjetInternational["statut"] } })}
                  className="ml-auto rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
                >
                  {Object.entries(PROJET_STATUTS).map(([v, l]) => (
                    <option key={v} value={v}>{l}</option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => deleteM.mutate(p.id)}
                  aria-label="Supprimer le projet"
                  className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
              {p.notes && <p className="text-sm text-[var(--muted-foreground)]">{p.notes}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
