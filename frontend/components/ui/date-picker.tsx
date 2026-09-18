"use client";

import * as React from "react";
import { CalendarIcon, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

/** Calendrier déroulant accessible, avec saisie clavier et date minimale. */

const JOURS = [
  { court: "L", complet: "Lundi" },
  { court: "M", complet: "Mardi" },
  { court: "M", complet: "Mercredi" },
  { court: "J", complet: "Jeudi" },
  { court: "V", complet: "Vendredi" },
  { court: "S", complet: "Samedi" },
  { court: "D", complet: "Dimanche" },
];

function parseDate(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
    return null;
  }
  return date;
}

function toValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function compareDates(left: Date, right: Date): number {
  return toValue(left).localeCompare(toValue(right));
}

function shiftMonth(date: Date, amount: number): Date {
  const year = date.getFullYear();
  const month = date.getMonth() + amount;
  const day = date.getDate();
  const lastDay = new Date(year, month + 1, 0).getDate();
  return new Date(year, month, Math.min(day, lastDay));
}

function firstAllowedDate(selected: Date | null, minDate: Date | null): Date {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const candidate = selected ?? today;
  return minDate && compareDates(candidate, minDate) < 0 ? minDate : candidate;
}

function datesForMonth(month: Date): (Date | null)[][] {
  const first = startOfMonth(month);
  const offset = (first.getDay() + 6) % 7;
  const daysInMonth = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
  const cells: (Date | null)[] = Array(42).fill(null);
  for (let day = 1; day <= daysInMonth; day += 1) {
    cells[offset + day - 1] = new Date(first.getFullYear(), first.getMonth(), day);
  }
  return Array.from({ length: 6 }, (_, week) => cells.slice(week * 7, week * 7 + 7));
}

function formatDate(value: string, options: Intl.DateTimeFormatOptions): string {
  const date = parseDate(value);
  return date ? new Intl.DateTimeFormat("fr-CA", options).format(date) : "";
}

function monthLabel(date: Date): string {
  return new Intl.DateTimeFormat("fr-CA", { month: "long", year: "numeric" }).format(date);
}

function fullDateLabel(date: Date): string {
  return new Intl.DateTimeFormat("fr-CA", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

function focusDateButton(root: HTMLDivElement | null, value: string): void {
  if (!root) return;
  root.querySelector<HTMLButtonElement>(`[data-calendar-date="${value}"]`)?.focus();
}

export function DatePicker({
  value,
  onChange,
  min,
  label,
  id,
}: {
  value: string;
  onChange: (value: string) => void;
  min?: string;
  label?: string;
  id?: string;
}) {
  const generatedId = React.useId();
  const triggerId = id ?? generatedId;
  const calendarId = `${triggerId}-calendar`;
  const monthId = `${triggerId}-month`;
  const [open, setOpen] = React.useState(false);
  const [alignRight, setAlignRight] = React.useState(false);
  const selected = parseDate(value);
  const minDate = min ? parseDate(min) : null;
  const [viewMonth, setViewMonth] = React.useState(() => startOfMonth(firstAllowedDate(selected, minDate)));
  const [focusedDate, setFocusedDate] = React.useState(() => firstAllowedDate(selected, minDate));
  const rootRef = React.useRef<HTMLDivElement>(null);
  const triggerRef = React.useRef<HTMLButtonElement>(null);

  React.useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  React.useEffect(() => {
    if (!open) return;
    const frame = window.requestAnimationFrame(() => focusDateButton(rootRef.current, toValue(focusedDate)));
    return () => window.cancelAnimationFrame(frame);
  }, [focusedDate, open, viewMonth]);

  const changeViewMonth = (amount: number) => {
    const nextFocus = shiftMonth(focusedDate, amount);
    const validFocus = minDate && compareDates(nextFocus, minDate) < 0 ? minDate : nextFocus;
    setFocusedDate(validFocus);
    setViewMonth(startOfMonth(validFocus));
  };

  const openCalendar = () => {
    const initial = firstAllowedDate(selected, minDate);
    const triggerBounds = triggerRef.current?.getBoundingClientRect();
    setAlignRight(Boolean(triggerBounds && triggerBounds.left + 256 > window.innerWidth - 12));
    setFocusedDate(initial);
    setViewMonth(startOfMonth(initial));
    setOpen(true);
  };

  const moveFocus = (amount: number) => {
    const candidate = new Date(focusedDate);
    candidate.setDate(candidate.getDate() + amount);
    const next = minDate && compareDates(candidate, minDate) < 0 ? minDate : candidate;
    setFocusedDate(next);
    setViewMonth(startOfMonth(next));
  };

  const moveToWeekEdge = (edge: "start" | "end") => {
    const mondayOffset = (focusedDate.getDay() + 6) % 7;
    const candidate = new Date(focusedDate);
    candidate.setDate(candidate.getDate() + (edge === "start" ? -mondayOffset : 6 - mondayOffset));
    const next = minDate && compareDates(candidate, minDate) < 0 ? minDate : candidate;
    setFocusedDate(next);
    setViewMonth(startOfMonth(next));
  };

  const handleDateKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    switch (event.key) {
      case "ArrowLeft":
        event.preventDefault();
        moveFocus(-1);
        break;
      case "ArrowRight":
        event.preventDefault();
        moveFocus(1);
        break;
      case "ArrowUp":
        event.preventDefault();
        moveFocus(-7);
        break;
      case "ArrowDown":
        event.preventDefault();
        moveFocus(7);
        break;
      case "Home":
        event.preventDefault();
        moveToWeekEdge("start");
        break;
      case "End":
        event.preventDefault();
        moveToWeekEdge("end");
        break;
      case "PageUp":
        event.preventDefault();
        changeViewMonth(event.shiftKey ? -12 : -1);
        break;
      case "PageDown":
        event.preventDefault();
        changeViewMonth(event.shiftKey ? 12 : 1);
        break;
    }
  };

  const previousMonth = new Date(viewMonth.getFullYear(), viewMonth.getMonth() - 1, 1);
  const previousMonthDisabled = Boolean(minDate && compareDates(previousMonth, startOfMonth(minDate)) < 0);
  const todayValue = toValue(new Date());

  return (
    <div className="relative" ref={rootRef}>
      {label && (
        <label htmlFor={triggerId} className="text-sm">
          {label}
        </label>
      )}
      <button
        ref={triggerRef}
        type="button"
        id={triggerId}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={calendarId}
        onClick={open ? () => setOpen(false) : openCalendar}
        className={cn(
          "mt-1 flex min-h-10 w-full items-center justify-between gap-2 rounded-lg border border-[var(--border)]",
          "bg-[var(--background)] p-2 text-left text-sm focus-visible:outline-2 focus-visible:outline-[var(--ring)]",
        )}
      >
        <span className={value ? "" : "text-[var(--muted-foreground)]"}>
          {selected ? formatDate(value, { day: "numeric", month: "short", year: "numeric" }) : "Choisir une date"}
        </span>
        <CalendarIcon className="h-4 w-4 shrink-0 text-[var(--muted-foreground)]" aria-hidden="true" />
      </button>

      {open && (
        <div
          id={calendarId}
          role="dialog"
          aria-label={`Calendrier${label ? ` — ${label}` : ""}`}
          className={cn(
            "absolute z-20 mt-1 w-64 max-w-[calc(100vw-2rem)] rounded-lg border border-[var(--border)] bg-[var(--card)] p-2 shadow-lg",
            alignRight ? "right-0" : "left-0",
          )}
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => changeViewMonth(-1)}
              disabled={previousMonthDisabled}
              className="rounded p-1.5 hover:bg-[var(--muted)] focus-visible:outline-2 focus-visible:outline-[var(--ring)] disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Mois précédent"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            </button>
            <span id={monthId} className="text-sm font-medium capitalize" aria-live="polite">
              {monthLabel(viewMonth)}
            </span>
            <button
              type="button"
              onClick={() => changeViewMonth(1)}
              className="rounded p-1.5 hover:bg-[var(--muted)] focus-visible:outline-2 focus-visible:outline-[var(--ring)]"
              aria-label="Mois suivant"
            >
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>

          <div role="grid" aria-labelledby={monthId} className="space-y-0.5">
            <div role="row" className="grid grid-cols-7 text-center text-xs text-[var(--muted-foreground)]">
              {JOURS.map((jour) => (
                <div key={jour.complet} role="columnheader" aria-label={jour.complet} className="py-1">
                  {jour.court}
                </div>
              ))}
            </div>
            {datesForMonth(viewMonth).map((week, weekIndex) => (
              <div key={weekIndex} role="row" className="grid grid-cols-7 gap-0.5">
                {week.map((date, dayIndex) => {
                  if (!date) {
                    return <div key={`empty-${dayIndex}`} role="gridcell" aria-disabled="true" className="aspect-square" />;
                  }

                  const dateValue = toValue(date);
                  const disabled = Boolean(minDate && compareDates(date, minDate) < 0);
                  const isSelected = dateValue === value;
                  const isFocused = dateValue === toValue(focusedDate);
                  const isToday = dateValue === todayValue;
                  return (
                    <div key={dateValue} role="gridcell" aria-selected={isSelected}>
                      <button
                        type="button"
                        data-calendar-date={dateValue}
                        disabled={disabled}
                        tabIndex={isFocused ? 0 : -1}
                        aria-label={fullDateLabel(date)}
                        aria-pressed={isSelected}
                        aria-current={isToday ? "date" : undefined}
                        onKeyDown={handleDateKeyDown}
                        onFocus={() => setFocusedDate(date)}
                        onClick={() => {
                          onChange(dateValue);
                          setOpen(false);
                          window.requestAnimationFrame(() => triggerRef.current?.focus());
                        }}
                        className={cn(
                          "aspect-square w-full rounded text-sm focus-visible:outline-2 focus-visible:outline-[var(--ring)]",
                          !disabled && "hover:bg-[var(--muted)]",
                          disabled && "cursor-not-allowed text-[var(--muted-foreground)] opacity-40",
                          isToday && !isSelected && "ring-1 ring-inset ring-[var(--ring)]",
                          isSelected && "bg-[var(--primary)] text-[var(--primary-foreground)] hover:bg-[var(--primary)]",
                        )}
                      >
                        {date.getDate()}
                      </button>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
