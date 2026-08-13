"use client";

import { Eye, EyeOff } from "lucide-react";
import { colorForSku } from "./sku-colors";
import { Button } from "@/components/ui/button";

export function SkuLegend({
  skus,
  hiddenSkus,
  onToggle,
}: {
  skus: string[];
  hiddenSkus: Set<string>;
  onToggle: (sku: string) => void;
}) {
  if (skus.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {skus.map((sku) => {
        const hidden = hiddenSkus.has(sku);
        return (
          <Button
            key={sku}
            size="sm"
            variant="secondary"
            className={hidden ? "opacity-50" : undefined}
            onClick={() => onToggle(sku)}
          >
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: colorForSku(sku) }} />
            {sku}
            {hidden ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
          </Button>
        );
      })}
    </div>
  );
}
