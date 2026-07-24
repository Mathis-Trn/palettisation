"use client";

import { useMemo, useState } from "react";
import type { PalletResult } from "@/domain/types";
import { PalletScene3D, type SceneDisplayOptions } from "./pallet-scene-3d";
import { SkuLegend } from "./sku-legend";
import { LayerControls } from "./layer-controls";
import { CartonInfoPanel } from "./carton-info-panel";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { FRAGILE_EDGE_COLOR } from "./sku-colors";

export function PalletViewer({ pallet }: { pallet: PalletResult }) {
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | null>(null);
  const [hiddenSkus, setHiddenSkus] = useState<Set<string>>(new Set());
  const [colorBySku, setColorBySku] = useState(true);
  const [showDimensionsCage, setShowDimensionsCage] = useState(true);
  const [showAxes, setShowAxes] = useState(true);
  const [layerIndex, setLayerIndex] = useState<number | null>(null);
  const [explodeFactor, setExplodeFactor] = useState(0);
  const [resetSignal, setResetSignal] = useState(0);

  const skus = useMemo(() => Array.from(new Set(pallet.placedCartons.map((c) => c.sku))).sort(), [pallet]);
  const layerCount = useMemo(() => new Set(pallet.placedCartons.map((c) => Math.round(c.position.z))).size, [pallet]);
  const selectedCarton = pallet.placedCartons.find((c) => c.instanceId === selectedInstanceId) ?? null;

  const options: SceneDisplayOptions = { showDimensionsCage, showAxes, colorBySku, hiddenSkus, layerIndex, explodeFactor };

  function toggleSku(sku: string) {
    setHiddenSkus((prev) => {
      const next = new Set(prev);
      if (next.has(sku)) next.delete(sku);
      else next.add(sku);
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-5 rounded-md border border-slate-200 bg-white px-4 py-3 text-sm">
        <ToggleField label="Colorer par SKU" checked={colorBySku} onCheckedChange={setColorBySku} />
        <ToggleField label="Dimensions et limites" checked={showDimensionsCage} onCheckedChange={setShowDimensionsCage} />
        <ToggleField label="Axes" checked={showAxes} onCheckedChange={setShowAxes} />
        <span className="flex items-center gap-1.5 text-xs text-slate-500">
          <span className="inline-block h-2.5 w-2.5 rounded-full border-2" style={{ borderColor: FRAGILE_EDGE_COLOR }} />
          Contour orange = carton fragile
        </span>
      </div>

      <PalletScene3D
        pallet={pallet}
        options={options}
        selectedInstanceId={selectedInstanceId}
        onSelect={setSelectedInstanceId}
        resetSignal={resetSignal}
      />

      <LayerControls
        layerCount={layerCount}
        layerIndex={layerIndex}
        onLayerChange={setLayerIndex}
        explodeFactor={explodeFactor}
        onExplodeChange={setExplodeFactor}
        onResetCamera={() => setResetSignal((s) => s + 1)}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Légende des références (clic pour masquer)</p>
          <SkuLegend skus={skus} hiddenSkus={hiddenSkus} onToggle={toggleSku} />
        </div>
        <CartonInfoPanel carton={selectedCarton} />
      </div>
    </div>
  );
}

function ToggleField({ label, checked, onCheckedChange }: { label: string; checked: boolean; onCheckedChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-2">
      <Switch checked={checked} onCheckedChange={onCheckedChange} />
      <Label className="text-xs">{label}</Label>
    </label>
  );
}
