"use client";

import { useState } from "react";
import { type MesureSante, todayKey } from "@/lib/sante";

type Props = {
  mesures: MesureSante[];
  onSave: (m: { date: string; poids?: number; photo_url?: string; note?: string }) => Promise<void>;
};

export function CompositionTab({ mesures, onSave }: Props) {
  const today = todayKey();
  const todays = mesures.find((m) => m.date === today);

  const [date, setDate] = useState(today);
  const [poids, setPoids] = useState<string>(todays?.poids?.toString() ?? "");
  const [photoUrl, setPhotoUrl] = useState<string>(todays?.photo_url ?? "");
  const [note, setNote] = useState<string>(todays?.note ?? "");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setMsg(null);
    try {
      await onSave({
        date,
        poids: poids ? parseFloat(poids) : undefined,
        photo_url: photoUrl || undefined,
        note: note || undefined,
      });
      setMsg("Enregistré ✔");
    } catch (e: any) {
      setMsg(`⚠ ${e?.message ?? "Erreur"}`);
    } finally {
      setSaving(false);
    }
  };

  const recent = [...mesures].reverse().slice(0, 30);

  return (
    <div className="space-y-4">
      <div className="rounded border border-[var(--border)] p-4 space-y-3">
        <h2 className="font-medium">Nouvelle mesure</h2>
        <div className="grid sm:grid-cols-2 gap-3">
          <label className="text-xs flex flex-col">
            Date
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
            />
          </label>
          <label className="text-xs flex flex-col">
            Poids (kg)
            <input
              type="number"
              step="0.1"
              value={poids}
              onChange={(e) => setPoids(e.target.value)}
              className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
              placeholder="ex. 51.2"
            />
          </label>
          <label className="text-xs flex flex-col sm:col-span-2">
            Photo (URL ou chemin local)
            <input
              type="text"
              value={photoUrl}
              onChange={(e) => setPhotoUrl(e.target.value)}
              className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
              placeholder="ex. file:///… ou https://…"
            />
          </label>
          <label className="text-xs flex flex-col sm:col-span-2">
            Note libre
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              className="mt-1 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
              placeholder="contexte, ressenti, tour de taille, % MG…"
            />
          </label>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded bg-[var(--primary)] text-[var(--primary-foreground)] px-3 py-1.5 text-sm font-medium disabled:opacity-50"
          >
            {saving ? "…" : "💾 Enregistrer"}
          </button>
          {msg && <span className="text-xs">{msg}</span>}
        </div>
      </div>

      <div className="rounded border border-[var(--border)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--muted)]/50 text-[var(--muted-foreground)] text-xs uppercase">
            <tr>
              <th className="text-left px-3 py-2">Date</th>
              <th className="text-right px-3 py-2">Poids</th>
              <th className="text-left px-3 py-2">Photo</th>
              <th className="text-left px-3 py-2">Note</th>
            </tr>
          </thead>
          <tbody>
            {recent.length === 0 && (
              <tr><td colSpan={4} className="px-3 py-4 text-center text-[var(--muted-foreground)]">
                Aucune mesure pour l'instant.
              </td></tr>
            )}
            {recent.map((m) => (
              <tr key={m.date} className="border-t border-[var(--border)]">
                <td className="px-3 py-1.5">{m.date}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">
                  {m.poids !== null ? `${m.poids.toFixed(1)} kg` : "—"}
                </td>
                <td className="px-3 py-1.5 text-xs">
                  {m.photo_url ? <a className="underline" href={m.photo_url} target="_blank" rel="noreferrer">photo</a> : "—"}
                </td>
                <td className="px-3 py-1.5 text-xs">{m.note ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
