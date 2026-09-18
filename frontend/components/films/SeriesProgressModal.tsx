"use client";

import { useState } from "react";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { WatchItem } from "@/lib/films";
import { useSerieProgress, useUpdateProgress } from "@/lib/queries/films";
import { Dialog, DialogBody, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export default function SeriesProgressModal({
  serie,
  onClose,
}: {
  serie: WatchItem;
  onClose: () => void;
}) {
  const progressQ = useSerieProgress(serie.id);
  const updateMutation = useUpdateProgress();

  const prog = progressQ.data && "saison" in progressQ.data ? progressQ.data : null;

  const [saison, setSaison] = useState(prog?.saison ?? 1);
  const [episode, setEpisode] = useState(prog?.episode_courant ?? 0);

  // Sync after load
  if (prog && saison === 1 && episode === 0 && (prog.saison !== 1 || prog.episode_courant !== 0)) {
    setSaison(prog.saison);
    setEpisode(prog.episode_courant);
  }

  const save = () => {
    updateMutation.mutate([serie.id, { saison, episode_courant: episode }], {
      onSuccess: () => {
        toast.success("Progression sauvegardée.");
        onClose();
      },
      onError: () => toast.error("Erreur lors de la sauvegarde."),
    });
  };

  const maxSaisons = serie.nb_saisons ?? 99;

  return (
    <Dialog
      open
      onClose={onClose}
      className="max-w-sm rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-xl"
    >
      <DialogHeader onClose={onClose} className="pb-0">
        <DialogTitle className="text-sm">Progression — {serie.titre}</DialogTitle>
      </DialogHeader>
      <DialogBody className="pb-5">
        {progressQ.isLoading ? (
          <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>
        ) : (
          <div className="space-y-4">
            <div>
              <p
                id="series-season-label"
                className="text-xs font-medium text-[var(--muted-foreground)] block mb-1"
              >
                Saison
              </p>
              <div
                className="flex items-center gap-3"
                role="group"
                aria-labelledby="series-season-label"
              >
                <button
                  onClick={() => setSaison((s) => Math.max(1, s - 1))}
                  disabled={saison <= 1}
                  aria-label="Saison précédente"
                  className="p-1 rounded hover:bg-[var(--muted)] disabled:opacity-40"
                >
                  <ChevronLeft size={16} />
                </button>
                <span className="text-lg font-bold w-8 text-center" aria-live="polite">
                  {saison}
                </span>
                <button
                  onClick={() => setSaison((s) => Math.min(maxSaisons, s + 1))}
                  disabled={saison >= maxSaisons}
                  aria-label="Saison suivante"
                  className="p-1 rounded hover:bg-[var(--muted)] disabled:opacity-40"
                >
                  <ChevronRight size={16} />
                </button>
                {serie.nb_saisons && (
                  <span className="text-xs text-[var(--muted-foreground)]">
                    / {serie.nb_saisons}
                  </span>
                )}
              </div>
            </div>

            <div>
              <p
                id="series-episode-label"
                className="text-xs font-medium text-[var(--muted-foreground)] block mb-1"
              >
                Épisode
              </p>
              <div
                className="flex items-center gap-3"
                role="group"
                aria-labelledby="series-episode-label"
              >
                <button
                  onClick={() => setEpisode((e) => Math.max(0, e - 1))}
                  disabled={episode <= 0}
                  aria-label="Épisode précédent"
                  className="p-1 rounded hover:bg-[var(--muted)] disabled:opacity-40"
                >
                  <ChevronLeft size={16} />
                </button>
                <span className="text-lg font-bold w-8 text-center" aria-live="polite">
                  {episode}
                </span>
                <button
                  onClick={() => setEpisode((e) => e + 1)}
                  aria-label="Épisode suivant"
                  className="p-1 rounded hover:bg-[var(--muted)]"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>

            <button
              onClick={save}
              disabled={updateMutation.isPending}
              className="w-full py-2 bg-[var(--ring)] text-white rounded-lg text-sm font-medium disabled:opacity-50"
            >
              {updateMutation.isPending ? "Sauvegarde…" : "Sauvegarder"}
            </button>
          </div>
        )}
      </DialogBody>
    </Dialog>
  );
}
