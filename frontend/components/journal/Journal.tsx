"use client";

import { useState } from "react";
import { QuickEntry } from "./QuickEntry";
import { TrendsTab } from "./TrendsTab";
import { CorrelationsPanel } from "./CorrelationsPanel";

export default function Journal() {
  const [refresh, setRefresh] = useState(0);
  return (
    <div className="space-y-6 p-4 max-w-3xl mx-auto">
      <h1 className="text-xl font-semibold">Journal · Humeur</h1>
      <QuickEntry onSaved={() => setRefresh((r) => r + 1)} />
      <section key={refresh} className="space-y-6">
        <TrendsTab />
        <CorrelationsPanel />
      </section>
    </div>
  );
}
