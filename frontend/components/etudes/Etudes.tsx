"use client";
import { useState } from "react";
import { CoursTab } from "./CoursTab";
import { DeadlinesTab } from "./DeadlinesTab";
import { GpaTab } from "./GpaTab";
import { SessionsTab } from "./SessionsTab";

const TABS = [
  { key: "cours",     label: "📚 Cours" },
  { key: "deadlines", label: "📅 Deadlines" },
  { key: "gpa",       label: "🎓 GPA" },
  { key: "sessions",  label: "⏱ Sessions" },
];

export function Etudes() {
  const [tab, setTab] = useState("cours");

  return (
    <div className="max-w-3xl mx-auto py-6 px-4 space-y-4">
      <h1 className="text-2xl font-bold">Études</h1>

      {/* Onglets */}
      <div className="flex gap-1 border-b border-[var(--border)] pb-0">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-3 py-2 text-sm rounded-t transition-colors ${
              tab === t.key
                ? "bg-[var(--card-bg)] border border-b-[var(--card-bg)] border-[var(--border)] font-medium -mb-px"
                : "text-[var(--muted)] hover:text-white"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Contenu */}
      <div className="border border-[var(--border)] rounded-b rounded-tr p-4 bg-[var(--card-bg)]">
        {tab === "cours"     && <CoursTab />}
        {tab === "deadlines" && <DeadlinesTab />}
        {tab === "gpa"       && <GpaTab />}
        {tab === "sessions"  && <SessionsTab />}
      </div>
    </div>
  );
}
