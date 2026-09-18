"use client";

import { useEffect, useState } from "react";

const GREETINGS: Array<[number, string]> = [
  [5, "Bonne nuit"],
  [12, "Bonjour"],
  [18, "Bon après‑midi"],
  [22, "Bonsoir"],
];

function getGreeting(hour: number): string {
  return GREETINGS.find(([limit]) => hour < limit)?.[1] ?? "Bonne nuit";
}

export function Greeting() {
  const [greeting, setGreeting] = useState("Mission Control");
  const [date, setDate] = useState<string | null>(null);

  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      const now = new Date();
      setGreeting(getGreeting(now.getHours()));
      setDate(
        now.toLocaleDateString("fr-CA", {
          weekday: "long",
          day: "numeric",
          month: "long",
        }),
      );
    });
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <div>
      <h1 className="max-w-[13ch] font-display text-[clamp(2.5rem,4vw,4rem)] font-normal leading-[0.94] tracking-[-0.035em] text-[var(--foreground)]">
        <span className="block whitespace-nowrap">{greeting},</span>
        <span className="block">Germain</span>
      </h1>
      {/* Réserve la hauteur de ligne avant montage pour éviter tout saut. */}
      <p className="mt-3 font-display text-base italic text-[var(--muted-foreground)] first-letter:uppercase">
        {date ?? " "}
      </p>
    </div>
  );
}
