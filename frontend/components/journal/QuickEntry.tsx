"use client";

import { useEffect, useState } from "react";
import { TAGS_EMOTIONS, type MoodEntry } from "@/lib/journal";
import { useJournalEntry, usePutJournalEntry } from "@/lib/queries/journal";

const todayISO = () => new Date().toISOString().slice(0, 10);

function Scale({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 text-sm text-[var(--muted-foreground)]">{label}</span>
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} onClick={() => onChange(n)}
          className={`h-8 w-8 rounded-full border text-sm ${value === n
            ? "bg-[var(--ring)] text-white border-[var(--ring)]"
            : "border-[var(--border)] hover:border-[var(--ring)]"}`}>{n}</button>
      ))}
    </div>
  );
}

export function QuickEntry({ onSaved }: { onSaved?: () => void }) {
  const date = todayISO();
  const [humeur, setHumeur] = useState(3);
  const [energie, setEnergie] = useState(3);
  const [tags, setTags] = useState<string[]>([]);
  const [note, setNote] = useState("");

  const entryQ = useJournalEntry(date);
  const putMutation = usePutJournalEntry();
  const saving = putMutation.isPending;

  useEffect(() => {
    const e: MoodEntry | undefined = entryQ.data;
    if (!e) return;
    setHumeur(e.humeur); setEnergie(e.energie); setTags(e.tags); setNote(e.note);
  }, [entryQ.data]);

  const toggleTag = (t: string) =>
    setTags((cur) => (cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t]));

  const save = () => {
    putMutation.mutate({ date, body: { humeur, energie, tags, note } }, {
      onSuccess: () => onSaved?.(),
    });
  };

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
      <h2 className="text-base font-semibold">Aujourd&apos;hui</h2>
      <Scale label="Humeur" value={humeur} onChange={setHumeur} />
      <Scale label="Énergie" value={energie} onChange={setEnergie} />
      <div className="flex flex-wrap gap-1.5">
        {TAGS_EMOTIONS.map((t) => (
          <button key={t} onClick={() => toggleTag(t)}
            className={`text-xs px-2.5 py-1 rounded-full border ${tags.includes(t)
              ? "bg-[var(--ring)] text-white border-[var(--ring)]"
              : "border-[var(--border)] text-[var(--muted-foreground)] hover:border-[var(--ring)]"}`}>{t}</button>
        ))}
      </div>
      <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note du jour (optionnel)"
        className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] p-2 text-sm" rows={2} />
      <button onClick={() => void save()} disabled={saving}
        className="rounded-md bg-[var(--primary)] text-[var(--primary-foreground)] px-3 py-1.5 text-sm font-medium disabled:opacity-50">
        {saving ? "…" : "Enregistrer"}
      </button>
    </div>
  );
}
