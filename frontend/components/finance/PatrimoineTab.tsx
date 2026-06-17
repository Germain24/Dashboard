"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, Plus } from "lucide-react";
import { financeApi, PATRIMOINE_DEVISES, type PatrimoineItem, type PatrimoineItemCreate } from "@/lib/finance";

const eur = (n: number) =>
  new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);

const KEY = ["finance", "patrimoine"] as const;

export function PatrimoineTab() {
  const qc = useQueryClient();
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: KEY, queryFn: financeApi.patrimoine });
  const invalidate = () => qc.invalidateQueries({ queryKey: KEY });
  const create = useMutation({ mutationFn: (b: PatrimoineItemCreate) => financeApi.patrimoineCreate(b), onSuccess: invalidate });
  const update = useMutation({ mutationFn: ({ id, patch }: { id: number; patch: Partial<PatrimoineItemCreate> }) => financeApi.patrimoineUpdate(id, patch), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: (id: number) => financeApi.patrimoineDelete(id), onSuccess: invalidate });

  const [type, setType] = useState<"actif" | "passif">("actif");
  const [label, setLabel] = useState("");
  const [valeur, setValeur] = useState("");
  const [devise, setDevise] = useState("EUR");
  const [categorie, setCategorie] = useState("");

  if (isError)
    return (
      <div className="text-sm text-[var(--warning-foreground)]">
        Impossible de charger le patrimoine.{" "}
        <button onClick={() => void refetch()} className="underline hover:text-[var(--foreground)]">Réessayer</button>
      </div>
    );
  if (isLoading || !data) return <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>;

  const submit = () => {
    if (!label.trim() || !valeur) return;
    create.mutate({ type, label: label.trim(), valeur: Number(valeur), devise, categorie: categorie.trim() });
    setLabel(""); setValeur(""); setCategorie("");
  };

  const actifs = data.items.filter((i) => i.type === "actif");
  const passifs = data.items.filter((i) => i.type === "passif");

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Patrimoine net" value={eur(data.net)} strong />
        <Stat label="Actifs" value={eur(data.actifs_manuels)} />
        <Stat label="Passifs" value={eur(data.passifs)} negative />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <ItemList title="Actifs (comptes, RealT, crypto…)" items={actifs} onUpdate={(id, patch) => update.mutate({ id, patch })} onDelete={(id) => remove.mutate(id)} />
        <ItemList title="Passifs (emprunts…)" items={passifs} onUpdate={(id, patch) => update.mutate({ id, patch })} onDelete={(id) => remove.mutate(id)} negative />
      </div>

      <div className="rounded-[var(--radius-lg)] border border-dashed border-[var(--border)] p-3">
        <p className="mb-2 text-xs font-semibold text-[var(--muted-foreground)]">Ajouter une ligne</p>
        <div className="flex flex-wrap items-center gap-2">
          <select value={type} onChange={(e) => setType(e.target.value as "actif" | "passif")} className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm">
            <option value="actif">Actif</option>
            <option value="passif">Passif</option>
          </select>
          <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Libellé (ex. Bourse Direct)" className="min-w-40 flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
          <input value={categorie} onChange={(e) => setCategorie(e.target.value)} placeholder="Catégorie" className="w-28 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
          <input type="number" value={valeur} onChange={(e) => setValeur(e.target.value)} placeholder="Valeur" className="w-28 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm tabular-nums" />
          <select value={devise} onChange={(e) => setDevise(e.target.value)} className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm">
            {PATRIMOINE_DEVISES.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
          <button onClick={submit} disabled={create.isPending} className="flex items-center gap-1.5 rounded-lg bg-[var(--ring)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50">
            <Plus size={14} /> Ajouter
          </button>
        </div>
        <p className="mt-2 text-xs text-[var(--muted-foreground)]">Saisis chaque compte dans sa devise locale — le total net est converti en €.</p>
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

function ItemRow({ it, onUpdate, onDelete }: { it: PatrimoineItem; onUpdate: (id: number, patch: Partial<PatrimoineItemCreate>) => void; onDelete: (id: number) => void }) {
  // L'état local est réinitialisé via la `key` du composant (= valeur serveur),
  // ce qui resynchronise l'input après un refetch sans setState-dans-effet.
  const [val, setVal] = useState(String(it.valeur));
  const commit = () => {
    const trimmed = val.trim();
    if (trimmed === "") { setVal(String(it.valeur)); return; }  // champ vidé → on annule (pas de 0 silencieux)
    const n = Number(trimmed);
    if (Number.isNaN(n)) { setVal(String(it.valeur)); return; }
    if (n !== it.valeur) onUpdate(it.id, { valeur: n });
  };
  return (
    <li className="flex items-center gap-2 px-3 py-2 text-sm">
      <span className="min-w-0 flex-1 truncate text-[var(--foreground)]">{it.label}{it.categorie && <span className="ml-1.5 text-xs text-[var(--muted-foreground)]">· {it.categorie}</span>}</span>
      <input
        value={val}
        onChange={(e) => setVal(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
        className="w-24 rounded border border-transparent bg-transparent px-1 py-0.5 text-right tabular-nums hover:border-[var(--border)] focus:border-[var(--ring)] focus:outline-none"
      />
      <select value={it.devise} onChange={(e) => onUpdate(it.id, { devise: e.target.value })} className="rounded bg-transparent text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
        {PATRIMOINE_DEVISES.map((d) => <option key={d} value={d}>{d}</option>)}
      </select>
      {it.devise !== "EUR" && it.valeur_eur != null && (
        <span className={`shrink-0 tabular-nums text-xs text-[var(--muted-foreground)]`}>= {eur(it.valeur_eur)}</span>
      )}
      <button onClick={() => onDelete(it.id)} aria-label="Supprimer" className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"><Trash2 size={14} /></button>
    </li>
  );
}

function ItemList({ title, items, onUpdate, onDelete, negative }: { title: string; items: PatrimoineItem[]; onUpdate: (id: number, patch: Partial<PatrimoineItemCreate>) => void; onDelete: (id: number) => void; negative?: boolean }) {
  const total = items.reduce((s, i) => s + (i.valeur_eur ?? i.valeur), 0);
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">{title}</p>
        <p className={`text-xs tabular-nums ${negative ? "text-[var(--warning-foreground)]" : "text-[var(--muted-foreground)]"}`}>{eur(total)}</p>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-[var(--muted-foreground)]">—</p>
      ) : (
        <ul className="divide-y divide-[var(--glass-border)] rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)]">
          {items.map((it) => <ItemRow key={`${it.id}:${it.valeur}:${it.devise}`} it={it} onUpdate={onUpdate} onDelete={onDelete} />)}
        </ul>
      )}
    </div>
  );
}
