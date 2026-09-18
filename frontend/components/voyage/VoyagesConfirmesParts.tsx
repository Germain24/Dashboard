import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { ChecklistItem, VoyageConfirme, VoyageEtape } from "@/lib/voyage";
import { useAddChecklistItem, useDeleteChecklistItem, useDeleteVoyage, useSetCoutReel, useUpdateChecklistItem } from "@/lib/queries/voyage";

export function eur(value: number): string {
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(value);
}

function parseCost(value: string): number | null {
  const trim = value.trim();
  return trim === "" ? null : Number(trim);
}

function saveCost(value: string, current: number | null, save: (cost: number | null) => void): void {
  const cost = parseCost(value);
  if (cost !== null && Number.isNaN(cost)) return;
  if (cost === current) return;
  save(cost);
}

export function EtapeLigne({ voyageId, etape }: { voyageId: number; etape: VoyageEtape }) {
  const mutation = useSetCoutReel();
  const [value, setValue] = useState(etape.cout_reel?.toString() ?? "");
  const difference = etape.cout_reel === null ? null : etape.cout_reel - etape.cout_estime;
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-[var(--border)] py-2 text-sm first:border-t-0">
      <span className="min-w-32 flex-1 font-medium">{etape.nom}</span>
      <span className="text-xs text-[var(--muted-foreground)]">{etape.jours} j{etape.date_arrivee ? ` · ${etape.date_arrivee}` : ""}</span>
      <span className="tabular-nums text-xs text-[var(--muted-foreground)]">estimé {eur(etape.cout_estime)}</span>
      <label className="flex items-center gap-1.5 text-xs"><span className="sr-only">Coût réel — {etape.nom}</span><input type="number" inputMode="decimal" aria-label={`Coût réel — ${etape.nom}`} value={value} placeholder="réel" onChange={(event) => setValue(event.target.value)} onBlur={() => saveCost(value, etape.cout_reel, (cost) => mutation.mutate({ voyageId, etapeId: etape.id, coutReel: cost }))} className="w-24 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm tabular-nums" /></label>
      <CostDifference value={difference} />
    </li>
  );
}

function CostDifference({ value }: { value: number | null }) {
  if (value === null || value === 0) return null;
  const className = value > 0 ? "text-amber-700 dark:text-amber-300" : "text-emerald-700 dark:text-emerald-300";
  return <span className={`tabular-nums text-xs ${className}`}>{value > 0 ? "+" : ""}{eur(value)}</span>;
}

export function ChecklistLigne({ voyageId, item }: { voyageId: number; item: ChecklistItem }) {
  const update = useUpdateChecklistItem();
  const remove = useDeleteChecklistItem();
  const updateItem = (fait: boolean) => update.mutate({ voyageId, itemId: item.id, patch: { fait } });
  return <li className="flex items-center gap-2 text-sm"><input id={`checklist-${item.id}`} type="checkbox" checked={item.fait} aria-label={item.label} onChange={(event) => updateItem(event.target.checked)} className="accent-[var(--ring)]" /><label htmlFor={`checklist-${item.id}`} className={`flex-1 cursor-pointer ${item.fait ? "text-[var(--muted-foreground)] line-through" : ""}`}>{item.label}</label><button type="button" onClick={() => remove.mutate({ voyageId, itemId: item.id })} aria-label={`Supprimer ${item.label}`} className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"><Trash2 className="h-3.5 w-3.5" aria-hidden="true" /></button></li>;
}

function BudgetSummary({ budget }: { budget: VoyageConfirme["budget"] }) {
  return <p className="text-xs text-[var(--muted-foreground)] tabular-nums">estimé {eur(budget.cout_estime_total)} · projeté <span className="font-medium text-[var(--foreground)]">{eur(budget.cout_projete_total)}</span><BudgetDifference value={budget.ecart} /></p>;
}

function BudgetDifference({ value }: { value: number }) {
  if (value === 0) return null;
  return <span className={value > 0 ? "text-amber-700 dark:text-amber-300" : "text-emerald-700 dark:text-emerald-300"}> ({value > 0 ? "+" : ""}{eur(value)})</span>;
}

function ChecklistPanel({ voyage }: { voyage: VoyageConfirme }) {
  const addItem = useAddChecklistItem();
  const [newItem, setNewItem] = useState("");
  const add = () => {
    const label = newItem.trim();
    if (!label) return;
    addItem.mutate({ voyageId: voyage.id, label }, { onSuccess: () => setNewItem("") });
  };
  return <div className="space-y-2 rounded-lg border border-[var(--border)] p-3"><p className="text-xs font-semibold text-[var(--muted-foreground)]">Checklist <span className="tabular-nums">{voyage.checklist_faits} / {voyage.checklist_total}</span></p><ul className="space-y-1">{voyage.checklist.map((item) => <ChecklistLigne key={item.id} voyageId={voyage.id} item={item} />)}</ul><div className="flex items-center gap-2"><input value={newItem} onChange={(event) => setNewItem(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") add(); }} placeholder="Ajouter un item…" aria-label={`Ajouter un item à la checklist de ${voyage.titre}`} className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm" /><button type="button" onClick={add} disabled={!newItem.trim() || addItem.isPending} className="flex items-center gap-1 rounded-lg border border-[var(--border)] px-2 py-1 text-xs hover:bg-[var(--muted)] disabled:opacity-50"><Plus className="h-3 w-3" aria-hidden="true" /> Ajouter</button></div></div>;
}

export function VoyageCarte({ voyage }: { voyage: VoyageConfirme }) {
  const deleteVoyage = useDeleteVoyage();
  return <div className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"><div className="flex flex-wrap items-center gap-2"><span className="font-semibold">{voyage.titre}</span><span className="text-xs text-[var(--muted-foreground)] tabular-nums">{voyage.date_debut} → {voyage.date_fin}</span><button type="button" onClick={() => deleteVoyage.mutate(voyage.id)} aria-label={`Supprimer le voyage ${voyage.titre}`} className="ml-auto p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"><Trash2 className="h-4 w-4" aria-hidden="true" /></button></div><BudgetSummary budget={voyage.budget} /><ul>{voyage.etapes.map((etape) => <EtapeLigne key={etape.id} voyageId={voyage.id} etape={etape} />)}</ul><ChecklistPanel voyage={voyage} /></div>;
}

export function VoyagesConfirmedContent({ voyages }: { voyages: VoyageConfirme[] | undefined }) {
  if (!voyages || voyages.length === 0) return <p className="text-sm text-[var(--muted-foreground)]">Aucun voyage confirmé — confirme un itinéraire pour suivre sa checklist et son budget.</p>;
  return <div className="space-y-3">{voyages.map((voyage) => <VoyageCarte key={voyage.id} voyage={voyage} />)}</div>;
}
