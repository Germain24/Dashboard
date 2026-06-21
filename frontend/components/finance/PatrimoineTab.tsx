"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, Plus } from "lucide-react";
import { financeApi, PATRIMOINE_DEVISES, type NetWorthPoint, type PatrimoineItem, type PatrimoineItemCreate } from "@/lib/finance";

const eur = (n: number) =>
  new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);

const KEY = ["finance", "patrimoine"] as const;

const BANK_CAT = "Compte en banque";

/** Regroupe les actifs par catégorie ; "Compte en banque" en tête, puis alpha. */
function groupByCategorie(items: PatrimoineItem[]): [string, PatrimoineItem[]][] {
  const groups = new Map<string, PatrimoineItem[]>();
  for (const it of items) {
    const k = it.categorie?.trim() || "Autres";
    (groups.get(k) ?? groups.set(k, []).get(k)!).push(it);
  }
  return [...groups.entries()].sort((a, b) =>
    a[0] === BANK_CAT ? -1 : b[0] === BANK_CAT ? 1 : a[0].localeCompare(b[0], "fr"),
  );
}

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

      <AccountBreakdownChart />

      <NetWorthChart />


      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-4">
          {groupByCategorie(actifs).map(([cat, its]) => (
            <ItemList key={cat} title={cat} items={its} onUpdate={(id, patch) => update.mutate({ id, patch })} onDelete={(id) => remove.mutate(id)} />
          ))}
          {actifs.length === 0 && <ItemList title="Actifs (comptes, RealT, crypto…)" items={[]} onUpdate={() => {}} onDelete={() => {}} />}
        </div>
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

const fmtDay = (iso: string) =>
  new Date(iso + "T12:00:00").toLocaleDateString("fr-CA", { day: "2-digit", month: "short" });

const ACCOUNT_PALETTE = [
  "#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6",
  "#06b6d4", "#ec4899", "#84cc16", "#14b8a6", "#f97316",
];

const fmtMonthYear = (iso: string) =>
  new Date(iso + "T12:00:00").toLocaleDateString("fr-CA", { month: "short", year: "2-digit" });

/** Aire empilée : valeur brute ventilée par compte, jour par jour (report du
 *  dernier solde connu de chaque relevé). Une couleur par compte. */
function AccountBreakdownChart() {
  const { data } = useQuery({
    queryKey: [...KEY, "breakdown"],
    queryFn: () => financeApi.patrimoineBreakdownHistory(3650),
  });
  const dates = data?.dates ?? [];
  const comptes = data?.comptes ?? [];
  const series = data?.series ?? {};
  const total = data?.total ?? [];
  const color = (i: number) => ACCOUNT_PALETTE[i % ACCOUNT_PALETTE.length];

  if (dates.length < 2 || comptes.length === 0) {
    return (
      <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">Évolution par compte</p>
        <p className="mt-2 text-xs text-[var(--muted-foreground)]">
          Pas encore assez de relevés pour tracer la répartition de ta valeur brute dans le temps.
        </p>
      </div>
    );
  }
  const n = dates.length;
  const max = Math.max(1, ...total);
  const W = 100, H = 100;
  const X = (i: number) => ((i / (n - 1)) * W).toFixed(2);
  const Y = (v: number) => (H - (v / max) * H).toFixed(2);

  // Aires empilées : bande de chaque compte entre le cumul précédent et le sien.
  let prev = new Array(n).fill(0);
  const bands = comptes.map((c, ci) => {
    const vals = series[c] ?? [];
    const cum = prev.map((p, i) => p + (vals[i] ?? 0));
    const top = cum.map((v, i) => `${X(i)},${Y(v)}`);
    const bottom: string[] = [];
    for (let i = n - 1; i >= 0; i--) bottom.push(`${X(i)},${Y(prev[i])}`);
    const poly = [...top, ...bottom].join(" ");
    prev = cum;
    return { c, color: color(ci), poly };
  });

  const last = total[total.length - 1] ?? 0;
  const labelIdx = [0, Math.floor(n / 4), Math.floor(n / 2), Math.floor((3 * n) / 4), n - 1];

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">Évolution par compte · valeur brute</p>
        <span className="shrink-0 text-xs tabular-nums text-[var(--foreground)]">{eur(last)}</span>
      </div>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-48 w-full"
        role="img" aria-label="Évolution de la valeur par compte">
        {bands.map((b) => (
          <polygon key={b.c} points={b.poly} fill={b.color} fillOpacity={0.85} stroke="none">
            <title>{b.c}</title>
          </polygon>
        ))}
      </svg>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-[var(--muted-foreground)]">
        {labelIdx.map((i) => <span key={i}>{fmtMonthYear(dates[i])}</span>)}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs">
        {comptes.map((c, ci) => (
          <li key={c} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: color(ci) }} />
            <span className="text-[var(--muted-foreground)]">{c}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Courbe d'évolution du patrimoine net dans le temps (#257). */
function NetWorthChart() {
  const { data } = useQuery({
    queryKey: [...KEY, "history"],
    queryFn: () => financeApi.patrimoineHistory(365),
  });
  const points: NetWorthPoint[] = data?.points ?? [];

  if (points.length < 2) {
    return (
      <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">Évolution du patrimoine net</p>
        <p className="mt-2 text-xs text-[var(--muted-foreground)]">
          Le suivi se construit au fil des jours — reviens demain pour voir la courbe.
        </p>
      </div>
    );
  }

  const nets = points.map((p) => p.net);
  const min = Math.min(...nets);
  const max = Math.max(...nets);
  const span = max - min || 1;
  const W = 100, H = 32;
  const coords = points
    .map((p, i) => `${((i / (points.length - 1)) * W).toFixed(2)},${(H - ((p.net - min) / span) * H).toFixed(2)}`)
    .join(" ");
  const first = points[0];
  const delta = points[points.length - 1].net - first.net;
  const up = delta >= 0;

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">Évolution du patrimoine net</p>
        <span className={`shrink-0 text-xs tabular-nums ${up ? "text-[var(--success-foreground)]" : "text-[var(--warning-foreground)]"}`}>
          {up ? "+" : ""}{eur(delta)} depuis le {fmtDay(first.date)}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-24 w-full" role="img" aria-label="Courbe du patrimoine net">
        <polyline points={coords} fill="none" stroke="var(--ring)" strokeWidth={0.8} vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-[var(--muted-foreground)]">
        <span>min {eur(min)}</span>
        <span>max {eur(max)}</span>
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
  const isAuto = it.valeur_source === "auto";
  return (
    <li className="flex items-center gap-2 px-3 py-2 text-sm">
      <span className="min-w-0 flex-1 truncate text-[var(--foreground)]">{it.label}{it.categorie && <span className="ml-1.5 text-xs text-[var(--muted-foreground)]">· {it.categorie}</span>}</span>
      {isAuto ? (
        <span
          className="flex w-24 items-center justify-end gap-1 px-1 py-0.5 text-right tabular-nums"
          title={`Solde importé${it.valeur_auto_date ? ` au ${it.valeur_auto_date}` : ""} — mis à jour à chaque import de relevé`}
        >
          {Number(it.valeur).toLocaleString("fr-FR")}
          <span className="rounded bg-[var(--muted)] px-1 text-[10px] font-medium text-[var(--muted-foreground)]">auto</span>
        </span>
      ) : (
        <input
          value={val}
          onChange={(e) => setVal(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
          className="w-24 rounded border border-transparent bg-transparent px-1 py-0.5 text-right tabular-nums hover:border-[var(--border)] focus:border-[var(--ring)] focus:outline-none"
        />
      )}
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
