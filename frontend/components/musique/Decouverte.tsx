"use client";

import { useState } from "react";
import { musiqueApi } from "@/lib/musique";

const AMBIANCES = ["café", "loft", "coworking", "étude", "repos", "énergie", "soirée", "love"];

export function Decouverte() {
  const [sel, setSel] = useState("café");
  const [items, setItems] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const go = async () => {
    setLoading(true);
    try { const r = await musiqueApi.discovery(sel); setItems(r.suggestions); }
    finally { setLoading(false); }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5 items-center">
        {AMBIANCES.map((a) => (
          <button key={a} onClick={() => setSel(a)}
            className={`text-xs px-2.5 py-1 rounded-full border ${sel === a
              ? "bg-[var(--ring)] text-white border-[var(--ring)]" : "border-[var(--border)]"}`}>{a}</button>
        ))}
        <button onClick={() => void go()} disabled={loading}
          className="ml-auto rounded-md border border-[var(--border)] px-3 py-1.5 text-sm">{loading ? "…" : "Suggérer (Ollama)"}</button>
      </div>
      <ul className="list-disc pl-5 text-sm space-y-0.5">
        {items.map((s, i) => <li key={i}>{s}</li>)}
      </ul>
      <p className="text-xs text-[var(--muted-foreground)]">Artistes/genres à explorer pour agrandir ta bibliothèque (suggestions locales, à vérifier).</p>
    </div>
  );
}
