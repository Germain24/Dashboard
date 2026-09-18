"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowDownLeft, ArrowUpRight, Download, Pencil, Upload, Wand2 } from "lucide-react";
import {
  useBudgetCategories,
  useBudgetTransactions,
  useImportCsv,
  useSetTransactionTags,
  useRuleSuggestions,
  useLearnRules,
  useSetTransactionCategory,
} from "@/lib/queries/budget";
import type { BudgetCategory } from "@/lib/budget";
import {
  categoryDescendantIds,
  categoryPathLabel,
  flattenCategoryOptions,
} from "@/lib/budget-categories";
import BudgetCategoryEditor from "./BudgetCategoryEditor";

const formatCAD = (v: number) =>
  new Intl.NumberFormat("fr-CA", { style: "currency", currency: "CAD" }).format(v ?? 0);

type BudgetTransaction = {
  id: number;
  date?: string | null;
  montant: number;
  marchand?: string | null;
  description?: string | null;
  compte?: string | null;
  category_id?: number | null;
  tags?: string[] | null;
};

export default function TransactionsTab() {
  const [msg, setMsg] = useState<string | null>(null);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [searchFilter, setSearchFilter] = useState("");
  const [tagFilter, setTagFilter] = useState(""); // '' tous · '__none__' sans tag · tag
  const [catFilter, setCatFilter] = useState(""); // '' tous · 'none' sans catégorie · famille
  const [subcatFilter, setSubcatFilter] = useState("");
  const [bankFilter, setBankFilter] = useState(""); // '' toutes · nom de banque
  const [typeFilter, setTypeFilter] = useState(""); // '' tous · 'credit' · 'debit'
  const [directionFilter, setDirectionFilter] = useState(""); // '' tous · 'income' · 'expense'
  const [sortBy, setSortBy] = useState("date-desc");
  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingCategoryId == null) return;
    const frame = window.requestAnimationFrame(() => {
      const categorySelects = Array.from(
        document.querySelectorAll<HTMLSelectElement>(
          `select[data-category-select-id="${editingCategoryId}"]`,
        ),
      );
      const visibleSelect = categorySelects.find((select) => select.offsetParent !== null);
      (visibleSelect ?? categorySelects[0])?.focus();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [editingCategoryId]);

  const txsQ = useBudgetTransactions({ from: fromDate || undefined, to: toDate || undefined });
  const categoriesQ = useBudgetCategories();
  const txs: BudgetTransaction[] = Array.isArray(txsQ.data)
    ? (txsQ.data as BudgetTransaction[])
    : [];
  const categories = (Array.isArray(categoriesQ.data) ? categoriesQ.data : []) as BudgetCategory[];
  const categoryOptions = flattenCategoryOptions(categories);
  const categoryRoots = categories.filter((category) => category.parent_id == null);
  const selectedCategory = catFilter && catFilter !== "none" ? Number(catFilter) : null;
  const selectedSubcategory = subcatFilter ? Number(subcatFilter) : null;
  const descendants =
    selectedCategory == null ? null : categoryDescendantIds(categories, selectedCategory);
  const subcategoryDescendants =
    selectedSubcategory == null ? null : categoryDescendantIds(categories, selectedSubcategory);
  const subcategories =
    selectedCategory == null
      ? []
      : categoryOptions.filter(
          ({ category }) => category.id !== selectedCategory && descendants?.has(category.id),
        );
  const loading = txsQ.isLoading || categoriesQ.isLoading;

  const bankOf = (t: BudgetTransaction) => (t.compte ?? "").split("-")[0] || "";
  const typeOf = (t: BudgetTransaction) => (t.compte ?? "").split("-")[1] || "";
  const allTags = Array.from(new Set(txs.flatMap((t) => t.tags ?? []))).sort();
  const banks = Array.from(new Set(txs.map(bankOf).filter(Boolean))).sort();
  const types = Array.from(new Set(txs.map(typeOf).filter(Boolean))).sort();
  const TYPE_LABEL: Record<string, string> = { credit: "Crédit", debit: "Débit" };
  const BANK_LABEL: Record<string, string> = {
    banquepopulaire: "Banque Populaire",
    desjardins: "Desjardins",
    wise: "Wise",
    westpac: "Westpac",
  };
  const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

  const filtered = txs.filter((t) => {
    const tags = t.tags ?? [];
    if (fromDate && (t.date ?? "") < fromDate) return false;
    if (toDate && (t.date ?? "") > toDate) return false;
    if (
      searchFilter.trim() &&
      !`${t.marchand ?? ""} ${t.description ?? ""}`
        .toLocaleLowerCase("fr-CA")
        .includes(searchFilter.trim().toLocaleLowerCase("fr-CA"))
    )
      return false;
    if (tagFilter === "__none__" && tags.length > 0) return false;
    if (tagFilter && tagFilter !== "__none__" && !tags.includes(tagFilter)) return false;
    if (catFilter === "none" && t.category_id != null) return false;
    if (descendants && !descendants.has(t.category_id ?? -1)) return false;
    if (subcategoryDescendants && !subcategoryDescendants.has(t.category_id ?? -1)) return false;
    if (bankFilter && bankOf(t) !== bankFilter) return false;
    if (typeFilter && typeOf(t) !== typeFilter) return false;
    if (directionFilter === "income" && t.montant <= 0) return false;
    if (directionFilter === "expense" && t.montant >= 0) return false;
    return true;
  });
  const SORTERS: Record<string, (a: BudgetTransaction, b: BudgetTransaction) => number> = {
    "date-desc": (a, b) => (b.date ?? "").localeCompare(a.date ?? ""),
    "date-asc": (a, b) => (a.date ?? "").localeCompare(b.date ?? ""),
    "amount-desc": (a, b) => Math.abs(b.montant) - Math.abs(a.montant),
    "amount-asc": (a, b) => Math.abs(a.montant) - Math.abs(b.montant),
    alpha: (a, b) => (a.marchand ?? "").localeCompare(b.marchand ?? ""),
  };
  const visible = [...filtered].sort(SORTERS[sortBy] ?? SORTERS["date-desc"]);
  const anyFilter = !!(
    fromDate ||
    toDate ||
    searchFilter ||
    tagFilter ||
    catFilter ||
    subcatFilter ||
    bankFilter ||
    typeFilter ||
    directionFilter
  );
  const filteredDep = filtered.filter((t) => t.montant < 0).reduce((s, t) => s + -t.montant, 0);
  const tagsMutation = useSetTransactionTags();
  const categoryMutation = useSetTransactionCategory();
  const importMutation = useImportCsv();
  const importing = importMutation.isPending;

  const catName = (id: number | null) => categoryPathLabel(categories, id);

  // Tags multiples (#119)
  const addTag = (tx: BudgetTransaction) => {
    const tag = window.prompt("Nouveau tag :")?.trim();
    if (!tag) return;
    tagsMutation.mutate({ id: tx.id, tags: [...(tx.tags ?? []), tag] });
  };
  const removeTag = (tx: BudgetTransaction, tag: string) => {
    tagsMutation.mutate({ id: tx.id, tags: (tx.tags ?? []).filter((t: string) => t !== tag) });
  };
  const transactionLabel = (tx: BudgetTransaction) =>
    tx.marchand || tx.description || "la transaction";

  const renderCategoryControl = (tx: BudgetTransaction, compact = false) => {
    const label = transactionLabel(tx);
    if (editingCategoryId === tx.id) {
      return (
        <select
          data-category-select-id={tx.id}
          value={tx.category_id == null ? "" : String(tx.category_id)}
          disabled={categoryMutation.isPending}
          aria-label={`Catégorie de ${label}`}
          onChange={(event) => {
            const value = event.target.value;
            categoryMutation.mutate(
              { id: tx.id, category_id: value ? Number(value) : null },
              {
                onSuccess: () => setEditingCategoryId(null),
                onError: () =>
                  setMsg("La catégorie de cette transaction n’a pas pu être modifiée."),
              },
            );
          }}
          className={
            compact
              ? "mt-1 min-h-11 w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-left text-xs text-[var(--foreground)]"
              : "max-w-[240px] rounded border border-[var(--border)] bg-[var(--background)] px-1.5 py-0.5 text-xs text-[var(--foreground)]"
          }
        >
          <option value="">Sans catégorie</option>
          {categoryOptions.map(({ category, label: categoryLabel }) => (
            <option key={category.id} value={String(category.id)}>
              {categoryLabel}
            </option>
          ))}
        </select>
      );
    }

    return (
      <button
        type="button"
        onClick={() => setEditingCategoryId(tx.id)}
        title="Modifier la catégorie"
        aria-label={`Modifier la catégorie de ${label}`}
        className={
          compact
            ? "mt-1 flex min-h-11 w-full items-center justify-between gap-2 rounded-md border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-left text-xs font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            : "inline-flex items-center gap-1 rounded px-1 py-0.5 text-left underline decoration-dotted underline-offset-2 transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
        }
      >
        <span className={compact ? "min-w-0 break-words" : undefined}>
          {catName(tx.category_id ?? null)}
        </span>
        <Pencil size={compact ? 14 : 10} className="shrink-0" aria-hidden="true" />
      </button>
    );
  };

  const renderTagControls = (tx: BudgetTransaction, compact = false) => (
    <div
      className={
        compact
          ? "mt-1 flex flex-wrap items-center gap-1.5"
          : "mt-1 flex flex-wrap items-center gap-1"
      }
    >
      {(tx.tags ?? []).map((tag: string) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 rounded-[var(--radius-sm)] bg-[var(--muted)] pl-2 text-[10px] text-[var(--muted-foreground)]"
        >
          {tag}
          <button
            type="button"
            onClick={() => removeTag(tx, tag)}
            aria-label={`Retirer le tag ${tag} de ${transactionLabel(tx)}`}
            className={
              compact
                ? "inline-flex min-h-11 min-w-11 items-center justify-center rounded-[var(--radius-sm)] text-sm hover:bg-[var(--background)] hover:text-[var(--destructive)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                : "px-1 py-0.5 hover:text-[var(--destructive)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            }
          >
            ×
          </button>
        </span>
      ))}
      <select
        aria-label={`Ajouter un tag à ${transactionLabel(tx)}`}
        value=""
        onChange={(event) => {
          const value = event.target.value;
          event.target.value = "";
          if (!value) return;
          if (value === "__new__") {
            addTag(tx);
            return;
          }
          tagsMutation.mutate({ id: tx.id, tags: [...(tx.tags ?? []), value] });
        }}
        className={
          compact
            ? "min-h-11 rounded-md border border-dashed border-[var(--border)] px-3 py-2 text-xs text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
            : "rounded-[var(--radius-sm)] border border-dashed border-[var(--border)] px-1.5 py-0.5 text-[10px] text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
        }
      >
        <option value="">+ tag</option>
        {allTags
          .filter((tag) => !(tx.tags ?? []).includes(tag))
          .map((tag) => (
            <option key={tag} value={tag}>
              {tag}
            </option>
          ))}
        <option value="__new__">Nouveau tag…</option>
      </select>
    </div>
  );

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setMsg(null);
    importMutation.mutate(
      { file },
      {
        onSuccess: (r) => {
          setMsg(
            r?.imported != null
              ? `${r.imported} importée(s), ${r.categorised ?? 0} auto-catégorisée(s)${r.errors ? `, ${r.errors} erreur(s)` : ""}.`
              : "Import échoué.",
          );
        },
        onError: () => setMsg("Import échoué."),
        onSettled: () => {
          if (fileRef.current) fileRef.current.value = "";
        },
      },
    );
  };

  return (
    <div className="space-y-4 animate-fade-in-up">
      {/* Import des relevés bancaires (#115) */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div>
          <h2 className="text-sm font-semibold">Importer un relevé</h2>
          <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
            PDF (Desjardins, Banque Populaire, Westpac), Excel Wise, CSV ou OFX/QFX — catégorisation
            auto via tes règles.
          </p>
          {msg && <p className="mt-1 text-xs text-[var(--success)]">{msg}</p>}
        </div>
        <input
          ref={fileRef}
          id="csv-import"
          type="file"
          accept=".pdf,application/pdf,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,.csv,text/csv,.ofx,.qfx"
          onChange={onFile}
          className="hidden"
        />
        <div className="flex items-center gap-2">
          <a
            href={`/api/budget/export/annual?year=${new Date().getFullYear()}`}
            download
            className="inline-flex items-center gap-2 rounded-md border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-[var(--accent)]"
            title="Exporter les transactions de l'année en CSV (déclaration / bilan)"
          >
            <Download size={14} aria-hidden="true" />
            Export {new Date().getFullYear()}
          </a>
          <label
            htmlFor="csv-import"
            className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
          >
            <Upload size={14} aria-hidden="true" />
            {importing ? "Import…" : "Importer un relevé"}
          </label>
        </div>
        <BudgetCategoryEditor categories={categories} />
      </div>

      {/* Règles apprises de l'historique (#258) */}
      <LearnedRulesSection />

      {/* Liste des transactions */}
      <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] px-4 py-3">
          <h2 className="text-sm font-semibold">
            Transactions
            <span className="ml-2 text-xs font-normal text-[var(--muted-foreground)]">
              {visible.length}
              {anyFilter && <> · {formatCAD(filteredDep)} de dépenses</>}
            </span>
          </h2>
          <div className="flex flex-wrap items-center gap-1.5">
            <input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              aria-label="Date de début"
              title="Date de début"
              className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
            />
            <input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              aria-label="Date de fin"
              title="Date de fin"
              className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
            />
            <input
              type="search"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              aria-label="Rechercher un marchand ou un libellé"
              placeholder="Marchand / libellé"
              className="w-36 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
            />
            <select
              value={directionFilter}
              onChange={(e) => setDirectionFilter(e.target.value)}
              aria-label="Filtrer par sens du flux"
              className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
            >
              <option value="">Revenus + dépenses</option>
              <option value="income">Entrées d'argent</option>
              <option value="expense">Sorties d'argent</option>
            </select>
            {banks.length > 1 && (
              <select
                value={bankFilter}
                onChange={(e) => setBankFilter(e.target.value)}
                aria-label="Filtrer par banque"
                className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
              >
                <option value="">Toutes banques</option>
                {banks.map((b) => (
                  <option key={b} value={b}>
                    {BANK_LABEL[b.toLowerCase()] ?? cap(b)}
                  </option>
                ))}
              </select>
            )}
            {types.length > 1 && (
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                aria-label="Filtrer par carte"
                className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
              >
                <option value="">Crédit + débit</option>
                {types.map((t) => (
                  <option key={t} value={t}>
                    {TYPE_LABEL[t] ?? cap(t)}
                  </option>
                ))}
              </select>
            )}
            <select
              value={catFilter}
              onChange={(e) => {
                setCatFilter(e.target.value);
                setSubcatFilter("");
              }}
              aria-label="Filtrer par catégorie"
              className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
            >
              <option value="">Toutes catégories</option>
              <option value="none">Sans catégorie</option>
              {categoryRoots.map((category) => (
                <option key={category.id} value={String(category.id)}>
                  {category.nom}
                </option>
              ))}
            </select>
            <select
              value={subcatFilter}
              onChange={(e) => setSubcatFilter(e.target.value)}
              disabled={!selectedCategory}
              aria-label="Filtrer par sous-catégorie"
              className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs disabled:opacity-50"
            >
              <option value="">Toutes sous-catégories</option>
              {subcategories.map(({ category, label }) => (
                <option key={category.id} value={String(category.id)}>
                  {label}
                </option>
              ))}
            </select>
            <select
              value={tagFilter}
              onChange={(e) => setTagFilter(e.target.value)}
              aria-label="Filtrer par tag"
              className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
            >
              <option value="">Tous les tags</option>
              <option value="__none__">Sans tag</option>
              {allTags.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              aria-label="Trier"
              className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
            >
              <option value="date-desc">Date ↓ (récent)</option>
              <option value="date-asc">Date ↑ (ancien)</option>
              <option value="amount-desc">Montant ↓</option>
              <option value="amount-asc">Montant ↑</option>
              <option value="alpha">A → Z</option>
            </select>
            {anyFilter && (
              <button
                type="button"
                onClick={() => {
                  setFromDate("");
                  setToDate("");
                  setSearchFilter("");
                  setTagFilter("");
                  setCatFilter("");
                  setSubcatFilter("");
                  setBankFilter("");
                  setTypeFilter("");
                  setDirectionFilter("");
                }}
                className="text-xs text-[var(--muted-foreground)] underline hover:text-[var(--foreground)]"
              >
                Réinitialiser
              </button>
            )}
          </div>
        </div>
        {loading ? (
          <div className="space-y-2 p-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-10 rounded skeleton-shimmer" />
            ))}
          </div>
        ) : visible.length === 0 ? (
          <p className="p-6 text-center text-sm text-[var(--muted-foreground)]">
            {txs.length === 0
              ? "Aucune transaction. Importe un relevé PDF, Excel, CSV, OFX ou QFX pour commencer."
              : "Aucune transaction pour ce filtre."}
          </p>
        ) : (
          <>
            <div className="hidden divide-y divide-[var(--border)] md:block">
              {visible.map((tx) => {
                const revenu = tx.montant > 0;
                return (
                  <div
                    key={tx.id}
                    className="flex items-center gap-3 px-4 py-3 transition-colors duration-150 hover:bg-[var(--muted)]"
                  >
                    <div
                      className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full ${
                        revenu
                          ? "bg-[color-mix(in_srgb,var(--success)_15%,transparent)]"
                          : "bg-[color-mix(in_srgb,var(--destructive)_10%,transparent)]"
                      }`}
                    >
                      {revenu ? (
                        <ArrowDownLeft
                          size={14}
                          className="text-[var(--success)]"
                          aria-hidden="true"
                        />
                      ) : (
                        <ArrowUpRight
                          size={14}
                          className="text-[var(--destructive)]"
                          aria-hidden="true"
                        />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{transactionLabel(tx)}</p>
                      <div className="flex flex-wrap items-center gap-1 text-xs text-[var(--muted-foreground)]">
                        <span>{tx.date}</span>
                        <span>·</span>
                        {renderCategoryControl(tx)}
                        {typeOf(tx) && (
                          <span className="ml-1.5 rounded bg-[var(--muted)] px-1 py-0.5 text-[10px]">
                            {TYPE_LABEL[typeOf(tx)] ?? cap(typeOf(tx))}
                          </span>
                        )}
                      </div>
                      {renderTagControls(tx)}
                    </div>
                    <span
                      className={`font-mono text-sm font-semibold ${revenu ? "text-[var(--success)]" : "text-[var(--foreground)]"}`}
                    >
                      {revenu ? "+" : ""}
                      {formatCAD(tx.montant)}
                    </span>
                  </div>
                );
              })}
            </div>

            <div
              data-testid="transactions-mobile-list"
              className="divide-y divide-[var(--border)] md:hidden"
            >
              {visible.map((tx) => {
                const revenu = tx.montant > 0;
                const bank = bankOf(tx);
                const type = typeOf(tx);
                return (
                  <article
                    key={tx.id}
                    data-testid={`transaction-mobile-card-${tx.id}`}
                    className="space-y-3 px-4 py-4"
                    aria-label={`Transaction ${transactionLabel(tx)}`}
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full ${
                          revenu
                            ? "bg-[color-mix(in_srgb,var(--success)_15%,transparent)]"
                            : "bg-[color-mix(in_srgb,var(--destructive)_10%,transparent)]"
                        }`}
                      >
                        {revenu ? (
                          <ArrowDownLeft
                            size={16}
                            className="text-[var(--success)]"
                            aria-hidden="true"
                          />
                        ) : (
                          <ArrowUpRight
                            size={16}
                            className="text-[var(--destructive)]"
                            aria-hidden="true"
                          />
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-3">
                          <p className="min-w-0 break-words text-sm font-semibold">
                            {transactionLabel(tx)}
                          </p>
                          <span
                            className={`shrink-0 font-mono text-sm font-semibold ${revenu ? "text-[var(--success)]" : "text-[var(--foreground)]"}`}
                          >
                            {revenu ? "+" : ""}
                            {formatCAD(tx.montant)}
                          </span>
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-[var(--muted-foreground)]">
                          <span>{tx.date}</span>
                          {bank && <span>{BANK_LABEL[bank.toLowerCase()] ?? cap(bank)}</span>}
                          {type && (
                            <span className="rounded bg-[var(--muted)] px-1.5 py-0.5 text-[10px]">
                              {TYPE_LABEL[type] ?? cap(type)}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="grid gap-3">
                      <div>
                        <p className="text-[11px] font-medium uppercase tracking-wide text-[var(--muted-foreground)]">
                          Catégorie
                        </p>
                        {renderCategoryControl(tx, true)}
                      </div>
                      <div>
                        <p className="text-[11px] font-medium uppercase tracking-wide text-[var(--muted-foreground)]">
                          Tags
                        </p>
                        {renderTagControls(tx, true)}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

/** Règles apprises de l'historique catégorisé à la main (#258, sans ML). */
function LearnedRulesSection() {
  const { data } = useRuleSuggestions();
  const learn = useLearnRules();
  const [done, setDone] = useState<string | null>(null);
  const suggestions = data?.suggestions ?? [];
  if (suggestions.length === 0) return null;

  const onLearn = () => {
    setDone(null);
    learn.mutate(undefined, {
      onSuccess: (r) =>
        setDone(
          `${r.created} règle(s) créée(s), ${r.recategorised} transaction(s) recatégorisée(s).`,
        ),
      onError: () => setDone("Apprentissage échoué."),
    });
  };

  return (
    <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--card)] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-1.5 text-sm font-semibold">
            <Wand2 size={14} aria-hidden="true" /> Règles suggérées
          </h2>
          <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
            Apprises de tes catégorisations manuelles répétées — applicables aux futurs imports.
          </p>
          {done && <p className="mt-1 text-xs text-[var(--success)]">{done}</p>}
        </div>
        <button
          type="button"
          onClick={onLearn}
          disabled={learn.isPending}
          className="inline-flex items-center gap-2 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
        >
          <Wand2 size={14} aria-hidden="true" />
          {learn.isPending ? "Apprentissage…" : `Créer ${suggestions.length} règle(s)`}
        </button>
      </div>
      <ul className="mt-3 flex flex-wrap gap-2">
        {suggestions.map((s) => (
          <li
            key={s.pattern}
            className="rounded-[var(--radius-sm)] bg-[var(--muted)] px-2 py-1 text-xs text-[var(--muted-foreground)]"
          >
            <span className="font-mono font-medium text-[var(--foreground)]">{s.pattern}</span> →{" "}
            {s.category_nom}
            <span className="ml-1 opacity-70">({s.occurrences}×)</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
