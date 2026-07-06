"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, Plus } from "lucide-react";
import {
  financeApi,
  type CreditAccount,
  type CreditAccountCreate,
  type CreditProfile,
  type CreditScoreEntry,
} from "@/lib/finance";

const cad = (n: number) =>
  new Intl.NumberFormat("fr-CA", { style: "currency", currency: "CAD", maximumFractionDigits: 0 }).format(n);

const fmtMonthYear = (iso: string) =>
  new Date(iso + "T12:00:00").toLocaleDateString("fr-CA", { month: "short", year: "numeric" });

const KEY = ["finance", "credit"] as const;

export function CreditTab() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: KEY });

  const plan = useQuery({ queryKey: [...KEY, "plan"], queryFn: financeApi.creditPlan });
  const profile = useQuery({ queryKey: [...KEY, "profile"], queryFn: financeApi.creditProfile });
  const accounts = useQuery({ queryKey: [...KEY, "accounts"], queryFn: financeApi.creditAccounts });
  const scores = useQuery({ queryKey: [...KEY, "scores"], queryFn: financeApi.creditScores });

  const updateProfile = useMutation({ mutationFn: financeApi.creditProfileUpdate, onSuccess: invalidate });
  const createAccount = useMutation({ mutationFn: financeApi.creditAccountCreate, onSuccess: invalidate });
  const updateAccount = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<CreditAccountCreate> }) =>
      financeApi.creditAccountUpdate(id, patch),
    onSuccess: invalidate,
  });
  const deleteAccount = useMutation({ mutationFn: financeApi.creditAccountDelete, onSuccess: invalidate });
  const createScore = useMutation({ mutationFn: financeApi.creditScoreCreate, onSuccess: invalidate });
  const deleteScore = useMutation({ mutationFn: financeApi.creditScoreDelete, onSuccess: invalidate });

  const anyError = plan.isError || profile.isError || accounts.isError || scores.isError;
  const anyLoading =
    plan.isLoading || profile.isLoading || accounts.isLoading || scores.isLoading ||
    !plan.data || !profile.data || !accounts.data || !scores.data;

  if (anyError)
    return (
      <div className="text-sm text-[var(--warning-foreground)]">
        Impossible de charger la marge de crédit.{" "}
        <button
          onClick={() => { void plan.refetch(); void profile.refetch(); void accounts.refetch(); void scores.refetch(); }}
          className="underline hover:text-[var(--foreground)]"
        >
          Réessayer
        </button>
      </div>
    );
  if (anyLoading) return <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3">
        <Stat label="Marge totale actuelle" value={cad(plan.data.marge_actuelle)} strong />
        <Stat
          label={`Marge projetée au ${fmtMonthYear(profile.data.date_cible)}`}
          value={cad(plan.data.marge_projetee_a_date_cible)}
          strong
        />
      </div>

      <p className="text-xs text-[var(--muted-foreground)]">
        La marge projetée est une estimation heuristique, pas une garantie d&apos;approbation bancaire.
      </p>

      <ProjectionChart points={plan.data.projection} />

      <ProfileForm profile={profile.data} onSave={(patch) => updateProfile.mutate(patch)} />

      <AccountsSection
        accounts={accounts.data}
        onCreate={(body) => createAccount.mutate(body)}
        onUpdate={(id, patch) => updateAccount.mutate({ id, patch })}
        onDelete={(id) => deleteAccount.mutate(id)}
      />

      <ScoresSection
        scores={scores.data}
        onCreate={(body) => createScore.mutate(body)}
        onDelete={(id) => deleteScore.mutate(id)}
      />

      <RoadmapSection actions={plan.data.actions} />
    </div>
  );
}

function Stat({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-3">
      <div className="text-xs text-[var(--muted-foreground)]">{label}</div>
      <div className={`tabular-nums text-[var(--foreground)] ${strong ? "text-xl font-semibold" : "text-base"}`}>{value}</div>
    </div>
  );
}

function ProjectionChart({ points }: { points: { date: string; marge_totale: number }[] }) {
  if (points.length < 2) return null;
  const values = points.map((p) => p.marge_totale);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const W = 100, H = 32;
  const coords = values
    .map((v, i) => `${((i / (values.length - 1)) * W).toFixed(2)},${(H - ((v - min) / span) * H).toFixed(2)}`)
    .join(" ");

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
      <p className="mb-2 text-xs font-semibold text-[var(--muted-foreground)]">Marge de crédit totale projetée</p>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-24 w-full" role="img" aria-label="Projection de la marge de crédit totale">
        <polyline points={coords} fill="none" stroke="var(--ring)" strokeWidth={0.8} vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-[var(--muted-foreground)]">
        <span>{fmtMonthYear(points[0].date)} · {cad(min)}</span>
        <span>{fmtMonthYear(points[points.length - 1].date)} · {cad(max)}</span>
      </div>
    </div>
  );
}

function ProfileForm({
  profile,
  onSave,
}: {
  profile: CreditProfile;
  onSave: (patch: { revenu_annuel?: number; date_arrivee_canada?: string; date_cible?: string }) => void;
}) {
  const [revenu, setRevenu] = useState(String(profile.revenu_annuel));
  const [arrivee, setArrivee] = useState(profile.date_arrivee_canada);
  const [cible, setCible] = useState(profile.date_cible);

  const commitRevenu = () => {
    const n = Number(revenu);
    if (!Number.isNaN(n) && n !== profile.revenu_annuel) onSave({ revenu_annuel: n });
  };

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
      <p className="mb-2 text-xs font-semibold text-[var(--muted-foreground)]">Profil</p>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-1.5">
          Revenu annuel
          <input
            value={revenu}
            onChange={(e) => setRevenu(e.target.value)}
            onBlur={commitRevenu}
            type="number"
            className="w-24 rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-right tabular-nums"
          />
        </label>
        <label className="flex items-center gap-1.5">
          Arrivée au Canada
          <input
            value={arrivee}
            onChange={(e) => setArrivee(e.target.value)}
            onBlur={() => arrivee !== profile.date_arrivee_canada && onSave({ date_arrivee_canada: arrivee })}
            type="date"
            className="rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1"
          />
        </label>
        <label className="flex items-center gap-1.5">
          Date cible
          <input
            value={cible}
            onChange={(e) => setCible(e.target.value)}
            onBlur={() => cible !== profile.date_cible && onSave({ date_cible: cible })}
            type="date"
            className="rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1"
          />
        </label>
      </div>
    </div>
  );
}

function AccountsSection({
  accounts,
  onCreate,
  onUpdate,
  onDelete,
}: {
  accounts: CreditAccount[];
  onCreate: (body: CreditAccountCreate) => void;
  onUpdate: (id: number, patch: Partial<CreditAccountCreate>) => void;
  onDelete: (id: number) => void;
}) {
  const [institution, setInstitution] = useState("");
  const [produit, setProduit] = useState("");
  const [limite, setLimite] = useState("");
  const [dateOuverture, setDateOuverture] = useState("");

  const submit = () => {
    if (!institution.trim() || !produit.trim() || !limite || !dateOuverture) return;
    onCreate({ institution: institution.trim(), produit: produit.trim(), limite_actuelle: Number(limite), date_ouverture: dateOuverture });
    setInstitution(""); setProduit(""); setLimite(""); setDateOuverture("");
  };

  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold text-[var(--muted-foreground)]">Mes comptes de crédit</p>
      {accounts.length === 0 ? (
        <p className="text-xs text-[var(--muted-foreground)]">Aucun compte enregistré.</p>
      ) : (
        <ul className="divide-y divide-[var(--glass-border)] rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)]">
          {accounts.map((a) => (
            <AccountRow key={`${a.id}:${a.limite_actuelle}:${a.statut}`} account={a} onUpdate={onUpdate} onDelete={onDelete} />
          ))}
        </ul>
      )}
      <div className="mt-3 rounded-[var(--radius-lg)] border border-dashed border-[var(--border)] p-3">
        <div className="flex flex-wrap items-center gap-2">
          <input value={institution} onChange={(e) => setInstitution(e.target.value)} placeholder="Institution" className="w-32 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
          <input value={produit} onChange={(e) => setProduit(e.target.value)} placeholder="Produit (ex. Carte Mastercard)" className="min-w-40 flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
          <input value={limite} onChange={(e) => setLimite(e.target.value)} type="number" placeholder="Limite" className="w-24 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm tabular-nums" />
          <input value={dateOuverture} onChange={(e) => setDateOuverture(e.target.value)} type="date" className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
          <button onClick={submit} className="flex items-center gap-1.5 rounded-lg bg-[var(--ring)] px-3 py-1.5 text-sm font-medium text-white">
            <Plus size={14} /> Ajouter
          </button>
        </div>
      </div>
    </div>
  );
}

function AccountRow({
  account,
  onUpdate,
  onDelete,
}: {
  account: CreditAccount;
  onUpdate: (id: number, patch: Partial<CreditAccountCreate>) => void;
  onDelete: (id: number) => void;
}) {
  const [limite, setLimite] = useState(String(account.limite_actuelle));
  const commit = () => {
    const n = Number(limite);
    if (!Number.isNaN(n) && n !== account.limite_actuelle) onUpdate(account.id, { limite_actuelle: n });
  };
  return (
    <li className="flex items-center gap-2 px-3 py-2 text-sm">
      <span className="min-w-0 flex-1 truncate text-[var(--foreground)]">
        {account.institution} <span className="text-xs text-[var(--muted-foreground)]">· {account.produit}</span>
      </span>
      <span className="text-xs text-[var(--muted-foreground)]">depuis {fmtMonthYear(account.date_ouverture)}</span>
      <input
        value={limite}
        onChange={(e) => setLimite(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
        className="w-24 rounded border border-transparent bg-transparent px-1 py-0.5 text-right tabular-nums hover:border-[var(--border)] focus:border-[var(--ring)] focus:outline-none"
      />
      <select
        value={account.statut}
        onChange={(e) => onUpdate(account.id, { statut: e.target.value as "actif" | "ferme" })}
        className="rounded bg-transparent text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
      >
        <option value="actif">Actif</option>
        <option value="ferme">Fermé</option>
      </select>
      <button onClick={() => onDelete(account.id)} aria-label="Supprimer" className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]">
        <Trash2 size={14} />
      </button>
    </li>
  );
}

function ScoresSection({
  scores,
  onCreate,
  onDelete,
}: {
  scores: CreditScoreEntry[];
  onCreate: (body: { date: string; score: number; source?: string }) => void;
  onDelete: (id: number) => void;
}) {
  const [date, setDate] = useState("");
  const [score, setScore] = useState("");
  const [source, setSource] = useState("");

  const submit = () => {
    if (!date || !score) return;
    onCreate({ date, score: Number(score), source: source.trim() });
    setDate(""); setScore(""); setSource("");
  };

  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold text-[var(--muted-foreground)]">Historique de pointage</p>
      {scores.length === 0 ? (
        <p className="text-xs text-[var(--muted-foreground)]">Aucun pointage enregistré.</p>
      ) : (
        <ul className="divide-y divide-[var(--glass-border)] rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)]">
          {scores.map((s) => (
            <li key={s.id} className="flex items-center gap-2 px-3 py-2 text-sm">
              <span className="text-xs text-[var(--muted-foreground)]">{fmtMonthYear(s.date)}</span>
              <span className="flex-1 font-medium tabular-nums text-[var(--foreground)]">{s.score}</span>
              <span className="text-xs text-[var(--muted-foreground)]">{s.source}</span>
              <button onClick={() => onDelete(s.id)} aria-label="Supprimer" className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]">
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 rounded-[var(--radius-lg)] border border-dashed border-[var(--border)] p-3">
        <div className="flex flex-wrap items-center gap-2">
          <input value={date} onChange={(e) => setDate(e.target.value)} type="date" className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
          <input value={score} onChange={(e) => setScore(e.target.value)} type="number" placeholder="Score" className="w-24 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm tabular-nums" />
          <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="Source (ex. Credit Karma)" className="min-w-40 flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
          <button onClick={submit} className="flex items-center gap-1.5 rounded-lg bg-[var(--ring)] px-3 py-1.5 text-sm font-medium text-white">
            <Plus size={14} /> Ajouter
          </button>
        </div>
      </div>
    </div>
  );
}

function RoadmapSection({
  actions,
}: {
  actions: { date: string; type: "hausse" | "ouverture"; institution: string; produit: string; delta_limite: number; justification: string }[];
}) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold text-[var(--muted-foreground)]">Feuille de route recommandée</p>
      <p className="mb-2 text-xs text-[var(--muted-foreground)]">
        Estimations heuristiques — ajuste le catalogue si tu connais les vraies politiques d'une banque.
      </p>
      {actions.length === 0 ? (
        <p className="text-xs text-[var(--muted-foreground)]">Aucune action recommandée pour l'instant.</p>
      ) : (
        <ol className="space-y-2">
          {actions.map((a, i) => (
            <li key={i} className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-[var(--foreground)]">
                  {fmtMonthYear(a.date)} · {a.type === "hausse" ? "Demander une augmentation" : "Ouvrir un compte"} — {a.institution} ({a.produit})
                </span>
                <span className="shrink-0 tabular-nums text-[var(--success-foreground)]">+{cad(a.delta_limite)}</span>
              </div>
              <p className="mt-1 text-xs text-[var(--muted-foreground)]">{a.justification}</p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
