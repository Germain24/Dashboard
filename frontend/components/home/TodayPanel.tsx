"use client";

/**
 * Panneau « Aujourd'hui » — cœur du tableau de bord d'accueil.
 *
 * Répond en un coup d'œil à « qu'est-ce qui m'attend aujourd'hui ? » :
 * prochains événements + tâches urgentes (cochables sur place). Source unique
 * /agenda/today (#90). Dégradation propre : squelette au chargement, message +
 * réessai en cas d'échec backend, état vide explicite quand la journée est libre.
 */

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowRight, CalendarDays, Circle, Clock } from "lucide-react";
import { useAgendaToday, useMarkTaskDone } from "@/lib/queries/agenda";
import { couleurFor, formatHeure, type AgendaJour, type Evenement, type Tache } from "@/lib/agenda";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";

type State = { status: "loading" } | { status: "error" } | { status: "ready"; data: AgendaJour };

/** Toute la journée planifiée : événements prévus + blocs générés par le
 *  planificateur (sport, batch cooking, révision, repas…) + séance d'entraînement.
 *  Triés par heure ; les blocs passés sont gardés (affichés estompés).
 *
 *  Une séance planifiée mais pas encore loggée (`fin` null) est un bloc
 *  flexible « horaire libre » sans heure réelle (cf. entrainement_bridge.py) —
 *  on ne l'affiche pas dans la timeline, sinon elle apparaît à "00 h 00"
 *  (même garde que JourTab.tsx). */
function dayEvents(data: AgendaJour): Evenement[] {
  return [
    ...data.evenements,
    ...(data.seance_entrainement?.fin ? [data.seance_entrainement] : []),
  ].sort((a, b) => a.debut.localeCompare(b.debut));
}

function eventBlockHeight(event: Evenement): number {
  const durationMin = event.fin
    ? Math.max(30, (new Date(event.fin).getTime() - new Date(event.debut).getTime()) / 60_000)
    : 60;
  return Math.max(48, Math.min(180, (durationMin / 60) * 20));
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
  return {
    label: d.toLocaleDateString("fr-CA", { day: "numeric", month: "short" }),
    tone: "muted",
  };
}

export function TodayPanel() {
  const [completedTaskIds, setCompletedTaskIds] = useState<number[]>([]);

  const todayQ = useAgendaToday();
  const markDoneMutation = useMarkTaskDone();
  // « ready » seulement quand data existe : isLoading peut être faux sans
  // données (requête en pause / premier rendu), ce qui crashait Ready.
  const state: State = todayQ.data
    ? { status: "ready", data: todayQ.data }
    : todayQ.isError
      ? { status: "error" }
      : { status: "loading" };

  const tasks =
    todayQ.data?.taches_urgentes.filter((task) => !completedTaskIds.includes(task.id)) ?? [];

  // Optimiste avec undo : la tâche disparaît immédiatement, un toast "Annuler"
  // permet de revenir en arrière. Double-clic protégé par le guard isPending.
  function complete(task: Tache) {
    if (markDoneMutation.isPending) return;
    setCompletedTaskIds((previous) =>
      previous.includes(task.id) ? previous : [...previous, task.id],
    );
    const toastId = toast("Tâche complétée", {
      description: task.titre,
      action: {
        label: "Annuler",
        onClick: () => {
          setCompletedTaskIds((previous) => previous.filter((id) => id !== task.id));
          toast.dismiss(toastId);
        },
      },
    });
    markDoneMutation.mutate(task.id, {
      onError: () => {
        setCompletedTaskIds((previous) => previous.filter((id) => id !== task.id));
        toast.dismiss(toastId);
        toast.error("Impossible de marquer la tâche faite. Réessaie.");
      },
      onSuccess: () => {
        toast.dismiss(toastId);
        toast.success("Tâche complétée");
      },
    });
  }

  return (
    <section
      aria-labelledby="today-heading"
      className="today-card animate-fade-in rounded-xl border"
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
          Plan complet →
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
  const events = dayEvents(data);
  const [now] = useState(() => Date.now());
  const slot = data.slots_libres[0];
  const upcomingEvents = events.filter(
    (event) => new Date(event.fin ?? event.debut).getTime() >= now,
  );
  const visibleEvents =
    upcomingEvents.length > 0
      ? upcomingEvents.slice(0, 5)
      : events.slice(Math.max(0, events.length - 3));

  if (events.length === 0 && tasks.length === 0) {
    return (
      <div>
        <EmptyState
          icon={<CalendarDays className="h-6 w-6" aria-hidden="true" />}
          title="Rien de prévu aujourd'hui"
          description="Aucun événement ni tâche urgente. Profite du calme ou choisis le prochain bloc à avancer."
          action={
            <Link
              href="/agenda"
              className="inline-flex min-h-11 items-center gap-1 rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90"
            >
              Organiser ma journée
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
          }
          className="border-0 py-6"
        />
        {slot && slot.duree_min >= 45 && <FreeSlotAction slot={slot} />}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {visibleEvents.length > 0 && (
        <ul className="today-events">
          {visibleEvents.map((e, i) => {
            const past = new Date(e.fin ?? e.debut).getTime() < now;
            return (
              <li
                key={e.id ?? `${e.debut}-${i}`}
                className={`today-event ${past ? "is-past" : ""}`}
                style={{ minHeight: eventBlockHeight(e), borderLeftColor: couleurFor(e) }}
              >
                <span
                  className="today-event-dot"
                  style={{ backgroundColor: couleurFor(e) }}
                  title={e.categorie ?? "Événement"}
                  role="presentation"
                />
                <span className="today-event-time">
                  {formatHeure(e.debut)}{e.fin ? `–${formatHeure(e.fin)}` : ""}
                </span>
                <span className="today-event-title">{e.titre}</span>
                {i === 0 && !past ? (
                  <span className="today-event-place" aria-label="Prochain bloc">
                    À suivre
                  </span>
                ) : e.lieu ? (
                  <span className="today-event-place">{e.lieu}</span>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      {events.length > visibleEvents.length && (
        <Link href="/agenda" className="today-more-events">
          {events.length - visibleEvents.length} autres blocs dans l&apos;agenda
          <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      )}

      {tasks.length > 0 && (
        <div className={events.length > 0 ? "border-t border-[var(--border)] pt-4" : ""}>
          <h3 className="mb-2 text-xs font-medium text-[var(--muted-foreground)]">
            À faire ({tasks.length})
          </h3>
          <ul className="space-y-1">
            {tasks.slice(0, 4).map((t) => (
              <TaskRow key={t.id} task={t} onComplete={onComplete} />
            ))}
          </ul>
          {tasks.length > 4 && (
            <Link
              href="/agenda"
              className="mt-2 inline-flex min-h-9 items-center gap-1 text-xs font-medium text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
            >
              Voir les {tasks.length - 4} autres tâches
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
          )}
        </div>
      )}

      {slot && slot.duree_min >= 45 && <FreeSlotAction slot={slot} />}
    </div>
  );
}

function FreeSlotAction({ slot }: { slot: AgendaJour["slots_libres"][number] }) {
  const duration = Math.round((slot.duree_min / 60) * 10) / 10;
  return (
    <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[var(--border)] bg-[var(--muted)] px-3 py-2.5">
      <p className="flex min-w-0 items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
        <Clock className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <span>
          Créneau libre : {formatHeure(slot.debut)}–{formatHeure(slot.fin)} · {duration} h
        </span>
      </p>
      <Link
        href="/agenda"
        className="inline-flex min-h-11 shrink-0 items-center gap-1 rounded-md px-2 text-xs font-semibold text-[var(--foreground)] transition-colors hover:bg-[var(--card)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
      >
        Planifier un bloc
        <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
      </Link>
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
        className="grid h-11 w-11 shrink-0 place-items-center rounded-full text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)] hover:text-[var(--success)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
      >
        <Circle className="h-4 w-4" aria-hidden="true" />
      </button>
      <span className="min-w-0 flex-1 truncate text-sm text-[var(--foreground)]">{task.titre}</span>
      {info && <span className={`shrink-0 text-xs font-medium ${toneClass}`}>{info.label}</span>}
    </li>
  );
}
