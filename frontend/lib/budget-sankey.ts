import type { BudgetCategory } from "@/lib/budget";
import { categoryChildOnPath, categoryDescendantIds, categoryRoot } from "@/lib/budget-categories";

export type FlowBucket = {
  id: string;
  label: string;
  value: number;
  categoryId?: number | null;
};

export type FlowLink = {
  sourceId: string;
  targetId: string;
  value: number;
};

export type CashflowSankeyData = {
  sources: FlowBucket[];
  targets: FlowBucket[];
  links: FlowLink[];
  totalIncome: number;
  totalExpenses: number;
  totalFlow: number;
  balance: number;
};

export type CashflowCategorySide = "income" | "expense";

/**
 * Place une transaction dans le nœud visible du niveau choisi. Une transaction
 * classée à une feuille est ainsi agrégée sous chacun de ses parents quand on
 * remonte l'arborescence.
 */
export function bucketTransactionCategory(
  categoryId: number | null,
  categories: BudgetCategory[],
  focusCategoryId: number | null,
  side: CashflowCategorySide,
  incomeRootId: number | null,
): FlowBucket {
  if (categoryId == null) {
    return {
      id: `uncategorized:${side}`,
      label: "Sans catégorie",
      value: 0,
      categoryId: null,
    };
  }

  const category = categories.find((item) => item.id === categoryId);
  if (!category) {
    return { id: `unknown:${side}:${categoryId}`, label: `#${categoryId}`, value: 0 };
  }

  const root = categoryRoot(categories, category.id);
  const focus =
    focusCategoryId == null
      ? null
      : (categories.find((item) => item.id === focusCategoryId) ?? null);
  const focusRoot = focus ? categoryRoot(categories, focus.id) : null;

  const rootBucket = (item: BudgetCategory | null) => ({
    id: `${side}:${item?.id ?? category.id}`,
    label: item?.nom ?? category.nom,
    value: 0,
    categoryId: item?.id ?? category.id,
  });

  if (side === "income" && incomeRootId != null && root?.id !== incomeRootId) {
    return rootBucket(root);
  }

  if (focus && categoryDescendantIds(categories, focus.id).has(category.id)) {
    if (category.id === focus.id) {
      return {
        id: `direct:${side}:${focus.id}`,
        label: `Direct · ${focus.nom}`,
        value: 0,
        categoryId: null,
      };
    }

    const child = categoryChildOnPath(categories, category.id, focus.id);
    if (child) {
      return { id: `category:${child.id}`, label: child.nom, value: 0, categoryId: child.id };
    }
  }

  if (focus && side === "income" && focusRoot?.id === incomeRootId) {
    return {
      id: `other:${side}:${incomeRootId}`,
      label: "Autres revenus",
      value: 0,
      categoryId: incomeRootId,
    };
  }

  if (focus && root && focusRoot && root.id === focusRoot.id) {
    return {
      id: `other:${side}:${root.id}`,
      label: `Autres ${root.nom}`,
      value: 0,
      categoryId: root.id,
    };
  }

  return rootBucket(root);
}

/**
 * Construis les rubans d'un Sankey agrégé. Faute de connaître le lien entre un
 * revenu précis et une dépense précise, chaque source est ventilée au prorata
 * des sorties. Le solde complète le graphe à droite (surplus) ou à gauche
 * (dépenses financées par la trésorerie antérieure).
 */
export function buildCashflowSankey(
  incomeBuckets: FlowBucket[],
  expenseBuckets: FlowBucket[],
): CashflowSankeyData {
  const sources = incomeBuckets
    .filter((bucket) => Number.isFinite(bucket.value) && bucket.value > 0)
    .map((bucket) => ({ ...bucket }))
    .sort((a, b) => b.value - a.value);
  const targets = expenseBuckets
    .filter((bucket) => Number.isFinite(bucket.value) && bucket.value > 0)
    .map((bucket) => ({ ...bucket }))
    .sort((a, b) => b.value - a.value);

  const totalIncome = sources.reduce((sum, bucket) => sum + bucket.value, 0);
  const totalExpenses = targets.reduce((sum, bucket) => sum + bucket.value, 0);
  const balance = totalIncome - totalExpenses;

  if (balance > 0) {
    targets.push({ id: "__surplus__", label: "Épargne / reste", value: balance });
  } else if (balance < 0) {
    sources.push({
      id: "__other_funds__",
      label: "Solde antérieur / autres fonds",
      value: -balance,
    });
  }

  const balancedTotal = Math.max(
    sources.reduce((sum, bucket) => sum + bucket.value, 0),
    targets.reduce((sum, bucket) => sum + bucket.value, 0),
  );
  const links =
    balancedTotal > 0
      ? sources.flatMap((source) =>
          targets.map((target) => ({
            sourceId: source.id,
            targetId: target.id,
            value: (source.value * target.value) / balancedTotal,
          })),
        )
      : [];

  return { sources, targets, links, totalIncome, totalExpenses, totalFlow: balancedTotal, balance };
}

/** Regroupe les petits nœuds pour garder les libellés du diagramme lisibles. */
export function compactFlowBuckets(
  buckets: FlowBucket[],
  otherLabel: string,
  maxVisible = 7,
): FlowBucket[] {
  const sorted = buckets.filter((bucket) => bucket.value > 0).sort((a, b) => b.value - a.value);
  if (sorted.length <= maxVisible) return sorted;

  const visible = sorted.slice(0, maxVisible - 1);
  const omitted = sorted.slice(maxVisible - 1);
  visible.push({
    id: `__other_${omitted[0]?.id ?? "flow"}__`,
    label: otherLabel,
    value: omitted.reduce((sum, bucket) => sum + bucket.value, 0),
  });
  return visible;
}
