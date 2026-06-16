"use client";

import * as React from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

/* ── Overlay ─────────────────────────────────────────────── */
interface DialogProps {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  className?: string;
}

export function Dialog({ open, onClose, children, className }: DialogProps) {
  React.useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-40 flex items-end sm:items-center justify-center p-4"
      role="dialog"
      aria-modal
    >
      {/* Backdrop : voile flouté, le contenu reste deviné derrière le verre */}
      <div
        className="absolute inset-0 bg-black/30 backdrop-blur-[6px] animate-fade-in"
        onClick={onClose}
        aria-hidden
      />
      {/* Panel : verre épais */}
      <div
        className={cn(
          "glass-modal relative z-10 w-full max-w-lg rounded-[var(--radius-lg)]",
          "animate-scale-in",
          // On mobile: bottom sheet; sm+: centered modal
          "max-h-[90dvh] overflow-y-auto",
          className,
        )}
      >
        {children}
      </div>
    </div>
  );
}

export function DialogHeader({ children, onClose, className }: {
  children: React.ReactNode;
  onClose?: () => void;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-2 p-5 pb-2", className)}>
      <div className="flex-1">{children}</div>
      {onClose && (
        <button
          onClick={onClose}
          className="shrink-0 rounded-[var(--radius-sm)] p-1 text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)] transition-colors"
          aria-label="Fermer"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

export function DialogTitle({ children, className }: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <h2 className={cn("font-display text-lg text-[var(--foreground)]", className)}>
      {children}
    </h2>
  );
}

export function DialogBody({ children, className }: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("px-5 pb-2", className)}>{children}</div>;
}

export function DialogFooter({ children, className }: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-end gap-2 border-t border-[var(--glass-border)] p-5 pt-3",
        className,
      )}
    >
      {children}
    </div>
  );
}
