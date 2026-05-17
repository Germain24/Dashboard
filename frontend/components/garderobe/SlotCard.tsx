"use client";

import Image from "next/image";
import { useState } from "react";
import type { Vetement, SlotInfo } from "@/lib/garderobe";
import { emojiForCategorie, assetUrl } from "@/lib/garderobe";

type Props = {
  slot: SlotInfo;
  item: Vetement | null;
  candidates: Vetement[];
  onChange: (next: Vetement | null) => void;
};

export function SlotCard({ slot, item, candidates, onChange }: Props) {
  // Liste de navigation : pour les slots ALWAYS, pas de None
  const navItems: (Vetement | null)[] =
    slot.need === "ALWAYS" ? [...candidates] : [null, ...candidates];
  const currentIdx = item ? navItems.findIndex((c) => c?.id === item.id) : 0;

  const cycle = (dir: 1 | -1) => {
    if (navItems.length === 0) return;
    const next = (currentIdx + dir + navItems.length) % navItems.length;
    onChange(navItems[next]);
  };

  const tagColor =
    slot.need === "ALWAYS" ? "text-blue-500"
    : slot.need === "METEO" ? "text-amber-500"
    : "text-[var(--muted-foreground)]";
  const tagLabel = slot.need === "ALWAYS" ? "REQUIS" : slot.need === "METEO" ? "MÉTÉO" : "OPT.";

  return (
    <div className="flex flex-col gap-1">
      <div className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">
        {slot.emoji} {slot.id} <span className={tagColor}>{tagLabel}</span>
      </div>
      <div className="flex items-stretch gap-1">
        <button
          className="px-2 py-1 text-sm rounded border border-[var(--border)] hover:bg-[var(--accent)]"
          onClick={() => cycle(-1)}
          aria-label={`précédent ${slot.id}`}
        >
          ‹
        </button>
        <SlotPreview item={item} slot={slot} />
        <button
          className="px-2 py-1 text-sm rounded border border-[var(--border)] hover:bg-[var(--accent)]"
          onClick={() => cycle(1)}
          aria-label={`suivant ${slot.id}`}
        >
          ›
        </button>
      </div>
    </div>
  );
}

function SlotPreview({ item, slot }: { item: Vetement | null; slot: SlotInfo }) {
  const [pngFailed, setPngFailed] = useState(false);

  if (!item) {
    return (
      <div className="flex-1 min-h-[110px] rounded-md border border-dashed border-[var(--border)] bg-[var(--muted)] flex flex-col items-center justify-center text-[var(--muted-foreground)] opacity-60">
        <div className="text-2xl">{slot.emoji}</div>
        <div className="text-[10px]">Non porté</div>
      </div>
    );
  }

  const border =
    item.needs_wash || item.is_worn_out ? "border-red-500"
    : item.proprete_pct >= 70 ? "border-blue-500"
    : item.proprete_pct >= 40 ? "border-amber-500" : "border-red-500";

  return (
    <div className={`flex-1 min-h-[110px] rounded-md border ${border} bg-[var(--card)] flex flex-col items-center justify-center gap-1 p-2 text-center`}>
      {!pngFailed ? (
        // Pixel art si dispo
        <img
          src={assetUrl(item.id)}
          alt={item.nom}
          onError={() => setPngFailed(true)}
          style={{ imageRendering: "pixelated", height: "60px", width: "auto" }}
        />
      ) : (
        <div className="text-3xl">{emojiForCategorie(item.categorie)}</div>
      )}
      <div className="text-[11px] font-medium truncate w-full" title={item.nom}>
        {item.nom}
      </div>
      <div className="text-[9px] text-[var(--muted-foreground)]">
        {item.couleur} · 🌡 {item.thermal_score.toFixed(1)}
      </div>
      <div className="flex gap-2 text-[9px]">
        <span className={item.needs_wash ? "text-red-500" : item.proprete_pct >= 70 ? "text-emerald-500" : "text-amber-500"}>
          {item.needs_wash ? "🧺 SALE" : `🧼 ${item.proprete_pct.toFixed(0)}%`}
        </span>
        <span className="text-blue-400">⚙ {item.vie_pct.toFixed(0)}%</span>
      </div>
    </div>
  );
}
