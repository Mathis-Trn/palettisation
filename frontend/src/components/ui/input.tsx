import * as React from "react";
import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean };

export const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, invalid, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-9 w-full rounded-md border bg-white px-3 text-sm text-navy-950 shadow-sm transition-colors placeholder:text-slate-400",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-turquoise-500",
      invalid ? "border-danger-500" : "border-slate-300",
      "disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400",
      className
    )}
    {...props}
  />
));
Input.displayName = "Input";
