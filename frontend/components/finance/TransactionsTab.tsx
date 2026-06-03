"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  financeApi, type TransactionOut, type TransactionCreate, type ImportResult,
} from "@/lib/finance";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";

function fmt(n: number) {
  return n.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const EMPTY_TX: TransactionCreate = {
  ticker: "", type_transaction: "ACHAT", date_transaction: new Date().toISOString().slice(0, 10),
  quantite: 0, prix_unitaire: 0, frais: 0, devise: "EUR",
};

export function TransactionsTab() {
  const [txs, setTxs] = useState<TransactionOut[]>([]);
  const [form, setForm] = useState<TransactionCreate>(EMPTY_TX);
  const [showForm, setShowForm] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [div, setDiv] = useState<{ total_recu: number; n_versements: number } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      setTxs(await financeApi.transactions());
      financeApi.dividendes().then(setDiv).catch(() => {});
    }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur réseau"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    setSaving(true); setError(null);
    try {
      await financeApi.createTransaction(form);
      setForm(EMPTY_TX); setShowForm(false); await load();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur création"); }
    finally { setSaving(false); }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return;
    setImporting(true); setImportResult(null); setError(null);
    try {
      const r = await financeApi.importCsv(file);
      setImportResult(r); await load();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur import"); }
    finally { setImporting(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const up = (k: keyof TransactionCreate, v: string | number) =>
    setForm(f => ({ ...f, [k]: v }));

  if (loading) return <Spinner label="Chargement transactions..." />;

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-[var(--destructive)]">⚠ {error}</p>}
      {div && div.n_versements > 0 && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm flex items-center gap-2 flex-wrap">
          <span className="text-[var(--muted-foreground)]">💰 Dividendes reçus</span>
          <span className="font-mono font-semibold text-[var(--success)]">
            {div.total_recu.toLocaleString("fr-CA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €
          </span>
          <span className="text-xs text-[var(--muted-foreground)]">· {div.n_versements} versement{div.n_versements > 1 ? "s" : ""}</span>
        </div>
      )}
      {importResult && (
        <div className="text-sm p-3 rounded-[var(--radius)] bg-[var(--success-muted)] text-[var(--success-foreground)]">
          Import : {importResult.imported} importées, {importResult.skipped} ignorées
          {importResult.errors.length > 0 && ` · ${importResult.errors.length} erreur(s)`}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 flex-wrap">
        <Button size="sm" onClick={() => setShowForm(v => !v)}>
          {showForm ? "Annuler" : "+ Ajouter manuellement"}
        </Button>
        <Button size="sm" variant="secondary"
          onClick={() => fileRef.current?.click()} disabled={importing}>
          {importing ? "Import..." : "📥 Importer CSV broker"}
        </Button>
        <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleImport} />
      </div>

      {/* Manual form */}
      {showForm && (
        <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4 space-y-3">
          <h3 className="text-sm font-semibold">Nouvelle transaction</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <Input label="Ticker *" value={form.ticker}
              onChange={e => up("ticker", e.target.value.toUpperCase())} />
            <Select label="Type *" value={form.type_transaction}
              onChange={e => up("type_transaction", e.target.value)}>
              <option value="ACHAT">ACHAT</option>
              <option value="VENTE">VENTE</option>
              <option value="DIVIDENDE">DIVIDENDE</option>
            </Select>
            <Input label="Date *" type="date" value={form.date_transaction}
              onChange={e => up("date_transaction", e.target.value)} />
            <Input label="Quantité *" type="number" value={form.quantite}
              onChange={e => up("quantite", parseFloat(e.target.value) || 0)} />
            <Input label="Prix unitaire *" type="number" value={form.prix_unitaire}
              onChange={e => up("prix_unitaire", parseFloat(e.target.value) || 0)} />
            <Input label="Frais" type="number" value={form.frais}
              onChange={e => up("frais", parseFloat(e.target.value) || 0)} />
            <Input label="Devise" value={form.devise ?? "EUR"}
              onChange={e => up("devise", e.target.value)} />
            <Input label="Broker" value={form.broker ?? ""}
              onChange={e => up("broker", e.target.value)} />
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={handleSave} disabled={saving || !form.ticker}>
              {saving ? "Enregistrement..." : "Enregistrer"}
            </Button>
          </div>
        </div>
      )}

      {/* Table */}
      {!txs.length ? (
        <EmptyState title="Aucune transaction" description="Importez un CSV broker ou saisissez manuellement." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-xs text-[var(--muted-foreground)] text-left">
                <th className="pb-1 pr-3">Date</th>
                <th className="pb-1 pr-3">Ticker</th>
                <th className="pb-1 pr-3">Type</th>
                <th className="pb-1 pr-3 text-right">Qté</th>
                <th className="pb-1 pr-3 text-right">Prix</th>
                <th className="pb-1 pr-3 text-right">Total</th>
                <th className="pb-1">Broker</th>
              </tr>
            </thead>
            <tbody>
              {txs.map(t => (
                <tr key={t.id} className="border-b border-[var(--border)] hover:bg-[var(--muted)]">
                  <td className="py-1.5 pr-3 text-xs">{t.date_transaction}</td>
                  <td className="py-1.5 pr-3 font-mono text-xs">{t.ticker}</td>
                  <td className="py-1.5 pr-3">
                    <Badge variant={t.type_transaction === "ACHAT" ? "success"
                      : t.type_transaction === "VENTE" ? "destructive" : "info"}>
                      {t.type_transaction}
                    </Badge>
                  </td>
                  <td className="py-1.5 pr-3 text-right">{fmt(t.quantite)}</td>
                  <td className="py-1.5 pr-3 text-right">{fmt(t.prix_unitaire)} {t.devise}</td>
                  <td className="py-1.5 pr-3 text-right font-medium">
                    {fmt(t.quantite * t.prix_unitaire + t.frais)} {t.devise}
                  </td>
                  <td className="py-1.5 text-xs text-[var(--muted-foreground)]">{t.broker ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
