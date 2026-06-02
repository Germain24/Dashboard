"use client";

import { useEffect, useState, useCallback } from "react";
import { financeApi, type PositionManuelle, type PositionCreate } from "@/lib/finance";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";

function fmt(n?: number | null, dec = 2) {
  if (n == null) return "—";
  return n.toLocaleString("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

const EMPTY_FORM: PositionCreate = { ticker: "", quantite: 0, pmu: undefined, devise: "EUR", broker: "" };

export function PortefeuilleTab() {
  const [positions, setPositions] = useState<PositionManuelle[]>([]);
  const [enriched, setEnriched] = useState<Record<string, { prix_actuel: number; valeur: number; pl: number; pl_pct: number }>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<PositionCreate>(EMPTY_FORM);
  const [editId, setEditId] = useState<number | null>(null);
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [pos, enrichedPos] = await Promise.all([
        financeApi.positionsList(),
        financeApi.portfolio(),
      ]);
      setPositions(pos);
      const map: typeof enriched = {};
      for (const p of enrichedPos) {
        map[`${p.ticker}__${p.broker ?? "default"}`] = {
          prix_actuel: p.prix_actuel,
          valeur: p.valeur_actuelle,
          pl: p.pl_latent,
          pl_pct: p.pl_pct,
        };
      }
      setEnriched(map);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleEdit = (p: PositionManuelle) => {
    setForm({ ticker: p.ticker, quantite: p.quantite, pmu: p.pmu, devise: p.devise, broker: p.broker ?? "" });
    setEditId(p.id);
    setShowForm(true);
  };

  const handleDelete = async (id: number, ticker: string) => {
    if (!confirm(`Supprimer la position ${ticker} ?`)) return;
    try {
      await financeApi.positionDelete(id);
      await load();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur suppression"); }
  };

  const handleSubmit = async () => {
    if (!form.ticker || form.quantite <= 0) { setError("Ticker et quantité obligatoires"); return; }
    setSaving(true); setError(null);
    try {
      if (editId !== null) {
        await financeApi.positionUpdate(editId, form);
      } else {
        await financeApi.positionCreate(form);
      }
      setForm(EMPTY_FORM); setEditId(null); setShowForm(false);
      await load();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur sauvegarde"); }
    finally { setSaving(false); }
  };

  const totalValeur = Object.values(enriched).reduce((s, p) => s + p.valeur, 0);
  const totalPl = Object.values(enriched).reduce((s, p) => s + p.pl, 0);

  if (loading) return <Spinner label="Chargement positions..." />;

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-[var(--destructive)]">⚠ {error}</p>}

      {/* Résumé */}
      {positions.length > 0 && (
        <div className="flex gap-4 flex-wrap">
          <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-3 flex-1 min-w-32">
            <p className="text-xs text-[var(--muted-foreground)]">Valeur totale</p>
            <p className="text-base font-semibold">{fmt(totalValeur)} €</p>
          </div>
          <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-3 flex-1 min-w-32">
            <p className="text-xs text-[var(--muted-foreground)]">P&L latent</p>
            <p className={`text-base font-semibold ${totalPl >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"}`}>
              {totalPl >= 0 ? "+" : ""}{fmt(totalPl)} €
            </p>
          </div>
          <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-3 flex-1 min-w-32">
            <p className="text-xs text-[var(--muted-foreground)]">Positions</p>
            <p className="text-base font-semibold">{positions.length}</p>
          </div>
        </div>
      )}

      {/* Bouton ajouter */}
      <div className="flex justify-end">
        <Button variant="default" size="sm" onClick={() => { setForm(EMPTY_FORM); setEditId(null); setShowForm(true); }}>
          + Ajouter une position
        </Button>
      </div>

      {/* Formulaire ajout/édition */}
      {showForm && (
        <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4 space-y-3 bg-[var(--muted)]">
          <p className="text-sm font-semibold">{editId !== null ? "Modifier la position" : "Nouvelle position"}</p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {[
              { label: "Ticker *", key: "ticker", type: "text", placeholder: "ex: CW8.PA" },
              { label: "Quantité *", key: "quantite", type: "number", placeholder: "0" },
              { label: "PMU (€)", key: "pmu", type: "number", placeholder: "prix moyen" },
              { label: "Devise", key: "devise", type: "text", placeholder: "EUR" },
              { label: "Broker", key: "broker", type: "text", placeholder: "Trading212…" },
            ].map(f => (
              <div key={f.key}>
                <label className="text-xs text-[var(--muted-foreground)]">{f.label}</label>
                <input
                  type={f.type}
                  placeholder={f.placeholder}
                  value={(form as unknown as Record<string, unknown>)[f.key] as string ?? ""}
                  onChange={e => setForm(prev => ({ ...prev, [f.key]: f.type === "number" ? parseFloat(e.target.value) || 0 : e.target.value }))}
                  className="w-full mt-1 px-2 py-1.5 text-sm rounded-[var(--radius)] border border-[var(--border)]
                             bg-[var(--background)] focus:outline-none focus:ring-1 focus:ring-[var(--ring)]"
                />
              </div>
            ))}
          </div>
          <div className="flex gap-2 justify-end">
            <Button variant="ghost" size="sm" onClick={() => { setShowForm(false); setEditId(null); }}>Annuler</Button>
            <Button variant="default" size="sm" onClick={handleSubmit} disabled={saving}>
              {saving ? "Sauvegarde..." : editId !== null ? "Mettre à jour" : "Ajouter"}
            </Button>
          </div>
        </div>
      )}

      {/* Table des positions */}
      {!positions.length ? (
        <EmptyState title="Aucune position" description="Ajoutez votre première position pour commencer le suivi." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-xs text-[var(--muted-foreground)] text-left">
                <th className="pb-1 pr-3">Ticker</th>
                <th className="pb-1 pr-3">Broker</th>
                <th className="pb-1 pr-3 text-right">Qté</th>
                <th className="pb-1 pr-3 text-right">PMU</th>
                <th className="pb-1 pr-3 text-right">Prix actuel</th>
                <th className="pb-1 pr-3 text-right">Valeur</th>
                <th className="pb-1 pr-3 text-right">P&L</th>
                <th className="pb-1 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {positions.map(p => {
                const key = `${p.ticker}__${p.broker ?? "default"}`;
                const live = enriched[key];
                return (
                  <tr key={p.id} className="border-b border-[var(--border)] hover:bg-[var(--muted)] transition-colors">
                    <td className="py-1.5 pr-3 font-mono font-semibold text-xs">{p.ticker}</td>
                    <td className="py-1.5 pr-3 text-xs text-[var(--muted-foreground)]">{p.broker ?? "—"}</td>
                    <td className="py-1.5 pr-3 text-right">{fmt(p.quantite, 4)}</td>
                    <td className="py-1.5 pr-3 text-right text-xs">{p.pmu ? `${fmt(p.pmu)} €` : "—"}</td>
                    <td className="py-1.5 pr-3 text-right text-xs">{live ? `${fmt(live.prix_actuel)} €` : "—"}</td>
                    <td className="py-1.5 pr-3 text-right font-medium">{live ? `${fmt(live.valeur)} €` : "—"}</td>
                    <td className={`py-1.5 pr-3 text-right text-xs ${live && live.pl >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"}`}>
                      {live ? `${live.pl >= 0 ? "+" : ""}${fmt(live.pl)} €` : "—"}
                    </td>
                    <td className="py-1.5 text-right">
                      <div className="flex gap-1 justify-end">
                        <button onClick={() => handleEdit(p)}
                          className="text-xs px-2 py-0.5 rounded border border-[var(--border)] hover:bg-[var(--muted)]">
                          ✏
                        </button>
                        <button onClick={() => handleDelete(p.id, p.ticker)}
                          className="text-xs px-2 py-0.5 rounded border border-[var(--destructive)] text-[var(--destructive)] hover:bg-[var(--destructive)] hover:text-white">
                          ✕
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
