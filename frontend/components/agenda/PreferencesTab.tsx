"use client";

/** Préférences de planification (remplace l'onglet Tâches).
 *  Moment préféré par activité (matin / après-midi / soir) → pris en compte par
 *  le planificateur au prochain plan. Extensible (jours préférés, ordre). */

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Moon, Dumbbell, ChefHat, GraduationCap, Home, RefreshCw, CalendarClock, Trash2, CheckCircle2, AlertTriangle } from "lucide-react";
import { useIcalSource, useReplanWeeklyRevisions, useRemoveIcalSource, useSaveIcalSource, useSyncIcalSource } from "@/lib/queries/agenda";

type Moments = Record<string, string>;

const ACTIVITIES = [
  { key: "sport", label: "Sport", Icon: Dumbbell },
  { key: "etudes", label: "Études", Icon: GraduationCap },
  { key: "cuisine", label: "Batch cooking", Icon: ChefHat },
  { key: "menage", label: "Ménage", Icon: Home },
] as const;

const MOMENTS = [
  { value: "", label: "Auto (créneau libre)" },
  { value: "matin", label: "Matin" },
  { value: "aprem", label: "Après-midi" },
  { value: "soir", label: "Soir" },
];

export default function PreferencesTab() {
  const [moments, setMoments] = useState<Moments>({});
  const [loaded, setLoaded] = useState(false);
  const [icalUrl, setIcalUrl] = useState("");
  const sourceQ = useIcalSource();
  const saveSource = useSaveIcalSource();
  const removeSource = useRemoveIcalSource();
  const syncSource = useSyncIcalSource();
  const replan = useReplanWeeklyRevisions();

  useEffect(() => {
    fetch("/api/agenda/preferences")
      .then((r) => (r.ok ? r.json() : { moments: {} }))
      .then((d) => setMoments(d.moments ?? {}))
      .catch(() => setMoments({}))
      .finally(() => setLoaded(true));
  }, []);

  const update = (key: string, value: string) => {
    const next = { ...moments };
    if (value) next[key] = value;
    else delete next[key];
    setMoments(next);
    fetch("/api/agenda/preferences", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ moments: { [key]: value } }),
    })
      .then((r) => {
        if (!r.ok) throw new Error();
        toast.success("Préférence enregistrée — appliquée au prochain plan.");
      })
      .catch(() => toast.error("Échec de l'enregistrement."));
  };

  const saveCalendar = () => {
    if (!icalUrl.trim()) return;
    saveSource.mutate({ url: icalUrl.trim(), label: "7shifts" }, {
      onSuccess: () => {
        setIcalUrl("");
        toast.success("Calendrier 7shifts enregistré. Lance une synchro pour vérifier le lien.");
      },
      onError: (error) => toast.error(error instanceof Error ? error.message : "Enregistrement impossible."),
    });
  };

  const runSync = () => syncSource.mutate(undefined, {
    onSuccess: (counts) => toast.success(`${counts.created_events} shift(s) ajouté(s), ${counts.updated_events} mis à jour, ${counts.skipped_duplicates} inchangé(s).`),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Synchronisation impossible."),
  });

  const runReplan = () => replan.mutate(undefined, {
    onSuccess: (result) => toast.success(result.message),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Replanification impossible."),
  });

  const lastSync = sourceQ.data?.last_sync_at
    ? new Date(sourceQ.data.last_sync_at).toLocaleString("fr-CA", { dateStyle: "medium", timeStyle: "short" })
    : "Jamais";

  return (
    <div className="max-w-xl space-y-4">
      <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <GraduationCap className="h-4 w-4 text-[var(--muted-foreground)]" aria-hidden="true" />
          Révisions hebdomadaires
        </h2>
        <p className="mt-1 text-xs text-[var(--muted-foreground)]">
          Chaque cours reçoit une séance de 2 h. Un créneau libre chez Shopify le dimanche compte pour 1 h 30; un shift ou un cours garde toujours la priorité.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button type="button" onClick={runReplan} disabled={replan.isPending}
            className="inline-flex items-center gap-2 rounded-md bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-50">
            <RefreshCw className={`h-4 w-4 ${replan.isPending ? "animate-spin" : ""}`} aria-hidden="true" />
            {replan.isPending ? "Recalcul…" : "Recalculer cette semaine"}
          </button>
          <span className="text-xs text-[var(--muted-foreground)]">Les blocs apparaissent dans l’Agenda et s’adaptent aux shifts synchronisés.</span>
        </div>
      </section>

      <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <CalendarClock className="h-4 w-4 text-[var(--muted-foreground)]" aria-hidden="true" />
          Calendrier de travail — 7shifts
        </h2>
        <p className="mt-1 text-xs text-[var(--muted-foreground)]">
          Colle le lien Calendar sync une fois. Il est conservé sur le serveur local et resynchronisé chaque heure quand le dashboard fonctionne.
        </p>

        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <label className="sr-only" htmlFor="ical-work-url">Lien iCal 7shifts</label>
          <input id="ical-work-url" type="url" inputMode="url" autoComplete="off" value={icalUrl}
            onChange={(event) => setIcalUrl(event.target.value)}
            placeholder={sourceQ.data?.configured ? "Lien enregistré (masqué) — coller un nouveau lien pour le remplacer" : "https://…"}
            className="min-w-0 flex-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]" />
          <button type="button" onClick={saveCalendar} disabled={!icalUrl.trim() || saveSource.isPending}
            className="rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium disabled:opacity-50">
            {saveSource.isPending ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          {sourceQ.data?.configured ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--success)]/10 px-2.5 py-1 text-xs font-medium text-[var(--success)]">
              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" /> Source configurée
            </span>
          ) : (
            <span className="text-xs text-[var(--muted-foreground)]">Aucune source configurée</span>
          )}
          <span className="text-xs text-[var(--muted-foreground)]">Dernière synchro : {lastSync}</span>
          {sourceQ.data?.configured && <>
            <button type="button" onClick={runSync} disabled={syncSource.isPending}
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-3 py-1.5 text-xs font-medium disabled:opacity-50">
              <RefreshCw className={`h-3.5 w-3.5 ${syncSource.isPending ? "animate-spin" : ""}`} aria-hidden="true" />
              Synchroniser maintenant
            </button>
            <button type="button" onClick={() => removeSource.mutate(undefined, {
              onSuccess: () => toast.success("Lien de calendrier supprimé."),
              onError: () => toast.error("Suppression impossible."),
            })} disabled={removeSource.isPending}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs text-[var(--muted-foreground)] hover:text-[var(--destructive)] disabled:opacity-50">
              <Trash2 className="h-3.5 w-3.5" aria-hidden="true" /> Retirer le lien
            </button>
          </>}
        </div>
        {sourceQ.data?.last_error && (
          <p role="status" className="mt-2 flex items-start gap-1.5 text-xs text-[var(--destructive)]">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            Dernière erreur : {sourceQ.data.last_error}
          </p>
        )}
      </section>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Moon className="h-4 w-4 text-[var(--muted-foreground)]" aria-hidden="true" />
          Moment préféré par activité
        </h2>
        <p className="mt-1 text-xs text-[var(--muted-foreground)]">
          Le planificateur place ces blocs au moment choisi s'il y a un créneau libre,
          sinon il prend le premier créneau disponible.
        </p>

        <div className="mt-4 space-y-3">
          {ACTIVITIES.map(({ key, label, Icon }) => (
            <div key={key} className="flex items-center gap-3">
              <Icon className="h-4 w-4 shrink-0 text-[var(--muted-foreground)]" aria-hidden="true" />
              <span className="w-32 text-sm">{label}</span>
              <select
                value={moments[key] ?? (key === "menage" ? "aprem" : "")}
                disabled={!loaded}
                onChange={(e) => update(key, e.target.value)}
                aria-label={`Moment préféré pour ${label}`}
                className="flex-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm"
              >
                {MOMENTS.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </div>

      <p className="text-xs text-[var(--muted-foreground)]">
        Les changements s'appliquent à la prochaine génération du plan (Agenda → Planifier,
        ou la replanification hebdomadaire automatique).
      </p>
    </div>
  );
}
