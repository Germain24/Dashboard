"use client";

import { useState } from "react";
import { LieuxTab } from "./LieuxTab";
import { PlanifierTab } from "./PlanifierTab";

export function Voyage() {
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const toggle = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size < 25) next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Voyage</h1>
      <LieuxTab selected={selected} onToggle={toggle} />
      <PlanifierTab candidats={[...selected]} onConfirmed={() => setSelected(new Set())} />
    </div>
  );
}
