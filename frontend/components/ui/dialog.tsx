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
  const panelRef = React.useRef<HTMLDivElement>(null);
  const previousFocusRef = React.useRef<HTMLElement | null>(null);
  const onCloseRef = React.useRef(onClose);
  const titleId = React.useId();

  React.useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  React.useEffect(() => {
    if (!open) return;
    previousFocusRef.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;
      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(
          "button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), " +
            "textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
        ),
      ).filter((element) => !element.hasAttribute("hidden"));
      if (focusable.length === 0) {
        e.preventDefault();
        panelRef.current.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || !panelRef.current.contains(active))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handler);
    const frame = window.requestAnimationFrame(() => {
      const initial = panelRef.current?.querySelector<HTMLElement>(
        "[data-autofocus], [data-dialog-close], button:not([disabled]), " +
          "input:not([disabled]), select:not([disabled]), textarea:not([disabled])",
      );
      (initial ?? panelRef.current)?.focus();
    });
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", handler);
      document.body.style.overflow = previousOverflow;
      previousFocusRef.current?.focus();
    };
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-40 flex items-end sm:items-center justify-center p-4">
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
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            aria-label="Fenêtre de dialogue"
            tabIndex={-1}
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
            <DialogContext.Provider value={{ titleId }}>{children}</DialogContext.Provider>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

const DialogContext = React.createContext<{ titleId?: string }>({});

export function DialogHeader({
  children,
  onClose,
  className,
}: {
  children: React.ReactNode;
  onClose?: () => void;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-2 p-5 pb-2", className)}>
      <div className="flex-1">{children}</div>
      {onClose && (
        <button
          type="button"
          data-dialog-close
          data-ui-control
          onClick={onClose}
          className="grid h-9 w-9 shrink-0 place-items-center rounded-[var(--radius-sm)] text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)] transition-colors"
          aria-label="Fermer"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}

export function DialogTitle({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const { titleId } = React.useContext(DialogContext);
  return (
    <h2 id={titleId} className={cn("font-display text-lg text-[var(--foreground)]", className)}>
      {children}
    </h2>
  );
}

export function DialogBody({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("px-5 pb-2", className)}>{children}</div>;
}

export function DialogFooter({
  children,
  className,
}: {
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
