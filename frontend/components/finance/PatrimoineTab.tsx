"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, Plus } from "lucide-react";
import { financeApi, type PatrimoineItemCreate } from "@/lib/finance";

const fmt = (n: number, devise = "EUR") =>
  new Intl.NumberFormat("fr-FR", { style: "currency", currency: devise, maximumFractionDigits: 0 }).format(n);

const KEY = ["finance", "patrimoine"] as const;

export function PatrimoineTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: KEY, queryFn: financeApi.patrimoine });
  const invalidate = () => qc.invalidateQueries({ queryKey: KEY });
  const create = useMutation({ mutationFn: (b: PatrimoineItemCreate) => financeApi.patrimoineCreate(b), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: (id: number) => financeApi.patrimoineDelete(id), onSuccess: invalidate });

  const [type, setType] = useState<"actif" | "passif">("actif");
  const [label, setLabel] = useState("");
  const [valeur, setValeur] = useState("");
  const [categorie, setCategorie] = useState("");

  if (isLoading || !data) return <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>;

  const submit = () => {
    if (!label.trim() || !valeur) return;
    create.mutate({ type, label: label.trim(), valeur: Number(valeur), categorie: categorie.trim() });
    setLabel(""); setValeur(""); setCategorie("");
  };

  const actifs = data.items.filter((i) => i.type === "actif");
  const passifs = data.items.filter((i) => i.type === "passif");

  return (
    <div className="space-y-6">
      {/* Synthèse patrimoine net */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Patrimoine net" value={fmt(data.net)} strong />
        <Stat label="Portefeuille" value={fmt(data.portefeuille)} />
        <Stat label="Actifs manuels" value={fmt(data.actifs_manuels)} />
        <Stat label="Passifs" value={fmt(data.passifs)} negative />
      </div>

      {/* Listes */}
      <div className="grid gap-4 sm:grid-cols-2">
        <ItemList title="Actifs (RealT, crypto…)" items={actifs} onDelete={(id) => remove.mutate(id)} />
        <ItemList title="Passifs (emprunts…)" items={passifs} onDelete={(id) => remove.mutate(id)} negative />
      </div>

      {/* Ajout */}
      <div className="rounded-[var(--radius-lg)] border border-dashed border-[var(--border)] p-3">
        <p className="mb-2 text-xs font-semibold text-[var(--muted-foreground)]">Ajouter une ligne</p>
        <div className="flex flex-wrap items-center gap-2">
          <select value={type} onChange={(e) => setType(e.target.value as "actif" | "passif")} className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm">
            <option value="actif">Actif</option>
            <option value="passif">Passif</option>
          </select>
          <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Libellé (ex. RealT — 12 tokens)" className="min-w-40 flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
          <input value={categorie} onChange={(e) => setCategorie(e.target.value)} placeholder="Catégorie" className="w-32 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
          <input type="number" value={valeur} onChange={(e) => setValeur(e.target.value)} placeholder="Valeur €" className="w-28 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm tabular-nums" />
          <button onClick={submit} disabled={create.isPending} className="flex items-center gap-1.5 rounded-lg bg-[var(--ring)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50">
            <Plus size={14} /> Ajouter
          </button>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, strong, negative }: { label: string; value: string; strong?: boolean; negative?: boolean }) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-3">
      <div className="text-xs text-[var(--muted-foreground)]">{label}</div>
      <div className={`tabular-nums ${strong ? "text-xl font-semibold" : "text-base"} ${negative ? "text-[var(--warning-foreground)]" : "text-[var(--foreground)]"}`}>{value}</div>
    </div>
  );
}

function ItemList({ title, items, onDelete, negative }: { title: string; items: import("@/lib/finance").PatrimoineItem[]; onDelete: (id: number) => void; negative?: boolean }) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold text-[var(--muted-foreground)]">{title}</p>
      {items.length === 0 ? (
        <p className="text-xs text-[var(--muted-foreground)]">—</p>
      ) : (
        <ul className="divide-y divide-[var(--glass-border)] rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)]">
          {items.map((it) => (
            <li key={it.id} className="flex items-center gap-2 px-3 py-2 text-sm">
              <span className="min-w-0 flex-1 truncate text-[var(--foreground)]">{it.label}{it.categorie && <span className="ml-1.5 text-xs text-[var(--muted-foreground)]">· {it.categorie}</span>}</span>
              <span className={`shrink-0 tabular-nums ${negative ? "text-[var(--warning-foreground)]" : "text-[var(--foreground)]"}`}>{fmt(it.valeur, it.devise)}</span>
              <button onClick={() => onDelete(it.id)} aria-label="Supprimer" className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"><Trash2 size={14} /></button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
