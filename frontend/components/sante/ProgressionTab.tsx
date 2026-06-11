"use client";

/** Photos de progression avant/après stockées localement (#69). */

import { useEffect, useRef, useState } from "react";
import { mediaUrl, todayKey, type ProgressPhoto } from "@/lib/sante";
import { useProgressPhotos, useUploadProgressPhoto } from "@/lib/queries/sante";
import { Button } from "@/components/ui/button";

export function ProgressionTab() {
  const [beforeIdx, setBeforeIdx] = useState(0);
  const [afterIdx, setAfterIdx] = useState(0);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const photosQ = useProgressPhotos();
  const photos: ProgressPhoto[] = photosQ.data ?? [];
  const uploadMutation = useUploadProgressPhoto();
  const uploading = uploadMutation.isPending;
  const err = actionErr ?? (photosQ.isError ? ((photosQ.error as Error)?.message ?? "Erreur de chargement") : null);

  useEffect(() => {
    setBeforeIdx(0);
    setAfterIdx(Math.max(0, photos.length - 1));
  }, [photos.length]);

  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setActionErr(null);
    uploadMutation.mutate([file, todayKey()], {
      onError: (er) => setActionErr(er instanceof Error ? er.message : "Échec de l'envoi"),
      onSettled: () => {
        if (fileRef.current) fileRef.current.value = "";
      },
    });
  };

  const before = photos[beforeIdx];
  const after = photos[afterIdx];
  const deltaPoids =
    before?.poids != null && after?.poids != null
      ? Math.round((after.poids - before.poids) * 10) / 10
      : null;

  return (
    <div className="space-y-5 animate-fade-in-up">
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => fileRef.current?.click()} disabled={uploading} size="sm">
          {uploading ? "Envoi…" : "📷 Ajouter une photo (aujourd'hui)"}
        </Button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          onChange={(e) => void onPick(e)}
          className="hidden"
        />
        <span className="text-xs text-[var(--muted-foreground)]">
          {photos.length} photo{photos.length > 1 ? "s" : ""} · stockées localement
        </span>
        {err && <span className="text-xs text-[var(--destructive)]">⚠ {err}</span>}
      </div>

      {photos.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">
          Aucune photo de progression. Ajoute une première photo pour démarrer ta comparaison avant/après.
        </p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <PhotoPane
              title="Avant"
              photos={photos}
              idx={beforeIdx}
              onChange={setBeforeIdx}
              photo={before}
            />
            <PhotoPane
              title="Après"
              photos={photos}
              idx={afterIdx}
              onChange={setAfterIdx}
              photo={after}
            />
          </div>
          {deltaPoids != null && (
            <p className="text-sm text-center text-[var(--muted-foreground)]">
              Variation de poids :{" "}
              <strong className={deltaPoids <= 0 ? "text-[var(--success)]" : "text-[var(--warning)]"}>
                {deltaPoids > 0 ? "+" : ""}
                {deltaPoids} kg
              </strong>
            </p>
          )}
        </>
      )}
    </div>
  );
}

function PhotoPane({
  title,
  photos,
  idx,
  onChange,
  photo,
}: {
  title: string;
  photos: ProgressPhoto[];
  idx: number;
  onChange: (i: number) => void;
  photo?: ProgressPhoto;
}) {
  return (
    <div className="rounded-xl border border-[var(--border)] overflow-hidden bg-[var(--card)]">
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--border)]">
        <span className="text-sm font-semibold">{title}</span>
        <select
          value={idx}
          onChange={(e) => onChange(Number(e.target.value))}
          className="rounded border border-[var(--border)] bg-transparent px-2 py-1 text-xs"
        >
          {photos.map((p, i) => (
            <option key={p.date} value={i}>
              {new Date(p.date).toLocaleDateString("fr-CA")}
              {p.poids != null ? ` · ${p.poids} kg` : ""}
            </option>
          ))}
        </select>
      </div>
      {photo && (
        <img
          src={mediaUrl(photo.photo_url)}
          alt={`Progression ${title} ${photo.date}`}
          className="w-full aspect-[3/4] object-cover bg-[var(--muted)]"
        />
      )}
    </div>
  );
}
