"use client";

import { type ReactNode } from "react";
import { SpatialGrid } from "@/components/deck/SpatialGrid";

export function Deck({ intro }: { intro?: ReactNode }) {
  return <SpatialGrid intro={intro} />;
}
