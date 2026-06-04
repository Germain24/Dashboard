"use client";

import { useEffect, useState } from "react";

function getGreeting(hour: number): string {
  if (hour < 5) return "Bonne nuit";
  if (hour < 12) return "Bonjour";
  if (hour < 18) return "Bon après-midi";
  if (hour < 22) return "Bonsoir";
  return "Bonne nuit";
}

export function Greeting() {
  const [greeting, setGreeting] = useState("Mission Control");
  const [date, setDate] = useState<string | null>(null);

  useEffect(() => {
    const now = new Date();
    setGreeting(getGreeting(now.getHours()));
    setDate(
      now.toLocaleDateString("fr-CA", {
        weekday: "long",
        day: "numeric",
        month: "long",
      }),
    );
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">{greeting}, Germain</h1>
      {/* Réserve la hauteur de ligne avant montage pour éviter tout saut. */}
      <p className="mt-1 text-sm text-[var(--muted-foreground)] first-letter:uppercase">
        {date ?? " "}
      </p>
    </div>
  );
}
