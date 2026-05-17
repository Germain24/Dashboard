"use client";

import { MACRO_UNITS } from "@/lib/sante";
import { MacroBar } from "./MacroBar";

type Props = {
  open: boolean;
  onClose: () => void;
  targets: Record<string, number>;
  totals: Record<string, number>;
};

const MICRO_KEYS = [
  "Sodium_Max",
  "Cholesterol_Max",
  "Sucres_Max",
  "Omega3",
  "Magnésium",
  "Calcium",
  "Fer",
  "Zinc",
  "Potassium",
  "Phosphore",
  "Chlorure",
  "Cuivre",
  "Iode",
  "Manganèse",
  "Sélénium",
  "VitA",
  "VitB1",
  "VitB2",
  "VitB3",
  "VitB5",
  "VitB6",
  "VitB9",
  "VitB12",
  "VitC",
  "VitD",
  "VitE",
  "VitK",
];

const MAX_NUTRIENTS = new Set(["Sodium_Max", "Cholesterol_Max", "Sucres_Max"]);

const LABELS: Record<string, string> = {
  Sodium_Max: "Sodium (max)",
  Cholesterol_Max: "Cholestérol (max)",
  Sucres_Max: "Sucres (max)",
  Omega3: "Oméga 3",
  VitA: "Vitamine A",
  VitB1: "B1",
  VitB2: "B2",
  VitB3: "B3",
  VitB5: "B5",
  VitB6: "B6",
  VitB9: "B9",
  VitB12: "B12",
  VitC: "Vitamine C",
  VitD: "Vitamine D",
  VitE: "Vitamine E",
  VitK: "Vitamine K",
};

export function MicrosDrawer({ open, onClose, targets, totals }: Props) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex">
      <div className="flex-1 bg-black/40" onClick={onClose} />
      <aside className="w-full max-w-md bg-[var(--background)] border-l border-[var(--border)] p-4 overflow-y-auto">
        <header className="flex items-center justify-between mb-4">
          <h2 className="font-medium">Détail micronutriments</h2>
          <button onClick={onClose} className="rounded border border-[var(--border)] px-2 py-1 text-xs hover:bg-[var(--accent)]">
            ✕
          </button>
        </header>
        <div className="grid gap-2">
          {MICRO_KEYS.map((k) => {
            const target = targets[k] ?? 0;
            const current = totals[k] ?? 0;
            if (!target && !current) return null;
            return (
              <MacroBar
                key={k}
                label={LABELS[k] ?? k}
                unit={MACRO_UNITS[k] ?? ""}
                current={current}
                target={target}
                isMax={MAX_NUTRIENTS.has(k)}
              />
            );
          })}
        </div>
      </aside>
    </div>
  );
}
