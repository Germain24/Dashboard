"use client";

import { useState } from "react";
import { BookOpen, AlarmClock, Clock, Award } from "lucide-react";
import { CoursTab } from "./CoursTab";
import { DeadlinesTab } from "./DeadlinesTab";
import { GpaTab } from "./GpaTab";
import { SessionsTab } from "./SessionsTab";

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
        {tab === "cours" && <CoursTab />}
        {tab === "deadlines" && <DeadlinesTab />}
        {tab === "gpa" && <GpaTab />}
        {tab === "sessions" && <SessionsTab />}
      </div>
    </div>
  );
}
