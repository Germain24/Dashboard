"use client";

import { useState, type FormEvent } from "react";
import { FolderTree, Pencil, Plus, X } from "lucide-react";
import type { BudgetCategory } from "@/lib/budget";
import {
  categoryDescendantIds,
  categoryPathLabel,
  flattenCategoryOptions,
} from "@/lib/budget-categories";
import { useCreateBudgetCategory, useUpdateBudgetCategory } from "@/lib/queries/budget";

type EditorMode = "create" | "organize";

export default function BudgetCategoryEditor({ categories }: { categories: BudgetCategory[] }) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<EditorMode>("create");
  const [name, setName] = useState("");
  const [parentId, setParentId] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [editedName, setEditedName] = useState("");
  const [editedParentId, setEditedParentId] = useState("");
  const createCategory = useCreateBudgetCategory();
  const updateCategory = useUpdateBudgetCategory();
  const options = flattenCategoryOptions(categories);
  const selectedCategory = categories.find((category) => category.id === Number(selectedId));
  const descendants = selectedCategory
    ? categoryDescendantIds(categories, selectedCategory.id)
    : new Set<number>();
  const parentOptions = options.filter(({ category }) => !descendants.has(category.id));
  const editedParent = categories.find((category) => category.id === Number(editedParentId));
  const previewPath = editedName.trim()
    ? `${editedParent ? `${categoryPathLabel(categories, editedParent.id)} › ` : ""}${editedName.trim()}`
    : "Nom de la catégorie";

  const submitCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nom = name.trim();
    if (!nom) return;
    createCategory.mutate(
      { nom, parent_id: parentId ? Number(parentId) : null },
      {
        onSuccess: () => {
          setName("");
          setParentId("");
        },
      },
    );
  };

  const submitUpdate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedCategory || !editedName.trim()) return;
    updateCategory.mutate({
      id: selectedCategory.id,
      nom: editedName.trim(),
      parent_id: editedParentId ? Number(editedParentId) : null,
    });
  };

  return (
    <section className="mt-3" aria-label="Gestion des catégories">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls="budget-category-editor"
        className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-[var(--muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
      >
        {open ? <X size={13} aria-hidden="true" /> : <FolderTree size={13} aria-hidden="true" />}
        {open ? "Fermer" : "Gérer les catégories"}
      </button>

      {open && (
        <div
          id="budget-category-editor"
          className="mt-3 rounded-lg border border-[var(--border)] bg-[var(--background)] p-3"
        >
          <div className="mb-3 flex flex-wrap gap-1 rounded-[var(--radius)] bg-[var(--muted)] p-1 sm:w-fit">
            <ModeButton active={mode === "create"} onClick={() => setMode("create")}>
              <Plus size={13} aria-hidden="true" />
              Ajouter
            </ModeButton>
            <ModeButton active={mode === "organize"} onClick={() => setMode("organize")}>
              <Pencil size={13} aria-hidden="true" />
              Renommer ou déplacer
            </ModeButton>
          </div>

          {mode === "create" ? (
            <form
              onSubmit={submitCreate}
              className="grid gap-2 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
            >
              <label className="text-xs text-[var(--muted-foreground)]">
                Nom
                <input
                  required
                  maxLength={60}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Ex. Bourse Direct, prime, pharmacie…"
                  className="mt-1 block w-full rounded-md border border-[var(--border)] bg-[var(--card)] px-2.5 py-2 text-sm text-[var(--foreground)]"
                />
              </label>
              <CategorySelect
                id="new-category-parent"
                label="Catégorie parente"
                value={parentId}
                options={options}
                onChange={setParentId}
                emptyLabel="Aucune — nouvelle famille"
              />
              <button
                type="submit"
                disabled={createCategory.isPending || !name.trim()}
                className="rounded-md bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {createCategory.isPending ? "Création…" : "Créer"}
              </button>
              {createCategory.isError && (
                <p role="alert" className="text-xs text-[var(--destructive)] sm:col-span-3">
                  Impossible de créer cette catégorie. Vérifie qu’elle n’existe pas déjà à ce
                  niveau.
                </p>
              )}
            </form>
          ) : (
            <form onSubmit={submitUpdate} className="grid gap-2 sm:grid-cols-2 sm:items-end">
              <CategorySelect
                id="category-to-edit"
                label="Catégorie à modifier"
                value={selectedCategory ? String(selectedCategory.id) : ""}
                options={options}
                onChange={(value) => {
                  setSelectedId(value);
                  const category = categories.find((item) => item.id === Number(value));
                  setEditedName(category?.nom ?? "");
                  setEditedParentId(category?.parent_id == null ? "" : String(category.parent_id));
                }}
                emptyLabel="Choisir une catégorie…"
              />
              <label className="text-xs text-[var(--muted-foreground)]">
                Nouveau nom
                <input
                  required
                  maxLength={60}
                  value={editedName}
                  onChange={(event) => setEditedName(event.target.value)}
                  disabled={!selectedCategory}
                  className="mt-1 block w-full rounded-md border border-[var(--border)] bg-[var(--card)] px-2.5 py-2 text-sm text-[var(--foreground)] disabled:opacity-50"
                />
              </label>
              <CategorySelect
                id="edited-category-parent"
                label="Nouvelle catégorie parente"
                value={editedParentId}
                options={parentOptions}
                onChange={setEditedParentId}
                emptyLabel="Aucune — déplacer à la racine"
                disabled={!selectedCategory}
              />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="min-w-0 text-[11px] text-[var(--muted-foreground)]">
                  {selectedCategory
                    ? `${categoryPathLabel(categories, selectedCategory.id)} → ${previewPath}`
                    : "Les transactions et enveloppes conservent leurs catégories."}
                </p>
                <button
                  type="submit"
                  disabled={!selectedCategory || !editedName.trim() || updateCategory.isPending}
                  className="shrink-0 rounded-md bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {updateCategory.isPending ? "Enregistrement…" : "Enregistrer"}
                </button>
              </div>
              {updateCategory.isError && (
                <p role="alert" className="text-xs text-[var(--destructive)] sm:col-span-2">
                  Impossible d’enregistrer. Vérifie le nom et le niveau choisi.
                </p>
              )}
            </form>
          )}

          <p className="mt-2 text-[11px] text-[var(--muted-foreground)]">
            Tu peux créer autant de niveaux que nécessaire. Pour une transaction, sélectionne
            ensuite la catégorie la plus précise.
          </p>
        </div>
      )}
    </section>
  );
}

function ModeButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
        active
          ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
          : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
      }`}
    >
      {children}
    </button>
  );
}

function CategorySelect({
  id,
  label,
  value,
  options,
  onChange,
  emptyLabel,
  disabled = false,
}: {
  id: string;
  label: string;
  value: string;
  options: Array<{ category: BudgetCategory; label: string }>;
  onChange: (value: string) => void;
  emptyLabel: string;
  disabled?: boolean;
}) {
  return (
    <label htmlFor={id} className="text-xs text-[var(--muted-foreground)]">
      {label}
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        className="mt-1 block w-full rounded-md border border-[var(--border)] bg-[var(--card)] px-2.5 py-2 text-sm text-[var(--foreground)] disabled:opacity-50"
      >
        <option value="">{emptyLabel}</option>
        {options.map(({ category, label: optionLabel }) => (
          <option key={category.id} value={category.id}>
            {optionLabel}
          </option>
        ))}
      </select>
    </label>
  );
}
