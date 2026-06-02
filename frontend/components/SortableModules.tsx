"use client";

/**
 * Grille de modules réordonnable par glisser-déposer (dnd-kit), persistée en
 * localStorage. Une contrainte de distance évite que le clic de navigation
 * d'une carte ne déclenche un drag involontaire.
 */

import { useMemo } from "react";
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  closestCenter,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  rectSortingStrategy,
  useSortable,
  sortableKeyboardCoordinates,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ModuleCard } from "@/components/ModuleCard";
import { MODULES, type Module } from "@/lib/modules";
import { useLocalStorage } from "@/lib/hooks";

function SortableCard({ module: m }: { module: Module }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: m.slug,
  });
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={isDragging ? "opacity-60 z-10" : ""}
      {...attributes}
      {...listeners}
    >
      <ModuleCard module={m} />
    </div>
  );
}

export function SortableModules() {
  const [order, setOrder] = useLocalStorage<string[]>("mc-modules-order", []);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  // Applique l'ordre sauvegardé ; les modules nouveaux (absents) sont ajoutés à la fin.
  const ordered = useMemo(() => {
    const bySlug = new Map(MODULES.map((m) => [m.slug, m]));
    const seen = new Set<string>();
    const result: Module[] = [];
    for (const slug of order) {
      const m = bySlug.get(slug);
      if (m && !seen.has(slug)) {
        result.push(m);
        seen.add(slug);
      }
    }
    for (const m of MODULES) {
      if (!seen.has(m.slug)) result.push(m);
    }
    return result;
  }, [order]);

  function onDragEnd(e: DragEndEvent) {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const slugs = ordered.map((m) => m.slug);
    const from = slugs.indexOf(String(active.id));
    const to = slugs.indexOf(String(over.id));
    if (from === -1 || to === -1) return;
    setOrder(arrayMove(slugs, from, to));
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
      <SortableContext items={ordered.map((m) => m.slug)} strategy={rectSortingStrategy}>
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {ordered.map((m) => (
            <SortableCard key={m.slug} module={m} />
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
}
