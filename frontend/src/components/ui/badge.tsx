import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium", {
  variants: {
    variant: {
      neutral: "bg-slate-100 text-slate-600",
      navy: "bg-navy-900 text-white",
      turquoise: "bg-turquoise-500/10 text-turquoise-600",
      orange: "bg-orange-500/10 text-orange-600",
      success: "bg-success-50 text-success-500",
      warning: "bg-warning-50 text-warning-500",
      danger: "bg-danger-50 text-danger-500",
    },
  },
  defaultVariants: { variant: "neutral" },
});

export type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>;

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
