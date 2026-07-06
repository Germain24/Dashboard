"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, Plus } from "lucide-react";
import {
  financeApi,
  type CreditAccount,
  type CreditAccountCreate,
  type CreditActionRule,
  type CreditActionRuleCreate,
  type CreditMarginPoint,
  type CreditPlanAction,
  type CreditProfile,
  type CreditScoreEntry,
  type CreditScorePoint,
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
  const rules = useQuery({ queryKey: [...KEY, "rules"], queryFn: financeApi.creditRules });

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
  const createRule = useMutation({ mutationFn: financeApi.creditRuleCreate, onSuccess: invalidate });
  const deleteRule = useMutation({ mutationFn: financeApi.creditRuleDelete, onSuccess: invalidate });

  const anyError = plan.isError || profile.isError || accounts.isError || scores.isError || rules.isError;
  const anyLoading =
    plan.isLoading || profile.isLoading || accounts.isLoading || scores.isLoading || rules.isLoading ||
    !plan.data || !profile.data || !accounts.data || !scores.data || !rules.data;

  if (anyError)
    return (
      <div className="text-sm text-[var(--warning-foreground)]">
        Impossible de charger la marge de crédit.{" "}
        <button
          onClick={() => {
            void plan.refetch(); void profile.refetch(); void accounts.refetch();
            void scores.refetch(); void rules.refetch();
          }}
          className="underline hover:text-[var(--foreground)]"
        >
          Réessayer
        </button>
      </div>
    );
  if (anyLoading) return <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>;

  const dernierScore = plan.data.historique_score.length
    ? plan.data.historique_score[plan.data.historique_score.length - 1].score
    : null;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3">
        <Stat label="Marge totale actuelle" value={cad(plan.data.marge_actuelle)} strong />
        <Stat label="Score le plus récent" value={dernierScore === null ? "—" : String(dernierScore)} strong />
      </div>

      <p className="text-xs text-[var(--muted-foreground)]">
        La portion projetée (pointillée) est une estimation basée sur tes règles de seuils et la progression
        passée de ton score — pas une garantie bancaire.
      </p>

      <ScoreChart real={plan.data.historique_score} projected={plan.data.projection_score} />
      <MarginChart real={plan.data.historique_marge} projected={plan.data.projection_marge} />

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

      <RulesSection
        rules={rules.data}
        onCreate={(body) => createRule.mutate(body)}
        onDelete={(id) => deleteRule.mutate(id)}
      />

      <RoadmapSection actions={plan.data.actions} projectionPossible={plan.data.projection_possible} />
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

/** Construit une polyline pour la portion "réelle" et une pour la portion
 *  "projetée" (reliée au dernier point réel), sur un même axe X d'indices
 *  0..total-1 partagé entre les deux séries. */
function buildDualSeries<T>(real: T[], projected: T[], getValue: (p: T) => number, W: number, H: number) {
  const all = [...real, ...projected];
  if (all.length < 2) return null;
  const values = all.map(getValue);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const total = all.length;
  const x = (i: number) => (i / (total - 1)) * W;
  const y = (v: number) => H - ((v - min) / span) * H;

  const realCoords = real.map((p, i) => `${x(i).toFixed(2)},${y(getValue(p)).toFixed(2)}`).join(" ");
  const projCoords = projected.length
    ? [
        `${x(Math.max(real.length - 1, 0)).toFixed(2)},${y(real.length ? getValue(real[real.length - 1]) : getValue(projected[0])).toFixed(2)}`,
        ...projected.map((p, i) => `${x(real.length + i).toFixed(2)},${y(getValue(p)).toFixed(2)}`),
      ].join(" ")
    : "";

  return { all, min, max, realCoords, projCoords };
}

function ScoreChart({ real, projected }: { real: CreditScorePoint[]; projected: CreditScorePoint[] }) {
  const W = 100, H = 32;
  const built = buildDualSeries(real, projected, (p) => p.score, W, H);
  if (!built)
    return (
      <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">Cote de crédit dans le temps</p>
        <p className="mt-2 text-xs text-[var(--muted-foreground)]">Ajoute au moins 2 points de score pour voir la courbe.</p>
      </div>
    );
  const { all, realCoords, projCoords } = built;
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
      <p className="mb-2 text-xs font-semibold text-[var(--muted-foreground)]">Cote de crédit dans le temps</p>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-24 w-full" role="img" aria-label="Cote de credit dans le temps">
        {realCoords && <polyline points={realCoords} fill="none" stroke="var(--ring)" strokeWidth={0.8} vectorEffect="non-scaling-stroke" />}
        {projCoords && (
          <polyline points={projCoords} fill="none" stroke="var(--muted-foreground)" strokeWidth={0.8} strokeDasharray="2,1.5" vectorEffect="non-scaling-stroke" />
        )}
      </svg>
      {/* Le score n'est pas monotone (il baisse de SCORE_IMPACT_PAR_ACTION à chaque action
          déclenchée) : on affiche les valeurs aux deux extrémités de la période, pas le
          min/max global, pour ne pas associer une date à une valeur atteinte ailleurs. */}
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-[var(--muted-foreground)]">
        <span>{fmtMonthYear(all[0].date)} · {all[0].score}</span>
        <span>{fmtMonthYear(all[all.length - 1].date)} · {all[all.length - 1].score}</span>
      </div>
    </div>
  );
}

function MarginChart({ real, projected }: { real: CreditMarginPoint[]; projected: CreditMarginPoint[] }) {
  const W = 100, H = 32;
  const built = buildDualSeries(real, projected, (p) => p.marge_totale, W, H);
  if (!built)
    return (
      <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">Marge de crédit totale dans le temps</p>
        <p className="mt-2 text-xs text-[var(--muted-foreground)]">
          Ajoute au moins 2 points de score (dans la section pointage) pour voir la projection de marge.
        </p>
      </div>
    );
  const { all, min, max, realCoords, projCoords } = built;
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
      <p className="mb-2 text-xs font-semibold text-[var(--muted-foreground)]">Marge de crédit totale dans le temps</p>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-24 w-full" role="img" aria-label="Marge de credit totale dans le temps">
        {realCoords && <polyline points={realCoords} fill="none" stroke="var(--ring)" strokeWidth={0.8} vectorEffect="non-scaling-stroke" />}
        {projCoords && (
          <polyline points={projCoords} fill="none" stroke="var(--muted-foreground)" strokeWidth={0.8} strokeDasharray="2,1.5" vectorEffect="non-scaling-stroke" />
        )}
      </svg>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-[var(--muted-foreground)]">
        <span>{fmtMonthYear(all[0].date)} · {cad(min)}</span>
        <span>{fmtMonthYear(all[all.length - 1].date)} · {cad(max)}</span>
      </div>
    </div>
  );
}

function ProfileForm({ profile, onSave }: { profile: CreditProfile; onSave: (patch: { date_cible?: string }) => void }) {
  const [cible, setCible] = useState(profile.date_cible);
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
      <p className="mb-2 text-xs font-semibold text-[var(--muted-foreground)]">Profil</p>
      <label className="flex items-center gap-1.5 text-sm">
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

function RulesSection({
  rules,
  onCreate,
  onDelete,
}: {
  rules: CreditActionRule[];
  onCreate: (body: CreditActionRuleCreate) => void;
  onDelete: (id: number) => void;
}) {
  const [seuil, setSeuil] = useState("");
  const [type, setType] = useState<"hausse" | "nouvelle_carte">("hausse");
  const [montant, setMontant] = useState("");

  const submit = () => {
    if (!seuil || !montant) return;
    onCreate({ seuil_score: Number(seuil), type, montant_estime: Number(montant) });
    setSeuil(""); setMontant("");
  };

  const sorted = [...rules].sort((a, b) => a.seuil_score - b.seuil_score);

  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold text-[var(--muted-foreground)]">Règles de seuils</p>
      <p className="mb-2 text-xs text-[var(--muted-foreground)]">
        À partir de quel score demander une augmentation ou ouvrir une nouvelle carte, et pour combien.
      </p>
      {sorted.length === 0 ? (
        <p className="text-xs text-[var(--muted-foreground)]">Aucune règle définie.</p>
      ) : (
        <ul className="divide-y divide-[var(--glass-border)] rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)]">
          {sorted.map((r) => (
            <li key={r.id} className="flex items-center gap-2 px-3 py-2 text-sm">
              <span className="w-20 shrink-0 tabular-nums text-[var(--foreground)]">Score {r.seuil_score}</span>
              <span className="flex-1 text-[var(--muted-foreground)]">
                {r.type === "hausse" ? "Demander une augmentation" : "Ouvrir une nouvelle carte"}
              </span>
              <span className="shrink-0 tabular-nums text-[var(--success-foreground)]">+{cad(r.montant_estime)}</span>
              <button onClick={() => onDelete(r.id)} aria-label="Supprimer" className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]">
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 rounded-[var(--radius-lg)] border border-dashed border-[var(--border)] p-3">
        <div className="flex flex-wrap items-center gap-2">
          <input value={seuil} onChange={(e) => setSeuil(e.target.value)} type="number" placeholder="Score seuil" className="w-28 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm tabular-nums" />
          <select value={type} onChange={(e) => setType(e.target.value as "hausse" | "nouvelle_carte")} className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm">
            <option value="hausse">Demander une augmentation</option>
            <option value="nouvelle_carte">Ouvrir une nouvelle carte</option>
          </select>
          <input value={montant} onChange={(e) => setMontant(e.target.value)} type="number" placeholder="Montant estimé" className="w-32 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm tabular-nums" />
          <button onClick={submit} className="flex items-center gap-1.5 rounded-lg bg-[var(--ring)] px-3 py-1.5 text-sm font-medium text-white">
            <Plus size={14} /> Ajouter
          </button>
        </div>
      </div>
    </div>
  );
}

function RoadmapSection({ actions, projectionPossible }: { actions: CreditPlanAction[]; projectionPossible: boolean }) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold text-[var(--muted-foreground)]">Prochaines actions prévues</p>
      {!projectionPossible ? (
        <p className="text-xs text-[var(--muted-foreground)]">Ajoute au moins 2 points de score pour voir les actions prévues.</p>
      ) : actions.length === 0 ? (
        <p className="text-xs text-[var(--muted-foreground)]">Aucune action prévue avant la date cible avec les règles actuelles.</p>
      ) : (
        <ol className="space-y-2">
          {actions.map((a, i) => (
            <li key={i} className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-[var(--foreground)]">
                  {fmtMonthYear(a.date)} · {a.type === "hausse" ? "Demander une augmentation" : "Ouvrir une nouvelle carte"} (score {a.seuil_score})
                </span>
                <span className="shrink-0 tabular-nums text-[var(--success-foreground)]">+{cad(a.montant_estime)}</span>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
