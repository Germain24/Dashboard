"use client";

import { useState } from "react";
import { Gamepad2, Trash2 } from "lucide-react";
import { ModuleHeader } from "@/components/layout";
import type { Game, GameGoal } from "@/lib/gaming";
import {
  useCreateGame,
  useCreateGameGoal,
  useDeleteGame,
  useDeleteGameGoal,
  useGameGoals,
  useGames,
  useUpdateGame,
  useUpdateGameGoal,
} from "@/lib/queries/gaming";
import { EmptyState } from "@/components/ui/empty-state";

const inputCls =
  "w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]";

const STATUTS: Record<Game["statut"], string> = {
  backlog: "Backlog",
  en_cours: "En cours",
  termine: "Terminé",
  abandonne: "Abandonné",
};

const GOAL_TYPES: Record<GameGoal["type"], string> = {
  objectif: "Objectif",
  build: "Build",
  filtre: "Filtre",
};

export function Gaming() {
  const gamesQ = useGames();
  const createM = useCreateGame();
  const updateM = useUpdateGame();
  const deleteM = useDeleteGame();

  const [form, setForm] = useState({ titre: "", plateforme: "PC" });
  const [openGame, setOpenGame] = useState<number | null>(null);

  if (gamesQ.isLoading) {
    return (
      <div className="p-6 space-y-4 animate-fade-in">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 rounded-xl border border-[var(--border)] bg-[var(--card)] skeleton-shimmer" />
        ))}
      </div>
    );
  }
  if (gamesQ.isError) return <div className="p-6 text-[var(--destructive)]">⚠ {(gamesQ.error).message}</div>;

  const games = gamesQ.data ?? [];

  const submit = () => {
    if (!form.titre.trim()) return;
    createM.mutate(
      { titre: form.titre.trim(), plateforme: form.plateforme.trim() || "PC" },
      { onSuccess: () => setForm({ titre: "", plateforme: "PC" }) },
    );
  };

  return (
    <div className="space-y-0 animate-fade-in">
      <ModuleHeader title="Gaming" subtitle="Carnet de bord : objectifs, builds, filtres d'items" />

      <div className="p-6 space-y-6 animate-fade-in-up">
        {/* Nouveau jeu */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
          <p className="text-sm font-semibold">Nouveau jeu</p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Titre</span>
              <input value={form.titre} onChange={(e) => setForm({ ...form, titre: e.target.value })} placeholder="Elden Ring, PoE…" className={inputCls} />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Plateforme</span>
              <input value={form.plateforme} onChange={(e) => setForm({ ...form, plateforme: e.target.value })} className={inputCls} />
            </label>
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

        {games.length === 0 ? (
          <EmptyState
            icon={<Gamepad2 className="h-6 w-6" />}
            title="Aucun jeu suivi"
            description="Ajoute tes jeux pour suivre tes objectifs, builds de personnages et filtres d'items."
          />
        ) : (
          <ul className="space-y-2">
            {games.map((g) => (
              <li key={g.id} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3 card-hover">
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setOpenGame(openGame === g.id ? null : g.id)}
                    className="font-medium hover:underline"
                  >
                    {g.titre}
                  </button>
                  <span className="rounded-md bg-[var(--muted)] px-2 py-0.5 text-xs">{g.plateforme}</span>
                  <span className="text-xs text-[var(--muted-foreground)] tabular-nums">
                    {g.heures} h{(g.nb_goals ?? 0) > 0 && ` · ${g.nb_goals} objectif${(g.nb_goals ?? 0) > 1 ? "s" : ""}`}
                  </span>
                  <select
                    value={g.statut}
                    onChange={(e) => updateM.mutate({ id: g.id, patch: { statut: e.target.value as Game["statut"] } })}
                    className="ml-auto rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
                  >
                    {Object.entries(STATUTS).map(([v, l]) => (
                      <option key={v} value={v}>{l}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => deleteM.mutate(g.id)}
                    aria-label="Supprimer le jeu"
                    className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
                {openGame === g.id && <GoalsPanel gameId={g.id} />}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function GoalsPanel({ gameId }: { gameId: number }) {
  const goalsQ = useGameGoals(gameId);
  const createM = useCreateGameGoal();
  const updateM = useUpdateGameGoal();
  const deleteM = useDeleteGameGoal();
  const [form, setForm] = useState({ titre: "", type: "objectif", contenu: "" });

  const goals = goalsQ.data ?? [];

  const submit = () => {
    if (!form.titre.trim()) return;
    createM.mutate(
      { gameId, data: { titre: form.titre.trim(), type: form.type as GameGoal["type"], contenu: form.contenu.trim() || null } },
      { onSuccess: () => setForm({ titre: "", type: "objectif", contenu: "" }) },
    );
  };

  return (
    <div className="space-y-2 border-t border-[var(--border)] pt-3">
      {goals.map((goal) => (
        <div key={goal.id} className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            checked={goal.fait}
            onChange={(e) => updateM.mutate({ id: goal.id, patch: { fait: e.target.checked } })}
            className="mt-1 accent-[var(--ring)]"
            aria-label="Fait"
          />
          <div className="flex-1">
            <span className={goal.fait ? "line-through text-[var(--muted-foreground)]" : ""}>{goal.titre}</span>
            <span className="ml-2 rounded-md bg-[var(--muted)] px-1.5 py-0.5 text-xs">{GOAL_TYPES[goal.type]}</span>
            {goal.contenu && <p className="text-xs text-[var(--muted-foreground)]">{goal.contenu}</p>}
          </div>
          <button
            type="button"
            onClick={() => deleteM.mutate(goal.id)}
            aria-label="Supprimer"
            className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"
          >
            <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>
      ))}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto_1fr_auto] sm:items-center">
        <input value={form.titre} onChange={(e) => setForm({ ...form, titre: e.target.value })} placeholder="Nouvel objectif / build…" className={inputCls} />
        <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className={inputCls}>
          {Object.entries(GOAL_TYPES).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
        <input value={form.contenu} onChange={(e) => setForm({ ...form, contenu: e.target.value })} placeholder="Détails (stats, liens…)" className={inputCls} />
        <button
          type="button"
          onClick={submit}
          disabled={!form.titre.trim() || createM.isPending}
          className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-[var(--muted)] disabled:opacity-50"
        >
          Ajouter
        </button>
      </div>
    </div>
  );
}
