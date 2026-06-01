"use client";
<<<<<<< HEAD
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
=======

import { useState } from "react";
import { BookOpen, AlarmClock, Clock, Award } from "lucide-react";

type Tab = "cours" | "deadlines" | "sessions" | "gpa";

const TABS: { id: Tab; label: string; Icon: React.ElementType }[] = [
  { id: "cours", label: "Cours", Icon: BookOpen },
  { id: "deadlines", label: "Deadlines", Icon: AlarmClock },
  { id: "sessions", label: "Sessions", Icon: Clock },
  { id: "gpa", label: "GPA", Icon: Award },
];

export function Etudes() {
  const [tab, setTab] = useState<Tab>("cours");

  return (
    <div className="space-y-0 animate-fade-in">
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="mb-4">
          <h1 className="text-xl font-semibold tracking-tight">Études</h1>
          <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Cours, évaluations &amp; GPA</p>
        </div>
        <div className="flex gap-1">
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md transition-all duration-200 ${
                tab === id
                  ? "text-[var(--ring)] bg-[color-mix(in_srgb,var(--ring)_10%,transparent)]"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]"
              }`}
            >
              <Icon size={15} />{label}
            </button>
          ))}
        </div>
      </div>

      <div key={tab} className="p-6 animate-fade-in-up">
        <div className="rounded-xl border border-dashed border-[var(--border)] p-10 text-center text-sm text-[var(--muted-foreground)]">
          Module en cours de développement — onglet <strong>{tab}</strong>
        </div>
>>>>>>> worktree-agent-a62d2a55482deb0a2
      </div>
    </div>
  );
}
