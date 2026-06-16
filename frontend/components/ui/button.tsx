import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { Spinner } from "./spinner";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2 rounded-[var(--radius)] text-sm font-medium",
    "cursor-pointer select-none",
    "transition-[background-color,border-color,color,box-shadow,transform,opacity] duration-200 ease-[var(--ease-out)]",
    "disabled:pointer-events-none disabled:opacity-50",
    "active:scale-[0.98]",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]",
  ],
  {
    variants: {
      variant: {
        default:
          "bg-[var(--primary)] text-[var(--primary-foreground)] shadow-sm hover:shadow-[var(--shadow-md)] hover:-translate-y-px hover:bg-[color-mix(in_srgb,var(--primary)_90%,var(--background))]",
        secondary:
          "border border-[var(--border)] bg-[var(--field)] text-[var(--foreground)] shadow-sm hover:bg-[var(--accent)] hover:border-[color-mix(in_srgb,var(--ring)_30%,transparent)]",
        outline:
          "border border-[var(--border)] bg-transparent text-[var(--foreground)] hover:bg-[var(--accent)] hover:border-[color-mix(in_srgb,var(--ring)_30%,transparent)]",
        ghost:
          "bg-transparent text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]",
        destructive:
          "bg-[var(--destructive)] text-[var(--destructive-foreground)] shadow-sm hover:shadow-[var(--shadow-md)] hover:-translate-y-px",
        success:
          "bg-[var(--success)] text-[var(--success-foreground)] shadow-sm hover:shadow-[var(--shadow-md)] hover:-translate-y-px",
        link:
          "text-[var(--ring)] underline-offset-4 hover:underline p-0 h-auto",
      },
      size: {
        sm: "h-7 px-3 text-xs",
        md: "h-8 px-3.5",
        lg: "h-10 px-5 text-base",
        icon: "h-8 w-8",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, loading, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        aria-busy={loading}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      >
        {loading ? (
          <>
            <Spinner size="sm" className="opacity-70" />
            {children}
          </>
        ) : (
          children
        )}
      </button>
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
