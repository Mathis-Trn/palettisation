import type { OptimizationResult } from "@/domain/types";
import { Card, CardContent } from "@/components/ui/card";
import { formatInt, formatKg, formatPercent } from "@/lib/format";

export function KpiCards({ result }: { result: OptimizationResult }) {
  const avgFootprint =
    result.pallets.length > 0 ? result.pallets.reduce((sum, p) => sum + p.footprintUsageRatio, 0) / result.pallets.length : 0;

  const items = [
    { label: "Cartons commandés", value: formatInt(result.totalCartonsCount) },
    { label: "Cartons placés", value: formatInt(result.placedCartonsCount), tone: "success" as const },
    { label: "Cartons non placés", value: formatInt(result.unplacedCartonsCount), tone: result.unplacedCartonsCount > 0 ? "warning" as const : undefined },
    { label: "Palettes générées", value: formatInt(result.palletsCount) },
    { label: "Occupation volumique", value: formatPercent(result.globalVolumeUsageRatio) },
    { label: "Occupation surface au sol (moy.)", value: formatPercent(avgFootprint) },
    { label: "Poids total", value: formatKg(result.totalWeightKg) },
    { label: "Durée du calcul", value: `${formatInt(result.durationMs)} ms` },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {items.map((item) => (
        <Card key={item.label}>
          <CardContent className="py-3">
            <p className="text-xs text-slate-500">{item.label}</p>
            <p
              className={
                "mt-1 text-xl font-semibold " +
                (item.tone === "success" ? "text-success-500" : item.tone === "warning" ? "text-warning-500" : "text-navy-950")
              }
            >
              {item.value}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
