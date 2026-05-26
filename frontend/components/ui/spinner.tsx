import * as React from "react";
import { cn } from "@/lib/utils";

interface SpinnerProps {
  className?: string;
  size?: "sm" | "md" | "lg";
  /** Inline label shown next to the spinner */
  label?: string;
}

export function Spinner({ className, size = "md", label }: SpinnerProps) {
  const sizeClass = {
    sm: "h-3 w-3 border",
    md: "h-4 w-4 border-2",
    lg: "h-6 w-6 border-2",
  }[size];

  return (
    <span
      className={cn("inline-flex items-center gap-2 text-[var(--muted-foreground)]", className)}
      role="status"
      aria-label={label ?? "Chargement"}
    >
      <span
        className={cn(
          "rounded-full border-[var(--border)] border-t-[var(--muted-foreground)] animate-spin",
          sizeClass,
        )}
      />
      {label && <span className="text-sm">{label}</span>}
    </span>
  );
}
