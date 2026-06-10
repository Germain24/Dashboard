"use client";

import { useState } from "react";
import { Bibliotheque } from "./Bibliotheque";
import { Ambiances } from "./Ambiances";
import { Decouverte } from "./Decouverte";

const TABS = [["ambiances", "Ambiances"], ["bibliotheque", "Bibliothèque"], ["decouverte", "Découverte"]] as const;

export default function Musique() {
  const [tab, setTab] = useState<string>("ambiances");
  return (
    <div className="space-y-5 p-4 max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold">Musique</h1>
      <div className="flex gap-2">
        {TABS.map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`text-sm px-3 py-1.5 rounded-full border ${tab === id
              ? "bg-[var(--ring)] text-white border-[var(--ring)]" : "border-[var(--border)] text-[var(--muted-foreground)]"}`}>{label}</button>
        ))}
      </div>
      {tab === "ambiances" && <Ambiances />}
      {tab === "bibliotheque" && <Bibliotheque />}
      {tab === "decouverte" && <Decouverte />}
    </div>
  );
}
