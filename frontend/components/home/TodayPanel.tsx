"use client";

/**
 * Panneau « Aujourd'hui » — cœur du tableau de bord d'accueil.
 *
 * Répond en un coup d'œil à « qu'est-ce qui m'attend aujourd'hui ? » :
 * prochains événements + tâches urgentes (cochables sur place). Source unique
 * /agenda/today (#90). Dégradation propre : squelette au chargement, message +
 * réessai en cas d'échec backend, état vide explicite quand la journée est libre.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowRight, CalendarDays, Circle, Clock } from "lucide-react";
import { useAgendaToday, useMarkTaskDone } from "@/lib/queries/agenda";
import {
  couleurFor,
  formatHeure,
  type AgendaJour,
  type Evenement,
  type Tache,
} from "@/lib/agenda";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";

type State =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; data: AgendaJour };

function upcomingEvents(data: AgendaJour): Evenement[] {
  const now = Date.now();
  return [
    ...data.evenements,
    ...(data.seance_entrainement ? [data.seance_entrainement] : []),
  ]
    .filter((e) => new Date(e.fin ?? e.debut).getTime() >= now)
    .sort((a, b) => a.debut.localeCompare(b.debut))
    .slice(0, 5);
}

type DeadlineInfo = { label: string; tone: "destructive" | "warning" | "muted" };

function deadlineInfo(deadline: string | null): DeadlineInfo | null {
  if (!deadline) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const d = new Date(deadline + "T00:00:00");
  const diff = Math.round((d.getTime() - today.getTime()) / 86_400_000);
  if (diff < 0) return { label: "en retard", tone: "destructive" };
  if (diff === 0) return { label: "aujourd'hui", tone: "warning" };
  if (diff === 1) return { label: "demain", tone: "muted" };
  return { label: d.toLocaleDateString("fr-CA", { day: "numeric", month: "short" }), tone: "muted" };
}

export function TodayPanel() {
  const [tasks, setTasks] = useState<Tache[]>([]);

  const todayQ = useAgendaToday();
  const markDoneMutation = useMarkTaskDone();
  const state: State = todayQ.isLoading
    ? { status: "loading" }
    : todayQ.isError
      ? { status: "error" }
      : { status: "ready", data: todayQ.data as AgendaJour };

  useEffect(() => {
    if (todayQ.data) setTasks(todayQ.data.taches_urgentes);
  }, [todayQ.data]);

  // Fire-and-forget : retire la tâche immédiatement (optimiste), restaure +
  // toast si l'appel échoue. Non-async pour rester compatible avec onClick (void).
  function complete(task: Tache) {
    setTasks((prev) => prev.filter((t) => t.id !== task.id));
    markDoneMutation.mutate(task.id, {
      onError: () => {
        setTasks((prev) => [...prev, task].sort((a, b) => a.priorite - b.priorite));
        toast.error("Impossible de marquer la tâche faite. Réessaie.");
      },
    });
  }

  return (
    <section
      aria-labelledby="today-heading"
      className="rounded-xl border border-[var(--border)] bg-[var(--card)] animate-fade-in"
    >
      <div className="flex items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3 sm:px-5">
        <h2 id="today-heading" className="flex items-center gap-2 text-sm font-semibold">
          <CalendarDays className="h-4 w-4 text-[var(--muted-foreground)]" aria-hidden="true" />
          Aujourd&apos;hui
        </h2>
        <Link
          href="/agenda"
          className="text-xs text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
        >
          Agenda →
        </Link>
      </div>

      <div className="px-4 py-4 sm:px-5">
        {state.status === "loading" && <Skeleton lines={4} />}

        {state.status === "error" && (
          <div className="flex flex-col items-start gap-2 py-2">
            <p className="text-sm text-[var(--muted-foreground)]">
              Agenda indisponible pour le moment.
            </p>
            <button
              type="button"
              onClick={() => void todayQ.refetch()}
              className="rounded-md border border-[var(--border)] px-2.5 py-1 text-xs font-medium transition-colors hover:bg-[var(--muted)]"
            >
              Réessayer
            </button>
          </div>
        )}

        {state.status === "ready" && (
          <Ready data={state.data} tasks={tasks} onComplete={complete} />
        )}
      </div>
    </section>
  );
}

function Ready({
  data,
  tasks,
  onComplete,
}: {
  data: AgendaJour;
  tasks: Tache[];
  onComplete: (t: Tache) => void;
}) {
  const events = upcomingEvents(data);
  const slot = data.slots_libres[0];

  if (events.length === 0 && tasks.length === 0) {
    return (
      <EmptyState
        icon={<CalendarDays className="h-6 w-6" aria-hidden="true" />}
        title="Rien de prévu aujourd'hui"
        description="Aucun événement ni tâche urgente. Profite du calme, ou planifie une session de travail."
        action={
          <Link
            href="/agenda"
            className="inline-flex items-center gap-1 rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90"
          >
            Ouvrir l&apos;agenda
            <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        }
        className="border-0 py-8"
      />
    );
  }

  return (
    <div className="space-y-4">
      {events.length > 0 && (
        <ul className="space-y-2.5">
          {events.map((e, i) => (
            <li key={e.id ?? `${e.debut}-${i}`} className="flex items-baseline gap-3 text-sm">
              <span
                className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: couleurFor(e) }}
                aria-hidden="true"
              />
              <span className="w-12 shrink-0 tabular-nums text-[var(--muted-foreground)]">
                {formatHeure(e.debut)}
              </span>
              <span className="min-w-0 flex-1 truncate text-[var(--foreground)]">{e.titre}</span>
              {e.lieu && (
                <span className="hidden shrink-0 truncate text-xs text-[var(--muted-foreground)] sm:block">
                  {e.lieu}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {tasks.length > 0 && (
        <div className={events.length > 0 ? "border-t border-[var(--border)] pt-4" : ""}>
          <h3 className="mb-2 text-xs font-medium text-[var(--muted-foreground)]">
            À faire ({tasks.length})
          </h3>
          <ul className="space-y-1">
            {tasks.map((t) => (
              <TaskRow key={t.id} task={t} onComplete={onComplete} />
            ))}
          </ul>
        </div>
      )}

      {slot && events.length > 0 && (
        <p className="flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
          <Clock className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          Créneau libre : {formatHeure(slot.debut)} – {formatHeure(slot.fin)}
          <span className="tabular-nums">· {Math.round(slot.duree_min / 60 * 10) / 10} h</span>
        </p>
      )}
    </div>
  );
}

function TaskRow({ task, onComplete }: { task: Tache; onComplete: (t: Tache) => void }) {
  const info = deadlineInfo(task.deadline);
  const toneClass =
    info?.tone === "destructive"
      ? "text-[var(--destructive)]"
      : info?.tone === "warning"
        ? "text-[var(--warning)]"
        : "text-[var(--muted-foreground)]";

  return (
    <li className="group flex items-center gap-2.5 rounded-md px-1 py-1.5 transition-colors hover:bg-[var(--muted)]">
      <button
        type="button"
        onClick={() => onComplete(task)}
        aria-label={`Marquer « ${task.titre} » comme fait`}
        className="shrink-0 rounded-full text-[var(--muted-foreground)] transition-colors hover:text-[var(--success)]"
      >
        <Circle className="h-4 w-4" aria-hidden="true" />
      </button>
      <span className="min-w-0 flex-1 truncate text-sm text-[var(--foreground)]">{task.titre}</span>
      {info && (
        <span className={`shrink-0 text-xs font-medium ${toneClass}`}>{info.label}</span>
      )}
    </li>
  );
}
