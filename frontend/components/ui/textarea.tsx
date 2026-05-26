import * as React from "react";
import { cn } from "@/lib/utils";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, label, error, id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, "-");
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label
            htmlFor={inputId}
            className="text-xs font-medium text-[var(--muted-foreground)]"
          >
            {label}
          </label>
        )}
        <textarea
          id={inputId}
          ref={ref}
          className={cn(
            "w-full rounded-[var(--radius)] border border-[var(--border)]",
            "bg-transparent px-3 py-2 text-sm text-[var(--foreground)]",
            "placeholder:text-[var(--muted-foreground)]",
            "transition-colors focus:border-[var(--ring)] focus:outline-none",
            "disabled:cursor-not-allowed disabled:opacity-50 resize-y min-h-[80px]",
            error && "border-[var(--destructive)]",
            className,
          )}
          {...props}
        />
        {error && (
          <p className="text-xs text-[var(--destructive)]">{error}</p>
        )}
      </div>
    );
  },
);
Textarea.displayName = "Textarea";

export { Textarea };
