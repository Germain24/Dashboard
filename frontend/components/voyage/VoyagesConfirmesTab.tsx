"use client";

/** Voyages confirmés (§5.4) : checklist de préparation + budget par étape.
 *  L'estimé vient du serveur (costs.py) ; seul le coût réel est saisissable. */

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { ChecklistItem, VoyageConfirme, VoyageEtape } from "@/lib/voyage";
import {
  useAddChecklistItem,
  useDeleteChecklistItem,
  useDeleteVoyage,
  useSetCoutReel,
  useUpdateChecklistItem,
  useVoyagesConfirmes,
} from "@/lib/queries/voyage";

const eur = (n: number) =>
  new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 })
    .format(n);

function EtapeLigne({ voyageId, etape }: { voyageId: number; etape: VoyageEtape }) {
  const setCoutReel = useSetCoutReel();
  const [valeur, setValeur] = useState(etape.cout_reel?.toString() ?? "");

  // Enregistrement au blur plutôt qu'à chaque frappe : une saisie de montant
  // passe par des états intermédiaires ("4", "40") qui n'ont pas de sens.
  const enregistrer = () => {
    const trim = valeur.trim();
    const coutReel = trim === "" ? null : Number(trim);
    if (coutReel !== null && Number.isNaN(coutReel)) return;
    if (coutReel === etape.cout_reel) return;
    setCoutReel.mutate({ voyageId, etapeId: etape.id, coutReel });
  };

  const ecart = etape.cout_reel === null ? null : etape.cout_reel - etape.cout_estime;

  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-[var(--border)] py-2 text-sm first:border-t-0">
      <span className="min-w-32 flex-1 font-medium">{etape.nom}</span>
      <span className="text-xs text-[var(--muted-foreground)]">
        {etape.jours} j{etape.date_arrivee ? ` · ${etape.date_arrivee}` : ""}
      </span>
      <span className="tabular-nums text-xs text-[var(--muted-foreground)]">
        estimé {eur(etape.cout_estime)}
      </span>
      <label className="flex items-center gap-1.5 text-xs">
        <span className="sr-only">Coût réel — {etape.nom}</span>
        <input
          type="number"
          inputMode="decimal"
          aria-label={`Coût réel — ${etape.nom}`}
          value={valeur}
          placeholder="réel"
          onChange={(e) => setValeur(e.target.value)}
          onBlur={enregistrer}
          className="w-24 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm tabular-nums"
        />
      </label>
      {ecart !== null && ecart !== 0 && (
        <span
          className={`tabular-nums text-xs ${ecart > 0 ? "text-amber-700 dark:text-amber-300" : "text-emerald-700 dark:text-emerald-300"}`}
        >
          {ecart > 0 ? "+" : ""}{eur(ecart)}
        </span>
      )}
    </li>
  );
}

function ChecklistLigne({ voyageId, item }: { voyageId: number; item: ChecklistItem }) {
  const update = useUpdateChecklistItem();
  const remove = useDeleteChecklistItem();

  return (
    <li className="flex items-center gap-2 text-sm">
      <input
        id={`checklist-${item.id}`}
        type="checkbox"
        checked={item.fait}
        aria-label={item.label}
        onChange={(e) =>
          update.mutate({ voyageId, itemId: item.id, patch: { fait: e.target.checked } })
        }
        className="accent-[var(--ring)]"
      />
      <label
        htmlFor={`checklist-${item.id}`}
        className={`flex-1 cursor-pointer ${item.fait ? "text-[var(--muted-foreground)] line-through" : ""}`}
      >
        {item.label}
      </label>
      <button
        type="button"
        onClick={() => remove.mutate({ voyageId, itemId: item.id })}
        aria-label={`Supprimer ${item.label}`}
        className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"
      >
        <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </li>
  );
}

function VoyageCarte({ voyage }: { voyage: VoyageConfirme }) {
  const addItem = useAddChecklistItem();
  const deleteVoyage = useDeleteVoyage();
  const [nouveau, setNouveau] = useState("");

  const ajouter = () => {
    const label = nouveau.trim();
    if (!label) return;
    addItem.mutate({ voyageId: voyage.id, label }, { onSuccess: () => setNouveau("") });
  };

  const { budget } = voyage;

  return (
    <div className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">{voyage.titre}</span>
        <span className="text-xs text-[var(--muted-foreground)] tabular-nums">
          {voyage.date_debut} → {voyage.date_fin}
        </span>
        <button
          type="button"
          onClick={() => deleteVoyage.mutate(voyage.id)}
          aria-label={`Supprimer le voyage ${voyage.titre}`}
          className="ml-auto p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <p className="text-xs text-[var(--muted-foreground)] tabular-nums">
        estimé {eur(budget.cout_estime_total)} · projeté{" "}
        <span className="font-medium text-[var(--foreground)]">{eur(budget.cout_projete_total)}</span>
        {budget.ecart !== 0 && (
          <span className={budget.ecart > 0 ? "text-amber-700 dark:text-amber-300" : "text-emerald-700 dark:text-emerald-300"}>
            {" "}({budget.ecart > 0 ? "+" : ""}{eur(budget.ecart)})
          </span>
        )}
      </p>

      <ul>
        {voyage.etapes.map((e) => (
          <EtapeLigne key={e.id} voyageId={voyage.id} etape={e} />
        ))}
      </ul>

      <div className="space-y-2 rounded-lg border border-[var(--border)] p-3">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">
          Checklist{" "}
          <span className="tabular-nums">
            {voyage.checklist_faits} / {voyage.checklist_total}
          </span>
        </p>
        <ul className="space-y-1">
          {voyage.checklist.map((item) => (
            <ChecklistLigne key={item.id} voyageId={voyage.id} item={item} />
          ))}
        </ul>
        <div className="flex items-center gap-2">
          <input
            value={nouveau}
            onChange={(e) => setNouveau(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ajouter()}
            placeholder="Ajouter un item…"
            aria-label={`Ajouter un item à la checklist de ${voyage.titre}`}
            className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm"
          />
          <button
            type="button"
            onClick={ajouter}
            disabled={!nouveau.trim() || addItem.isPending}
            className="flex items-center gap-1 rounded-lg border border-[var(--border)] px-2 py-1 text-xs hover:bg-[var(--muted)] disabled:opacity-50"
          >
            <Plus className="h-3 w-3" aria-hidden="true" /> Ajouter
          </button>
        </div>
      </div>
    </div>
  );
}

export function VoyagesConfirmesTab() {
  const voyagesQ = useVoyagesConfirmes();

  if (voyagesQ.isError) {
    return (
      <p className="text-sm text-[var(--destructive)]">
        {voyagesQ.error?.message ?? "Erreur de chargement des voyages"}
      </p>
    );
  }
  if (voyagesQ.isLoading) {
    return <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>;
  }

  const voyages = voyagesQ.data ?? [];
  if (voyages.length === 0) {
    return (
      <p className="text-sm text-[var(--muted-foreground)]">
        Aucun voyage confirmé — confirme un itinéraire pour suivre sa checklist et son budget.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {voyages.map((v) => (
        <VoyageCarte key={v.id} voyage={v} />
      ))}
    </div>
  );
}
