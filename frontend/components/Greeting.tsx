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

  useEffect(() => {
    const hour = new Date().getHours();
    setGreeting(getGreeting(hour));
  }, []);

  return (
    <h1 className="text-2xl font-semibold tracking-tight">
      {greeting}, Germain
    </h1>
  );
}
