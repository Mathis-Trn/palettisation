import { cn } from "@/lib/utils";

export function ProgressBar({ value, className, tone = "turquoise" }: { value: number; className?: string; tone?: "turquoise" | "orange" | "navy" }) {
  const pct = Math.max(0, Math.min(100, value * 100));
  const toneClass = tone === "orange" ? "bg-orange-500" : tone === "navy" ? "bg-navy-700" : "bg-turquoise-500";
  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-slate-100", className)}>
      <div className={cn("h-full rounded-full transition-all", toneClass)} style={{ width: `${pct}%` }} />
    </div>
  );
}
