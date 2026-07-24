"use client";

import { useState } from "react";
import type { Simulation } from "@/domain/types";
import { TRANSPORT_VEHICLE_PRESETS } from "@/domain/constants";
import { computeTransportLoad } from "@/transport-loader";
import type { TransportLoadResult, VehicleConfig } from "@/transport-loader/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { VehicleFloorPlan } from "./vehicle-floor-plan";
import { Truck } from "lucide-react";
import { formatInt, formatPercent } from "@/lib/format";

const CUSTOM_PRESET_VALUE = "custom";

export function TransportPanel({ simulation }: { simulation: Simulation }) {
  const [vehicle, setVehicle] = useState<VehicleConfig>({
    name: TRANSPORT_VEHICLE_PRESETS[0].name,
    innerLengthMm: TRANSPORT_VEHICLE_PRESETS[0].innerLengthMm,
    innerWidthMm: TRANSPORT_VEHICLE_PRESETS[0].innerWidthMm,
    innerHeightMm: TRANSPORT_VEHICLE_PRESETS[0].innerHeightMm,
    maxPayloadKg: TRANSPORT_VEHICLE_PRESETS[0].maxPayloadKg,
    allowPalletRotationFloor: true,
    allowPalletStacking: false,
  });
  const [presetName, setPresetName] = useState<string>(TRANSPORT_VEHICLE_PRESETS[0].name);
  const [result, setResult] = useState<TransportLoadResult | null>(null);

  const pallets = simulation.lastResult?.pallets ?? [];

  function applyPreset(name: string) {
    setPresetName(name);
    if (name === CUSTOM_PRESET_VALUE) return;
    const preset = TRANSPORT_VEHICLE_PRESETS.find((p) => p.name === name);
    if (preset) setVehicle((v) => ({ ...v, ...preset, name: preset.name }));
  }

  function patchVehicle(patch: Partial<VehicleConfig>) {
    setPresetName(CUSTOM_PRESET_VALUE);
    setVehicle((v) => ({ ...v, ...patch }));
  }

  function handleCompute() {
    setResult(computeTransportLoad(pallets, vehicle));
  }

  return (
    <div className="flex flex-col gap-5">
      <Card>
        <CardHeader>
          <CardTitle>Véhicule / conteneur</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div>
            <Label>Préréglage</Label>
            <Select value={presetName} onValueChange={applyPreset}>
              <SelectTrigger className="mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TRANSPORT_VEHICLE_PRESETS.map((preset) => (
                  <SelectItem key={preset.name} value={preset.name}>
                    {preset.name}
                  </SelectItem>
                ))}
                <SelectItem value={CUSTOM_PRESET_VALUE}>Personnalisé</SelectItem>
              </SelectContent>
            </Select>
            <p className="mt-1 text-xs text-slate-500">
              Dimensions fournies à titre indicatif — à vérifier systématiquement selon le transporteur réel.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <NumberField label="Longueur intérieure (mm)" value={vehicle.innerLengthMm} onChange={(v) => patchVehicle({ innerLengthMm: v })} />
            <NumberField label="Largeur intérieure (mm)" value={vehicle.innerWidthMm} onChange={(v) => patchVehicle({ innerWidthMm: v })} />
            <NumberField label="Hauteur intérieure (mm)" value={vehicle.innerHeightMm} onChange={(v) => patchVehicle({ innerHeightMm: v })} />
            <NumberField label="Charge utile max. (kg)" value={vehicle.maxPayloadKg} onChange={(v) => patchVehicle({ maxPayloadKg: v })} />
          </div>

          <div className="flex flex-wrap gap-6">
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={vehicle.allowPalletRotationFloor} onCheckedChange={(v) => patchVehicle({ allowPalletRotationFloor: v })} />
              Pivoter les palettes au sol
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={vehicle.allowPalletStacking} onCheckedChange={(v) => patchVehicle({ allowPalletStacking: v })} />
              Autoriser l&apos;empilage de palettes
            </label>
          </div>

          <div>
            <Button onClick={handleCompute} disabled={pallets.length === 0}>
              <Truck className="h-4 w-4" />
              Calculer le chargement
            </Button>
            {pallets.length === 0 && <p className="mt-2 text-xs text-slate-500">Lancez d&apos;abord une optimisation dans l&apos;onglet Résultats.</p>}
          </div>
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <CardTitle>Plan de chargement</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <MiniStat label="Palettes chargeables" value={formatInt(result.palletsLoadable)} />
              <MiniStat label="Véhicules nécessaires" value={formatInt(result.vehiclesNeeded)} />
              <MiniStat label="Palettes restantes" value={formatInt(result.unassignedPalletIndexes.length)} />
              <MiniStat label="Palettes au total" value={formatInt(pallets.length)} />
            </div>

            {result.vehicles.map((v) => (
              <div key={v.index} className="flex flex-col gap-2">
                <p className="text-sm font-medium text-navy-900">
                  Véhicule {v.index + 1} — {formatPercent(v.usedFloorAreaRatio)} de la surface au sol, {v.usedWeightKg.toFixed(0)} kg
                </p>
                <VehicleFloorPlan vehicle={vehicle} result={v} />
              </div>
            ))}

            {result.unassignedPalletIndexes.length > 0 && (
              <p className="rounded-md bg-warning-50 px-3 py-2 text-sm text-warning-500">
                {result.unassignedPalletIndexes.length} palette(s) n&apos;ont pas pu être chargées : palette(s){" "}
                {result.unassignedPalletIndexes.map((i) => i + 1).join(", ")}.
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div>
      <Label>{label}</Label>
      <Input type="number" className="mt-1" value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-slate-50 px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="font-semibold text-navy-950">{value}</p>
    </div>
  );
}
