import type { BudgetCategory } from "@/lib/budget";

export function categoryChildren(categories: BudgetCategory[], parentId: number): BudgetCategory[] {
  return categories.filter((category) => category.parent_id === parentId);
}

/** Renvoie le premier niveau sous `ancestorId` qui contient `categoryId`. */
export function categoryChildOnPath(
  categories: BudgetCategory[],
  categoryId: number,
  ancestorId: number,
): BudgetCategory | null {
  const byId = new Map(categories.map((category) => [category.id, category]));
  let current = byId.get(categoryId);
  const visited = new Set<number>();

  while (current && !visited.has(current.id)) {
    if (current.parent_id === ancestorId) return current;
    visited.add(current.id);
    current = current.parent_id == null ? undefined : byId.get(current.parent_id);
  }

  return null;
}

export function categoryDescendantIds(
  categories: BudgetCategory[],
  categoryId: number,
): Set<number> {
  const descendants = new Set([categoryId]);
  let expanded = true;
  while (expanded) {
    expanded = false;
    for (const category of categories) {
      if (
        category.parent_id != null &&
        descendants.has(category.parent_id) &&
        !descendants.has(category.id)
      ) {
        descendants.add(category.id);
        expanded = true;
      }
    }
  }
  return descendants;
}

export function categoryRoot(
  categories: BudgetCategory[],
  categoryId: number | null,
): BudgetCategory | null {
  if (categoryId == null) return null;
  const byId = new Map(categories.map((category) => [category.id, category]));
  let current = byId.get(categoryId) ?? null;
  const visited = new Set<number>();
  while (current?.parent_id != null && !visited.has(current.id)) {
    visited.add(current.id);
    current = byId.get(current.parent_id) ?? current;
    if (current.parent_id != null && !byId.has(current.parent_id)) break;
  }
  return current;
}

export function categoryPathLabel(categories: BudgetCategory[], categoryId: number | null): string {
  if (categoryId == null) return "Sans catégorie";
  const byId = new Map(categories.map((category) => [category.id, category]));
  const labels: string[] = [];
  const visited = new Set<number>();
  let current = byId.get(categoryId);
  while (current && !visited.has(current.id)) {
    labels.unshift(current.nom);
    visited.add(current.id);
    current = current.parent_id == null ? undefined : byId.get(current.parent_id);
  }
  return labels.length ? labels.join(" › ") : `#${categoryId}`;
}

export function flattenCategoryOptions(
  categories: BudgetCategory[],
): Array<{ category: BudgetCategory; label: string }> {
  const childrenByParent = new Map<number | null, BudgetCategory[]>();
  for (const category of categories) {
    const siblings = childrenByParent.get(category.parent_id) ?? [];
    siblings.push(category);
    childrenByParent.set(category.parent_id, siblings);
  }
  for (const siblings of childrenByParent.values()) {
    siblings.sort((a, b) => a.nom.localeCompare(b.nom, "fr-CA"));
  }

  const options: Array<{ category: BudgetCategory; label: string }> = [];
  const visit = (parentId: number | null, prefix = "") => {
    for (const category of childrenByParent.get(parentId) ?? []) {
      options.push({ category, label: `${prefix}${category.nom}` });
      visit(category.id, `${prefix}${category.nom} › `);
    }
  };
  visit(null);
  return options;
}
