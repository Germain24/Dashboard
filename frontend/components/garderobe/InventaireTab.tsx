"use client";

import { useMemo, useState } from "react";
import type { Vetement } from "@/lib/garderobe";
import { emojiForCategorie, assetUrl } from "@/lib/garderobe";

export function InventaireTab({ wardrobe }: { wardrobe: Vetement[] }) {
  const [cat, setCat] = useState<string>("");
  const [style, setStyle] = useState<string>("");
  const [etat, setEtat] = useState<string>("");

  const cats = useMemo(
    () => Array.from(new Set(wardrobe.map((v) => v.categorie).filter(Boolean))).sort(),
    [wardrobe],
  );
  const styles = useMemo(() => {
    const s = new Set<string>();
    for (const v of wardrobe) for (const st of v.style || []) s.add(st);
    return Array.from(s).sort();
  }, [wardrobe]);

  const filtered = useMemo(() => {
    return wardrobe.filter((v) => {
      if (cat && v.categorie !== cat) return false;
      if (style && !(v.style || []).includes(style)) return false;
      if (etat === "propre" && !(v.proprete_pct >= 70 && !v.needs_wash)) return false;
      if (etat === "mi-sale" && !(v.proprete_pct >= 30 && v.proprete_pct < 70)) return false;
      if (etat === "a-laver" && !v.needs_wash) return false;
      if (etat === "hs" && !v.is_worn_out) return false;
      return true;
    });
  }, [wardrobe, cat, style, etat]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        <select value={cat} onChange={(e) => setCat(e.target.value)} className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm">
          <option value="">Toutes catégories</option>
          {cats.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={style} onChange={(e) => setStyle(e.target.value)} className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm">
          <option value="">Tous styles</option>
          {styles.map((s) => <option key={s} value={s}>{s}</option>)}
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
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {filtered.map((v) => (
            <VetementCard key={v.id} v={v} />
          ))}
        </div>
      )}
    </div>
  );
}

function VetementCard({ v }: { v: Vetement }) {
  const [failed, setFailed] = useState(false);
  const border =
    v.needs_wash ? "border-red-500"
    : v.proprete_pct < 50 ? "border-amber-500"
    : "border-[var(--border)]";

  return (
    <div className={`rounded-lg border ${border} bg-[var(--card)] p-3 text-center flex flex-col items-center gap-1`}>
      {!failed ? (
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
        <span className="text-blue-400">⚙ {v.vie_pct.toFixed(0)}%</span>
      </div>
    </div>
  );
}
