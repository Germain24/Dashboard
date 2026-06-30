"use client";

import { useMemo, useRef, useState } from "react";
import type { Vetement } from "@/lib/garderobe";
import { emojiForCategorie, assetUrl, mediaUrl } from "@/lib/garderobe";
import { useObjectif, useUpdateVetement, useUploadVetementPhoto } from "@/lib/queries/garderobe";
import { dominantColorFromFile } from "@/lib/dominantColor";

export function InventaireTab({ wardrobe, onReload }: { wardrobe: Vetement[]; onReload?: () => void }) {
  const [cat, setCat] = useState<string>("");
  const [style, setStyle] = useState<string>("");
  const [etat, setEtat] = useState<string>("");
  const [couleur, setCouleur] = useState<string>("");
  const [saison, setSaison] = useState<string>("");

  const objectifQ = useObjectif();
  const typeNames = useMemo(
    () => (objectifQ.data?.types ?? []).map((t) => t.nom),
    [objectifQ.data],
  );

  const cats = useMemo(
    () => Array.from(new Set(wardrobe.map((v) => v.categorie).filter(Boolean))).sort(),
    [wardrobe],
  );
  const styles = useMemo(() => {
    const s = new Set<string>();
    for (const v of wardrobe) for (const st of v.style || []) s.add(st);
    return Array.from(s).sort();
  }, [wardrobe]);
  const couleurs = useMemo(
    () => Array.from(new Set(wardrobe.map((v) => v.couleur).filter(Boolean) as string[])).sort(),
    [wardrobe],
  );

  const filtered = useMemo(() => {
    return wardrobe.filter((v) => {
      if (cat && v.categorie !== cat) return false;
      if (style && !(v.style || []).includes(style)) return false;
      if (couleur && v.couleur !== couleur) return false;
      if (saison && v.saison !== "toutes" && v.saison !== saison) return false;
      if (etat === "propre" && !(v.proprete_pct >= 70 && !v.needs_wash)) return false;
      if (etat === "mi-sale" && !(v.proprete_pct >= 30 && v.proprete_pct < 70)) return false;
      if (etat === "a-laver" && !v.needs_wash) return false;
      if (etat === "hs" && !v.is_worn_out) return false;
      return true;
    });
  }, [wardrobe, cat, style, etat, couleur, saison]);

  return (
    <div className="space-y-4 animate-fade-in-up">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
        <select value={cat} onChange={(e) => setCat(e.target.value)} className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm">
          <option value="">Toutes catégories</option>
          {cats.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={style} onChange={(e) => setStyle(e.target.value)} className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm">
          <option value="">Tous styles</option>
          {styles.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={couleur} onChange={(e) => setCouleur(e.target.value)} className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm">
          <option value="">Toutes couleurs</option>
          {couleurs.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={saison} onChange={(e) => setSaison(e.target.value)} className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm">
          <option value="">Toutes saisons</option>
          <option value="hiver">❄️ Hiver</option>
          <option value="mi-saison">🍂 Mi-saison</option>
          <option value="été">☀️ Été</option>
        </select>
        <select value={etat} onChange={(e) => setEtat(e.target.value)} className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm">
          <option value="">Tous états</option>
          <option value="propre">✓ Propres</option>
          <option value="mi-sale">⚠ Mi-sales</option>
          <option value="a-laver">🧺 À laver</option>
          <option value="hs">💀 HS</option>
        </select>
      </div>
      {filtered.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">Aucun vêtement ne correspond.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 stagger">
          {filtered.map((v) => (
            <VetementCard key={v.id} v={v} onReload={onReload} typeNames={typeNames} />
          ))}
        </div>
      )}
    </div>
  );
}

function VetementCard({ v, onReload, typeNames }: { v: Vetement; onReload?: () => void; typeNames: string[] }) {
  const [failed, setFailed] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const photoUrl = (v.extra?.photo_url as string | undefined) || undefined;
  const border =
    v.needs_wash ? "border-red-500"
    : v.proprete_pct < 50 ? "border-amber-500"
    : "border-[var(--border)]";

  const uploadMutation = useUploadVetementPhoto();
  const updateMutation = useUpdateVetement();
  const current = v.type_objectif ?? "";
  const opts = current && !typeNames.includes(current) ? [current, ...typeNames] : typeNames;

  const onPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const couleur = (await dominantColorFromFile(file)) ?? undefined;
      await uploadMutation.mutateAsync({ id: v.id, file, couleurDominante: couleur });
      onReload?.();
    } catch {
      /* toast global */
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className={`relative rounded-xl border ${border} bg-[var(--card)] p-3 text-center flex flex-col items-center gap-1 card-hover`}>
      <button
        onClick={() => fileRef.current?.click()}
        disabled={uploading}
        title="Ajouter une photo (couleur dominante détectée)"
        className="absolute top-1 right-1 text-xs opacity-60 hover:opacity-100"
      >
        {uploading ? "…" : "📷"}
      </button>
      <input ref={fileRef} type="file" accept="image/*" onChange={(e) => void onPick(e)} className="hidden" />
      {photoUrl ? (
        <img src={mediaUrl(photoUrl)} alt={v.nom} style={{ height: "56px", width: "auto", objectFit: "cover", borderRadius: "6px" }} />
      ) : !failed ? (
        <img src={assetUrl(v.id)} alt={v.nom} onError={() => setFailed(true)} style={{ imageRendering: "pixelated", height: "56px", width: "auto" }} />
      ) : (
        <div className="text-2xl">{emojiForCategorie(v.categorie)}</div>
      )}
      <div className="text-xs font-medium truncate w-full" title={v.nom}>{v.nom}</div>
      <div className="text-[10px] text-[var(--muted-foreground)]">
        {v.marque ? v.marque + " · " : ""}{v.couleur}
      </div>
      <div className="flex gap-2 text-[10px]">
        <span className={v.needs_wash ? "text-red-500" : "text-[var(--muted-foreground)]"}>
          🧼 {v.proprete_pct.toFixed(0)}%
        </span>
        <span style={{ color: "var(--ring)" }}>⚙ {v.vie_pct.toFixed(0)}%</span>
      </div>
      {v.entretien && (
        <div
          className="text-[10px] text-[var(--muted-foreground)] flex items-center gap-1"
          title={`Entretien (${v.matiere ?? "matière inconnue"}) : ${v.entretien.resume}`}
        >
          <span>{v.entretien.icones}</span>
          <span className="truncate">
            {v.entretien.temperature ? `${v.entretien.temperature}°C` : v.entretien.lavage}
            {v.entretien.delicat ? " · délicat" : ""}
          </span>
        </div>
      )}
      <select
        title="Type objectif"
        value={current}
        onChange={(e) => updateMutation.mutate({ id: v.id, patch: { type_objectif: e.target.value || null } })}
        className="mt-1 w-full rounded border border-[var(--border)] bg-[var(--card)] px-1.5 py-1 text-[10px]"
      >
        <option value="">— Type objectif —</option>
        {opts.map((t) => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>
    </div>
  );
}
