import * as React from "react";
import { cn } from "@/lib/utils";

export interface SelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
}

const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, id, children, ...props }, ref) => {
    const selectId = id ?? label?.toLowerCase().replace(/\s+/g, "-");
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label
            htmlFor={selectId}
            className="text-xs font-medium text-[var(--muted-foreground)]"
          >
            {label}
          </label>
        )}
        <select
          id={selectId}
          ref={ref}
          className={cn(
            "h-8 w-full appearance-none rounded-[var(--radius)] border border-[var(--border)]",
            "bg-[var(--field)] px-3 py-1 text-sm text-[var(--foreground)]",
            "transition-[border-color,box-shadow] duration-200 ease-[var(--ease-out)]",
            "focus:border-[var(--ring)] focus:outline-none",
            "focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--ring)_12%,transparent)]",
            "disabled:cursor-not-allowed disabled:opacity-50",
            "cursor-pointer",
            error && "border-[var(--destructive)]",
            className,
          )}
          {...props}
        >
          {children}
        </select>
        {error && (
          <p className="text-xs text-[var(--destructive)]">{error}</p>
        )}
      </div>
    );
  },
);
Select.displayName = "Select";

export { Select };
