"use client";

import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  Plus,
  RefreshCw,
  Search,
  Upload,
  X,
} from "lucide-react";
import {
  financeApi,
  type ImportResult,
  type TransactionCreate,
  type TransactionOut,
  type TransactionType,
} from "@/lib/finance";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";

const PAGE_SIZE = 100;

type IncomeSummary = Awaited<ReturnType<typeof financeApi.dividendes>>;

const newTransaction = (): TransactionCreate => ({
  ticker: "",
  type_transaction: "achat",
  date_transaction: new Date().toISOString().slice(0, 10),
  quantite: 0,
  prix_unitaire: 0,
  frais: 0,
  devise: "EUR",
});

const money = (value: number, currency = "EUR") =>
  new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);

const quantity = (value: number) =>
  value.toLocaleString("fr-FR", { maximumFractionDigits: 6 });

export function TransactionsTab() {
  const [page, setPage] = useState(0);
  const [filterDraft, setFilterDraft] = useState("");
  const [tickerFilter, setTickerFilter] = useState("");
  const [form, setForm] = useState<TransactionCreate>(newTransaction);
  const [showForm, setShowForm] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const dataQuery = useQuery({
    queryKey: ["finance", "transactions-page", page, tickerFilter],
    queryFn: async () => {
      const [result, incomeResult] = await Promise.all([
        financeApi.transactionsPage({
          ticker: tickerFilter || undefined,
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
        }),
        financeApi.dividendes(),
      ]);
      return { result, income: incomeResult };
    },
    placeholderData: (previous) => previous,
  });
  const transactions = dataQuery.data?.result.items ?? [];
  const total = dataQuery.data?.result.total ?? 0;
  const income: IncomeSummary | null = dataQuery.data?.income ?? null;
  const queryError = dataQuery.error instanceof Error ? dataQuery.error.message : null;
  const error = actionError ?? queryError;

  const update = (key: keyof TransactionCreate, value: string | number | null) =>
    setForm((current) => ({ ...current, [key]: value }));

  const changeType = (type: TransactionType) => {
    const cashType = ["interet", "depot", "retrait", "frais"].includes(type);
    setForm((current) => ({
      ...current,
      type_transaction: type,
      ticker: cashType ? "CASH" : current.ticker === "CASH" ? "" : current.ticker,
      quantite: cashType || type === "dividende" ? 1 : current.quantite,
      montant_brut: type === "dividende" || type === "interet" ? current.montant_brut ?? 0 : null,
      retenue_source: type === "dividende" ? current.retenue_source ?? 0 : 0,
    }));
  };

  const handleSave = async () => {
    const type = form.type_transaction;
    const isIncome = type === "dividende" || type === "interet";
    const isCash = isIncome || ["depot", "retrait", "frais"].includes(type);
    const gross = Number(form.montant_brut ?? form.prix_unitaire);
    const payload: TransactionCreate = {
      ...form,
      ticker: form.ticker.trim().toUpperCase(),
      quantite: isCash ? 1 : form.quantite,
      prix_unitaire: isIncome ? gross : form.prix_unitaire,
      montant_brut: isIncome ? gross : null,
    };
    if (!payload.ticker || payload.quantite <= 0 || payload.prix_unitaire < 0) {
      setActionError("Complétez le ticker, la quantité et le montant avec des valeurs valides.");
      return;
    }
    if ((payload.retenue_source ?? 0) > gross) {
      setActionError("La retenue à la source ne peut pas dépasser le montant brut.");
      return;
    }

    setSaving(true);
    setActionError(null);
    try {
      await financeApi.createTransaction(payload);
      setForm(newTransaction());
      setShowForm(false);
      if (page !== 0) setPage(0);
      else await dataQuery.refetch();
    } catch (caught: unknown) {
      setActionError(caught instanceof Error ? caught.message : "Erreur de création");
    } finally {
      setSaving(false);
    }
  };

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setImportResult(null);
    setActionError(null);
    try {
      const result = await financeApi.importCsv(file);
      setImportResult(result);
      if (page !== 0) setPage(0);
      else await dataQuery.refetch();
    } catch (caught: unknown) {
      setActionError(caught instanceof Error ? caught.message : "Erreur d'import");
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const maxPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1);
  const isIncome = form.type_transaction === "dividende" || form.type_transaction === "interet";
  const isCash = isIncome || ["depot", "retrait", "frais"].includes(form.type_transaction);

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Metric label="Transactions enregistrées" value={total.toLocaleString("fr-FR")} />
        <Metric label="Dividendes nets" value={money(income?.total_recu ?? 0)} />
        <Metric label="Intérêts nets" value={money(income?.interets_recus ?? 0)} />
      </div>

      {error && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius)] border border-[var(--destructive)]/30 bg-[var(--destructive-muted)]/25 p-3 text-sm text-[var(--destructive)]">
          <span className="flex items-center gap-2"><AlertTriangle className="h-4 w-4" aria-hidden />{error}</span>
          <Button size="sm" variant="ghost" onClick={() => void dataQuery.refetch()}><RefreshCw className="h-3.5 w-3.5" aria-hidden />Réessayer</Button>
        </div>
      )}

      {importResult && (
        <div className="rounded-[var(--radius)] border border-[var(--success)]/25 bg-[var(--success-muted)]/35 p-3 text-sm text-[var(--success-foreground)]">
          Import terminé : {importResult.imported} ajoutée{importResult.imported > 1 ? "s" : ""}, {importResult.updated} mise{importResult.updated > 1 ? "s" : ""} à jour, {importResult.skipped} inchangée{importResult.skipped > 1 ? "s" : ""}.
          {importResult.errors.length > 0 && <span className="ml-1 text-[var(--destructive)]">{importResult.errors.length} erreur{importResult.errors.length > 1 ? "s" : ""}.</span>}
        </div>
      )}

      <div className="flex flex-col gap-3 border-y border-[var(--glass-border)] py-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => setShowForm((visible) => !visible)}>
            {showForm ? <X className="h-3.5 w-3.5" aria-hidden /> : <Plus className="h-3.5 w-3.5" aria-hidden />}
            {showForm ? "Fermer" : "Ajouter"}
          </Button>
          <Button size="sm" variant="secondary" onClick={() => fileRef.current?.click()} loading={importing}>
            <Upload className="h-3.5 w-3.5" aria-hidden />Importer un CSV
          </Button>
          <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(event) => void handleImport(event)} aria-label="Importer un relevé CSV" />
        </div>

        <form
          className="flex w-full gap-2 lg:w-auto"
          onSubmit={(event) => {
            event.preventDefault();
            setPage(0);
            setTickerFilter(filterDraft.trim().toUpperCase());
          }}
        >
          <label className="relative min-w-0 flex-1 lg:w-64">
            <span className="sr-only">Rechercher un ticker</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--muted-foreground)]" aria-hidden />
            <input value={filterDraft} onChange={(event) => setFilterDraft(event.target.value)} placeholder="Rechercher un ticker" className="glass-inset h-8 w-full rounded-[var(--radius)] border border-[var(--border)] pl-9 pr-3 text-xs uppercase outline-none focus-visible:border-[var(--ring)]" />
          </label>
          <Button size="sm" variant="secondary" type="submit">Filtrer</Button>
          {tickerFilter && (
            <Button size="icon" variant="ghost" type="button" aria-label="Effacer le filtre" title="Effacer le filtre" onClick={() => { setFilterDraft(""); setTickerFilter(""); setPage(0); }}>
              <X className="h-4 w-4" aria-hidden />
            </Button>
          )}
        </form>
      </div>

      {showForm && (
        <section className="glass-card rounded-[var(--radius-lg)] p-4 animate-fade-in">
          <div className="mb-4 flex items-center gap-2">
            <CircleDollarSign className="h-4 w-4 text-[var(--muted-foreground)]" aria-hidden />
            <h3 className="text-sm font-semibold">Nouvelle transaction</h3>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Select label="Type" value={form.type_transaction} onChange={(event) => changeType(event.target.value as TransactionType)}>
              <option value="achat">Achat</option>
              <option value="vente">Vente</option>
              <option value="dividende">Dividende</option>
              <option value="interet">Intérêt sur espèces</option>
              <option value="depot">Dépôt</option>
              <option value="retrait">Retrait</option>
              <option value="frais">Frais isolé</option>
            </Select>
            <Input label="Date" type="date" value={form.date_transaction} onChange={(event) => update("date_transaction", event.target.value)} />
            <Input label="Ticker" value={form.ticker} disabled={isCash && form.type_transaction !== "dividende"} onChange={(event) => update("ticker", event.target.value.toUpperCase())} />
            <Input label="Courtier" value={form.broker ?? ""} onChange={(event) => update("broker", event.target.value)} />

            {!isCash && (
              <>
                <Input label="Quantité" type="number" min="0" step="any" value={form.quantite} onChange={(event) => update("quantite", Number(event.target.value))} />
                <Input label="Prix unitaire" type="number" min="0" step="any" value={form.prix_unitaire} onChange={(event) => update("prix_unitaire", Number(event.target.value))} />
              </>
            )}
            {isIncome ? (
              <Input label="Montant brut" type="number" min="0" step="0.01" value={form.montant_brut ?? 0} onChange={(event) => update("montant_brut", Number(event.target.value))} />
            ) : isCash ? (
              <Input label="Montant" type="number" min="0" step="0.01" value={form.prix_unitaire} onChange={(event) => update("prix_unitaire", Number(event.target.value))} />
            ) : null}
            {form.type_transaction === "dividende" && (
              <Input label="Retenue à la source" type="number" min="0" step="0.01" value={form.retenue_source ?? 0} onChange={(event) => update("retenue_source", Number(event.target.value))} />
            )}
            {(form.type_transaction === "achat" || form.type_transaction === "vente" || isIncome) && (
              <Input label="Frais" type="number" min="0" step="0.01" value={form.frais ?? 0} onChange={(event) => update("frais", Number(event.target.value))} />
            )}
            <Input label="Devise" value={form.devise ?? "EUR"} onChange={(event) => update("devise", event.target.value.toUpperCase())} />
          </div>
          <div className="mt-4 flex gap-2 border-t border-[var(--glass-border)] pt-3">
            <Button size="sm" onClick={() => void handleSave()} loading={saving}>Enregistrer</Button>
            <Button size="sm" variant="ghost" onClick={() => { setForm(newTransaction()); setShowForm(false); }}>Annuler</Button>
          </div>
        </section>
      )}

      {dataQuery.isLoading ? (
        <div className="grid min-h-64 place-items-center"><Spinner label="Chargement des transactions" /></div>
      ) : transactions.length === 0 ? (
        <EmptyState title={tickerFilter ? "Aucun résultat" : "Aucune transaction"} description={tickerFilter ? "Aucune transaction ne correspond à ce ticker." : "Importez un relevé CSV ou ajoutez une opération."} />
      ) : (
        <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--glass-border)]">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-[var(--field)] text-left text-xs text-[var(--muted-foreground)]">
                <tr>
                  <th className="px-3 py-2 font-medium">Date</th>
                  <th className="px-3 py-2 font-medium">Titre</th>
                  <th className="px-3 py-2 font-medium">Type</th>
                  <th className="px-3 py-2 text-right font-medium">Quantité</th>
                  <th className="px-3 py-2 text-right font-medium">Montant net</th>
                  <th className="px-3 py-2 text-right font-medium">Frais / retenue</th>
                  <th className="px-3 py-2 font-medium">Courtier</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((transaction) => {
                  const net = transactionNetAmount(transaction);
                  const deductions = (transaction.frais ?? 0) + (transaction.retenue_source ?? 0);
                  return (
                    <tr key={transaction.id} className="border-t border-[var(--glass-border)] transition-colors hover:bg-[var(--accent)]/45">
                      <td className="whitespace-nowrap px-3 py-2.5 text-xs">{transaction.date.slice(0, 10)}</td>
                      <td className="px-3 py-2.5 font-mono text-xs font-medium">{transaction.ticker}</td>
                      <td className="px-3 py-2.5"><TransactionBadge type={transaction.type} /></td>
                      <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums">{["achat", "vente"].includes(transaction.type) ? quantity(transaction.quantite) : "-"}</td>
                      <td className="px-3 py-2.5 text-right font-mono text-xs font-medium tabular-nums">{money(net, transaction.devise)}</td>
                      <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums text-[var(--muted-foreground)]">{deductions > 0 ? money(deductions, transaction.devise) : "-"}</td>
                      <td className="px-3 py-2.5 text-xs text-[var(--muted-foreground)]">{transaction.broker ?? "-"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-[var(--glass-border)] bg-[var(--field)]/45 px-3 py-2">
            <span className="text-xs text-[var(--muted-foreground)]">{page * PAGE_SIZE + 1}-{Math.min((page + 1) * PAGE_SIZE, total)} sur {total}</span>
            <div className="flex gap-1">
              <Button size="icon" variant="ghost" aria-label="Page précédente" title="Page précédente" disabled={page === 0} onClick={() => setPage((current) => Math.max(0, current - 1))}><ChevronLeft className="h-4 w-4" aria-hidden /></Button>
              <Button size="icon" variant="ghost" aria-label="Page suivante" title="Page suivante" disabled={page >= maxPage} onClick={() => setPage((current) => Math.min(maxPage, current + 1))}><ChevronRight className="h-4 w-4" aria-hidden /></Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass-card rounded-[var(--radius-lg)] p-4">
      <span className="text-xs text-[var(--muted-foreground)]">{label}</span>
      <strong className="mt-1 block font-mono text-lg tabular-nums">{value}</strong>
    </div>
  );
}

function transactionNetAmount(transaction: TransactionOut): number {
  const gross = transaction.montant_brut ?? transaction.quantite * transaction.prix_unitaire;
  const fees = transaction.frais ?? 0;
  const withholding = transaction.retenue_source ?? 0;
  if (transaction.type === "achat") return -(gross + fees);
  if (transaction.type === "retrait" || transaction.type === "frais") return -gross;
  return gross - fees - withholding;
}

function TransactionBadge({ type }: { type: string }) {
  const variant = type === "achat" || type === "depot"
    ? "success"
    : type === "vente" || type === "retrait" || type === "frais"
      ? "destructive"
      : type === "interet"
        ? "warning"
        : "info";
  const labels: Record<string, string> = {
    achat: "Achat",
    vente: "Vente",
    dividende: "Dividende",
    interet: "Intérêt",
    depot: "Dépôt",
    retrait: "Retrait",
    frais: "Frais",
  };
  return <Badge variant={variant}>{labels[type] ?? type}</Badge>;
}
