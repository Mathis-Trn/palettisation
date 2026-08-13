"use client";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Layers, RotateCcw } from "lucide-react";

export function LayerControls({
  layerCount,
  layerIndex,
  onLayerChange,
  explodeFactor,
  onExplodeChange,
  onResetCamera,
}: {
  layerCount: number;
  layerIndex: number | null;
  onLayerChange: (index: number | null) => void;
  explodeFactor: number;
  onExplodeChange: (value: number) => void;
  onResetCamera: () => void;
}) {
  return (
    <div className="flex w-full min-w-0 flex-wrap items-center gap-4 rounded-md border border-slate-200 bg-white px-4 py-3">
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <Layers className="h-4 w-4 shrink-0 text-slate-500" />
        <Label className="text-xs">Couche</Label>
        <Button size="sm" variant={layerIndex === null ? "turquoise" : "secondary"} onClick={() => onLayerChange(null)}>
          Toutes
        </Button>
        {Array.from({ length: layerCount }, (_, i) => (
          <Button key={i} size="sm" variant={layerIndex === i ? "turquoise" : "secondary"} onClick={() => onLayerChange(i)}>
            {i + 1}
          </Button>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <Label className="text-xs">Explosion verticale</Label>
        <input
          type="range"
          min={0}
          max={3}
          step={0.1}
          value={explodeFactor}
          onChange={(e) => onExplodeChange(Number(e.target.value))}
          className="w-32 accent-turquoise-500"
        />
      </div>

      <Button size="sm" variant="ghost" onClick={onResetCamera}>
        <RotateCcw className="h-3.5 w-3.5" />
        Réinitialiser la caméra
      </Button>
    </div>
  );
}
