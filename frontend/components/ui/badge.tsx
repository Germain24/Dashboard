import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-[var(--radius-sm)] px-2 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--muted)] text-[var(--muted-foreground)]",
        primary:
          "bg-[var(--primary)] text-[var(--primary-foreground)]",
        success:
          "bg-[var(--success-muted)] text-[var(--success-foreground)]",
        warning:
          "bg-[var(--warning-muted)] text-[var(--warning-foreground)]",
        destructive:
          "bg-[var(--destructive-muted)] text-[var(--destructive-foreground)]",
        info:
          "bg-[var(--info-muted)] text-[var(--info-foreground)]",
        outline:
          "border border-[var(--border)] text-[var(--muted-foreground)] bg-transparent",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
