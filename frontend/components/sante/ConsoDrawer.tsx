"use client";

import { useEffect, useMemo, useState } from "react";
import type { PlanItem } from "@/lib/sante";
import {
  Dialog,
  DialogBody,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  useAddSanteFavorite,
  useRemoveSanteFavorite,
  useSanteAliments,
  useSanteFavorites,
} from "@/lib/queries/sante";

type Props = {
  open: boolean;
  onClose: () => void;
  planItems: PlanItem[]; // ce que dit le plan
  initialConsumed?: Record<string, number> | null; // ce que tu as déjà déclaré (g/aliment)
  onSave: (consumedG: Record<string, number>) => Promise<void>;
};

/**
 * Drawer permettant d'éditer la quantité (en grammes) réellement consommée
 * pour chaque aliment du plan. La compensation J-1 utilise ces valeurs.
 *
 * Pratique : par défaut, on pré-remplit avec le plan généré. L'utilisateur
 * ajuste les lignes qu'il a changées.
 */
export function ConsoDrawer({ open, onClose, planItems, initialConsumed, onSave }: Props) {
  // Map nom → grammes. Si initialConsumed est null, on pré-remplit avec le plan.
  const [grams, setGrams] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Favoris (#64) + lignes ajoutées hors plan
  const [extra, setExtra] = useState<string[]>([]);
  const [picker, setPicker] = useState("");

  const favorites: string[] = useSanteFavorites().data ?? [];
  const alimentsQ = useSanteAliments();
  const catalog: string[] = useMemo(
    () => (alimentsQ.data ?? []).map((a) => a.nom),
    [alimentsQ.data],
  );
  const addFavMutation = useAddSanteFavorite();
  const removeFavMutation = useRemoveSanteFavorite();

  const planNames = useMemo(() => new Set(planItems.map((it) => it.aliment)), [planItems]);

  useEffect(() => {
    if (!open) return;
    const next: Record<string, number> = {};
    // Pré-remplit avec le plan
    for (const it of planItems) {
      next[it.aliment] = Math.round(it.quantite_g);
    }
    // initialConsumed est stocké sous forme `<aliment>_g` côté backend (cf. ConvertedConsumed)
    // ou bien sous forme `Calories: X` (totaux agrégés). On distingue : si la clé matche
    // un aliment, on prend cette quantité ; sinon on ignore (les totaux nutritifs ne se
    // ré-éditent pas ici, ils sont recalculés à partir des grammes).
    if (initialConsumed) {
      for (const [k, v] of Object.entries(initialConsumed)) {
        if (k.endsWith("_g")) {
          const aliment = k.slice(0, -2);
          next[aliment] = Math.round(v);
        }
      }
    }
    // Lignes hors plan déjà déclarées → on les garde visibles
    const seededExtra: string[] = [];
    if (initialConsumed) {
      for (const k of Object.keys(initialConsumed)) {
        if (k.endsWith("_g")) {
          const aliment = k.slice(0, -2);
          if (!planNames.has(aliment)) seededExtra.push(aliment);
        }
      }
    }
    // Resetting the draft is the intended synchronization point for opening this editor.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setExtra(seededExtra);
    setGrams(next);
    setErr(null);
  }, [open, planItems, initialConsumed, planNames]);

  const setQty = (aliment: string, qty: number) => {
    setGrams((g) => ({ ...g, [aliment]: Math.max(0, qty) }));
  };

  const addRow = (aliment: string) => {
    if (!aliment) return;
    if (!planNames.has(aliment) && !extra.includes(aliment)) {
      setExtra((e) => [...e, aliment]);
    }
    setGrams((g) => ({ ...g, [aliment]: g[aliment] || 100 }));
  };

  const toggleFavorite = (aliment: string) => {
    if (favorites.includes(aliment)) removeFavMutation.mutate(aliment);
    else addFavMutation.mutate(aliment);
  };

  const handleSave = async () => {
    setSaving(true);
    setErr(null);
    try {
      // On garde toutes les lignes, même celles à 0 (pour distinguer "rien mangé" de "non saisi").
      await onSave(grams);
      onClose();
    } catch (error: unknown) {
      setErr(error instanceof Error ? error.message : "Erreur enregistrement");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} className="max-w-md">
      <DialogHeader onClose={onClose} className="pb-2">
        <DialogTitle>Ce que j&apos;ai mangé aujourd&apos;hui</DialogTitle>
      </DialogHeader>
      <DialogBody className="max-h-[calc(90dvh-10rem)] space-y-3 overflow-y-auto pb-5">
        <p className="text-xs text-[var(--muted-foreground)] mb-3">
          Pré-rempli avec le plan généré. Modifie les lignes qui ne correspondent pas, puis
          enregistre. Ces valeurs alimentent la compensation J-1 du lendemain.
        </p>

        <div className="space-y-2">
          {planItems.map((it) => (
            <div key={it.aliment} className="flex items-center gap-2 text-sm">
              <span className="flex-1 truncate" title={it.aliment}>
                {it.aliment}
              </span>
              <span className="text-xs text-[var(--muted-foreground)] tabular-nums">
                plan : {it.quantite_g.toFixed(0)}g
              </span>
              <input
                type="number"
                min={0}
                step={10}
                value={grams[it.aliment] ?? 0}
                onChange={(e) => setQty(it.aliment, parseFloat(e.target.value) || 0)}
                aria-label={`Quantité consommée pour ${it.aliment}, en grammes`}
                className="w-20 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm text-right"
              />
              <span className="text-xs">g</span>
            </div>
          ))}
        </div>

        {/* Lignes hors plan (ajoutées via favoris / recherche) */}
        {extra.length > 0 && (
          <div className="mt-2 space-y-2 border-t border-[var(--border)] pt-2">
            {extra.map((nom) => (
              <div key={nom} className="flex items-center gap-2 text-sm">
                <span className="flex-1 truncate" title={nom}>
                  {nom}
                </span>
                <button
                  type="button"
                  onClick={() => void toggleFavorite(nom)}
                  aria-label={
                    favorites.includes(nom)
                      ? `Retirer ${nom} des favoris`
                      : `Ajouter ${nom} aux favoris`
                  }
                  aria-pressed={favorites.includes(nom)}
                  title={favorites.includes(nom) ? "Retirer des favoris" : "Ajouter aux favoris"}
                  className="text-xs"
                >
                  {favorites.includes(nom) ? "⭐" : "☆"}
                </button>
                <input
                  type="number"
                  min={0}
                  step={10}
                  value={grams[nom] ?? 0}
                  onChange={(e) => setQty(nom, parseFloat(e.target.value) || 0)}
                  aria-label={`Quantité consommée pour ${nom}, en grammes`}
                  className="w-20 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm text-right"
                />
                <span className="text-xs">g</span>
              </div>
            ))}
          </div>
        )}

        {planItems.length === 0 && extra.length === 0 && (
          <div className="text-sm text-[var(--muted-foreground)]">Aucun item dans le plan.</div>
        )}

        {/* Favoris — saisie rapide (#64) */}
        <div className="mt-4 border-t border-[var(--border)] pt-3">
          <p className="text-xs font-medium text-[var(--muted-foreground)] mb-2">
            ⭐ Favoris — saisie rapide
          </p>
          {favorites.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {favorites.map((nom) => (
                <button
                  key={nom}
                  type="button"
                  onClick={() => addRow(nom)}
                  title={`Ajouter ${nom}`}
                  className="rounded-full border border-[var(--border)] px-2.5 py-1 text-xs hover:bg-[var(--muted)]"
                >
                  + {nom}
                </button>
              ))}
            </div>
          ) : (
            <p className="text-xs text-[var(--muted-foreground)]">
              Aucun favori. Ajoute un aliment ci-dessous pour le retrouver vite.
            </p>
          )}
          <div className="mt-2 flex gap-2">
            <label htmlFor="conso-catalog-picker" className="sr-only">
              Rechercher un aliment à ajouter
            </label>
            <input
              id="conso-catalog-picker"
              list="conso-catalog"
              value={picker}
              onChange={(e) => setPicker(e.target.value)}
              placeholder="Chercher un aliment…"
              className="flex-1 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
            />
            <datalist id="conso-catalog">
              {catalog.map((nom) => (
                <option key={nom} value={nom} />
              ))}
            </datalist>
            <button
              type="button"
              onClick={() => {
                if (catalog.includes(picker)) {
                  addRow(picker);
                  setPicker("");
                }
              }}
              disabled={!catalog.includes(picker)}
              className="rounded border border-[var(--border)] px-2 py-1 text-xs hover:bg-[var(--muted)] disabled:opacity-50"
            >
              Ajouter
            </button>
            <button
              type="button"
              onClick={() => {
                if (catalog.includes(picker)) void toggleFavorite(picker);
              }}
              disabled={!catalog.includes(picker)}
              aria-label={
                favorites.includes(picker)
                  ? `Retirer ${picker} des favoris`
                  : `Ajouter ${picker || "cet aliment"} aux favoris`
              }
              aria-pressed={favorites.includes(picker)}
              title="Ajouter/retirer des favoris"
              className="rounded border border-[var(--border)] px-2 py-1 text-xs hover:bg-[var(--muted)] disabled:opacity-50"
            >
              {favorites.includes(picker) ? "⭐" : "☆"}
            </button>
          </div>
        </div>

        {err && (
          <div role="alert" className="mt-3 text-sm text-[var(--destructive)]">
            ⚠ {err}
          </div>
        )}
      </DialogBody>
      <DialogFooter className="justify-start">
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={saving}
          className="rounded bg-[var(--success)] text-[var(--success-foreground)] px-3 py-1.5 text-sm font-semibold disabled:opacity-50"
        >
          {saving ? "…" : "💾 Enregistrer ma conso"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--accent)]"
        >
          Annuler
        </button>
      </DialogFooter>
    </Dialog>
  );
}
