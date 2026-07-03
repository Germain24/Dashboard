"use client";

import * as React from "react";
import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { cn } from "@/lib/utils";
import { springs, durations, EASE_OUT } from "@/lib/motion/tokens";

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

  return (
    <AnimatePresence>
      {open && (
        <div
          className="fixed inset-0 z-40 flex items-end sm:items-center justify-center p-4"
          role="dialog"
          aria-modal
        >
          {/* Backdrop : voile flouté, le contenu reste deviné derrière le verre */}
          <motion.div
            data-testid="dialog-backdrop"
            className="glass-veil absolute inset-0"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: durations.fast, ease: EASE_OUT }}
            onClick={onClose}
            aria-hidden
          />
          {/* Panel : verre épais, ressort amorti sans rebond */}
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: 6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, y: 4 }}
            transition={springs.soft}
            className={cn(
              "glass-modal relative z-10 w-full max-w-lg rounded-[var(--radius-lg)]",
              // On mobile: bottom sheet; sm+: centered modal
              "max-h-[90dvh] overflow-y-auto",
              className,
            )}
          >
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
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
