"use client";

import { useId, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { springs, durations, EASE_OUT } from "@/lib/motion/tokens";

interface CollapsibleSectionProps {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
  className?: string;
}

/**
 * Section repliable pour les pages denses (densité 2.6) : en-tête Title,
 * chevron à ressort, hauteur animée. Reduced-motion : bascule sèche.
 */
export function CollapsibleSection({
  title,
  defaultOpen = false,
  children,
  className,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const reduced = useReducedMotion();
  const id = useId();

  return (
    <section
      className={cn(
        "rounded-[var(--radius-lg)] border border-[var(--border)]",
        className,
      )}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold text-[var(--foreground)]"
      >
        {title}
        <motion.span
          animate={{ rotate: open ? 180 : 0 }}
          transition={reduced ? { duration: 0 } : springs.soft}
          aria-hidden
        >
          <ChevronDown className="h-4 w-4 text-[var(--muted-foreground)]" />
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={id}
            initial={reduced ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={reduced ? undefined : { height: 0, opacity: 0 }}
            transition={{ duration: durations.fast, ease: EASE_OUT }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
