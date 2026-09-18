"use client";

import { useEffect, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { Clock, X } from "lucide-react";
import type { Ingredient, RecipeDetail } from "@/lib/cuisine";
import { useRecipe, useRecipeNote, useSetRecipeNote } from "@/lib/queries/cuisine";
import { Skeleton } from "@/components/ui/skeleton";

function recipeBase(recipe: RecipeDetail | null) {
  return recipe?.portions || 1;
}

function recipeValue(value: RecipeDetail | undefined) {
  return value ?? null;
}

function noteValue(override: string | null, fetched: string | undefined) {
  return override ?? fetched ?? '';
}

function quantityFormatter(portions: number, base: number) {
  return (quantity: number) => String(Math.round(quantity * (portions / base) * 100) / 100);
}

function RecipeIngredients({ ingredients, formatQuantity }: { ingredients: Ingredient[]; formatQuantity: (quantity: number) => string }) {
  if (ingredients.length === 0) return <p className="text-sm text-[var(--muted-foreground)]">Aucun ingrédient.</p>;
  return <ul className="space-y-1 text-sm">{ingredients.map((ingredient, index) => <li key={index} className="flex justify-between gap-2 border-b border-[var(--border)] py-1 last:border-0"><span>{ingredient.nom_libre}</span><span className="shrink-0 tabular-nums text-[var(--muted-foreground)]">{ingredient.quantite ? `${formatQuantity(ingredient.quantite)} ${ingredient.unite}` : ''}</span></li>)}</ul>;
}

function RecipeTimers({ recipe }: { recipe: RecipeDetail }) {
  if (recipe.temps_prep <= 0 && recipe.temps_cuisson <= 0) return null;
  return <div className="flex flex-wrap gap-3 rounded-md border border-[var(--border)] p-2.5"><Timer minutes={recipe.temps_prep} label="Prép." /><Timer minutes={recipe.temps_cuisson} label="Cuisson" /></div>;
}

function Timer({ minutes, label }: { minutes: number; label: string }) {
  if (minutes <= 0) return null;
  return <CookTimer minutes={minutes} label={label} />;
}

function RecipeNote({ note, onNote, onSave, saving }: { note: string; onNote: (value: string) => void; onSave: () => void; saving: boolean }) {
  return <div><p className="mb-1 text-xs font-medium text-[var(--muted-foreground)]">Notes personnelles</p><textarea value={note} onChange={(event) => onNote(event.target.value)} rows={3} placeholder="Tes remarques, variantes, astuces…" className="w-full resize-none rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]" /><button type="button" onClick={onSave} disabled={saving} className="mt-1.5 rounded-md bg-[var(--primary)] px-3 py-1 text-xs font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-60">{saving ? 'Enregistrement…' : 'Enregistrer la note'}</button></div>;
}

function RecipeLoaded({ recipe, portions, onPortions, note, onNote, onSaveNote, saving }: { recipe: RecipeDetail; portions: number; onPortions: (value: number) => void; note: string; onNote: (value: string) => void; onSaveNote: () => void; saving: boolean }) {
  const base = recipeBase(recipe);
  const formatQuantity = quantityFormatter(portions, base);
  return <>
    <div className="flex items-center justify-between"><span className="text-xs font-medium text-[var(--muted-foreground)]">Portions</span><div className="flex items-center gap-2"><button type="button" onClick={() => onPortions(Math.max(1, portions - 1))} aria-label="Moins de portions" className="h-7 w-7 rounded-md border border-[var(--border)] hover:bg-[var(--muted)]">−</button><span className="w-8 text-center tabular-nums font-semibold">{portions}</span><button type="button" onClick={() => onPortions(portions + 1)} aria-label="Plus de portions" className="h-7 w-7 rounded-md border border-[var(--border)] hover:bg-[var(--muted)]">+</button>{portions !== base && <span className="text-xs text-[var(--muted-foreground)]">(base {base})</span>}</div></div>
    <RecipeIngredients ingredients={recipe.ingredients} formatQuantity={formatQuantity} />
    <RecipeTimers recipe={recipe} />
    {recipe.instructions && <div><p className="mb-1 text-xs font-medium text-[var(--muted-foreground)]">Instructions</p><p className="whitespace-pre-wrap text-sm">{recipe.instructions}</p></div>}
    <RecipeNote note={note} onNote={onNote} onSave={onSaveNote} saving={saving} />
  </>;
}

function RecipeModalContent({ recipe, error, portions, onPortions, note, onNote, onSaveNote, saving }: { recipe: RecipeDetail | null; error: boolean; portions: number; onPortions: (value: number) => void; note: string; onNote: (value: string) => void; onSaveNote: () => void; saving: boolean }) {
  return <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4"><RecipeError visible={error} /><RecipeLoading visible={!recipe && !error} /><RecipeLoadedState recipe={recipe} portions={portions} onPortions={onPortions} note={note} onNote={onNote} onSaveNote={onSaveNote} saving={saving} /></div>;
}

function RecipeError({ visible }: { visible: boolean }) {
  return visible ? <p className="text-sm text-[var(--destructive)]">Recette indisponible.</p> : null;
}

function RecipeLoading({ visible }: { visible: boolean }) {
  return visible ? <Skeleton className="h-40" /> : null;
}

function RecipeLoadedState(props: { recipe: RecipeDetail | null; portions: number; onPortions: (value: number) => void; note: string; onNote: (value: string) => void; onSaveNote: () => void; saving: boolean }) {
  if (!props.recipe) return null;
  return <RecipeLoaded {...props} recipe={props.recipe} />;
}

export default function RecipeDetailModal({ id, onClose }: { id: number; onClose: () => void }) {
  const { recipe, error, portions, setPortions, note, setNote, saveNote, saving } = useRecipeDetailState(id, onClose);
  return <RecipeDialog title={recipe?.titre ?? 'Recette'} onClose={onClose}><RecipeModalContent recipe={recipe} error={error} portions={portions} onPortions={setPortions} note={note} onNote={setNote} onSaveNote={saveNote} saving={saving} /></RecipeDialog>;
}

function RecipeDialog({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-[6vh]"><div role="dialog" aria-modal="true" aria-label={title} className="flex max-h-[88vh] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow-lg)]"><div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3"><h2 className="font-display text-base font-semibold">{title}</h2><button type="button" onClick={onClose} aria-label="Fermer" className="rounded-[var(--radius-sm)] p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"><X className="h-4 w-4" aria-hidden="true" /></button></div>{children}</div></div>;
}

function useRecipeDetailState(id: number, onClose: () => void) {
  const recipeQ = useRecipe(id);
  const recipe = recipeValue(recipeQ.data);
  const noteQ = useRecipeNote(id);
  const noteMutation = useSetRecipeNote();
  const [portionsOverride, setPortionsOverride] = useState<number | null>(null);
  const [noteOverride, setNoteOverride] = useState<string | null>(null);
  const portions = portionsOverride ?? recipeBase(recipe);
  const note = noteValue(noteOverride, noteQ.data);
  const setPortions = (value: number) => setPortionsOverride(value);
  const setNote = (value: string) => setNoteOverride(value);
  useEffect(() => { const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); }; document.addEventListener('keydown', onKey); return () => document.removeEventListener('keydown', onKey); }, [onClose]);
  const saveNote = () => noteMutation.mutate({ id, note }, { onSuccess: () => toast.success('Note enregistrée.'), onError: () => toast.error("Impossible d'enregistrer la note.") });
  return { recipe, error: recipeQ.isError, portions, setPortions, note, setNote, saveNote, saving: noteMutation.isPending };
}

function CookTimer({ minutes, label }: { minutes: number; label: string }) {
  const [endsAt, setEndsAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { if (endsAt === null) return; const interval = setInterval(() => setNow(Date.now()), 250); return () => clearInterval(interval); }, [endsAt]);
  const remainingMs = timerMilliseconds(endsAt, now, minutes);
  const remaining = Math.max(0, Math.ceil(remainingMs / 1000));
  const running = Boolean(endsAt !== null && remainingMs > 0);
  const done = Boolean(endsAt !== null && remainingMs <= 0);
  const mmss = `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}`;
  return <div className="flex items-center gap-2 text-sm"><Clock size={14} className="text-[var(--muted-foreground)]" aria-hidden="true" /><span className="text-xs text-[var(--muted-foreground)]">{label}</span><span className={`font-mono tabular-nums ${done ? 'text-[var(--success)]' : ''}`}>{mmss}</span><TimerButton running={running} done={done} onStop={() => setEndsAt(null)} onStart={() => setEndsAt(Date.now() + minutes * 60 * 1000)} /></div>;
}

function timerMilliseconds(endsAt: number | null, now: number, minutes: number) {
  return endsAt === null ? minutes * 60 * 1000 : endsAt - now;
}

function TimerButton({ running, done, onStop, onStart }: { running: boolean; done: boolean; onStop: () => void; onStart: () => void }) {
  if (running) return <button type="button" onClick={onStop} className="rounded border border-[var(--border)] px-2 py-0.5 text-xs hover:bg-[var(--muted)]">Arrêter</button>;
  return <button type="button" onClick={onStart} className="rounded border border-[var(--border)] px-2 py-0.5 text-xs hover:bg-[var(--muted)]">{done ? 'Relancer' : 'Démarrer'}</button>;
}
