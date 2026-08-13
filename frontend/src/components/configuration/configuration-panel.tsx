"use client";

import { useMemo, useState } from "react";
import type { PalletConfig, Simulation, TransportMode } from "@/domain/types";
import { useSimulationStore } from "@/store/simulation-store";
import { PALLET_PRESETS } from "@/domain/constants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { TRANSPORT_MODE_LABELS } from "@/lib/format";

const PALLET_FORMAT_OPTIONS = [
  { value: "routier", label: "Palette transport routier (800×1200, 1100 mm max)" },
  { value: "maritime", label: "Palette transport maritime / aérien (800×1200, 1600 mm max)" },
  { value: "custom", label: "Format personnalisé" },
] as const;

function detectFormat(simulation: Simulation): "routier" | "maritime" | "custom" {
  const { dimensions } = simulation.settings.palletConfig;
  const isPreset = (preset: Pick<PalletConfig, "dimensions">) =>
    dimensions.length === preset.dimensions.length &&
    dimensions.width === preset.dimensions.width &&
    dimensions.height === preset.dimensions.height;
  if (isPreset(PALLET_PRESETS.routier)) return "routier";
  if (isPreset(PALLET_PRESETS.maritime)) return "maritime";
  return "custom";
}

export function ConfigurationPanel({ simulation }: { simulation: Simulation }) {
  const updateSettings = useSimulationStore((s) => s.updateSettings);
  const [formatChoice, setFormatChoice] = useState(() => detectFormat(simulation));
  const { settings } = simulation;
  const { palletConfig } = settings;

  const oversizedCartons = useMemo(() => {
    const maxDim = Math.max(palletConfig.dimensions.length, palletConfig.dimensions.width, palletConfig.dimensions.height);
    return simulation.cartonLines.filter((line) => {
      const minLineDim = Math.min(line.dimensions.length, line.dimensions.width, line.dimensions.height);
      const maxLineDim = Math.max(line.dimensions.length, line.dimensions.width, line.dimensions.height);
      return maxLineDim > maxDim && minLineDim > 0;
    });
  }, [simulation.cartonLines, palletConfig.dimensions]);

  function patchPallet(patch: Partial<typeof palletConfig>) {
    updateSettings(simulation.id, { palletConfig: { ...palletConfig, ...patch } });
  }

  function handleTransportModeChange(mode: TransportMode) {
    const preset = mode === "routier" ? PALLET_PRESETS.routier : PALLET_PRESETS.maritime;
    updateSettings(simulation.id, { transportMode: mode, palletConfig: { ...preset } });
    setFormatChoice(mode === "routier" ? "routier" : "maritime");
  }

  function handleFormatChange(value: (typeof PALLET_FORMAT_OPTIONS)[number]["value"]) {
    setFormatChoice(value);
    if (value === "routier") patchPallet({ ...PALLET_PRESETS.routier });
    else if (value === "maritime") patchPallet({ ...PALLET_PRESETS.maritime });
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Transport et format de palette</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div>
            <Label>Mode de transport</Label>
            <Select value={settings.transportMode} onValueChange={(v) => handleTransportModeChange(v as TransportMode)}>
              <SelectTrigger className="mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(TRANSPORT_MODE_LABELS) as TransportMode[]).map((mode) => (
                  <SelectItem key={mode} value={mode}>
                    {TRANSPORT_MODE_LABELS[mode]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label>Format de palette</Label>
            <Select value={formatChoice} onValueChange={(v) => handleFormatChange(v as typeof formatChoice)}>
              <SelectTrigger className="mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PALLET_FORMAT_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <NumberField
              label="Longueur (mm)"
              value={palletConfig.dimensions.length}
              onChange={(v) => {
                setFormatChoice("custom");
                patchPallet({ dimensions: { ...palletConfig.dimensions, length: v } });
              }}
            />
            <NumberField
              label="Largeur (mm)"
              value={palletConfig.dimensions.width}
              onChange={(v) => {
                setFormatChoice("custom");
                patchPallet({ dimensions: { ...palletConfig.dimensions, width: v } });
              }}
            />
            <NumberField
              label="Hauteur max. totale (mm)"
              value={palletConfig.dimensions.height}
              onChange={(v) => {
                setFormatChoice("custom");
                patchPallet({ dimensions: { ...palletConfig.dimensions, height: v } });
              }}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <NumberField
              label="Hauteur palette vide (mm)"
              value={palletConfig.emptyPalletHeightMm}
              onChange={(v) => patchPallet({ emptyPalletHeightMm: v })}
            />
            <label className="flex items-center justify-between gap-3 px-3 py-2">
              <span className="text-xs text-slate-600">La hauteur max. inclut la palette</span>
              <Switch
                checked={palletConfig.maxHeightIncludesPallet}
                onCheckedChange={(v) => patchPallet({ maxHeightIncludesPallet: v })}
              />
            </label>
          </div>

          {oversizedCartons.length > 0 && (
            <p className="rounded-md bg-warning-50 px-3 py-2 text-xs text-warning-500">
              {oversizedCartons.length} référence(s) semblent plus grandes que la palette dans toutes les orientations :{" "}
              {oversizedCartons.map((c) => c.sku).join(", ")}.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Contraintes de chargement</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <NumberField
            label="Charge maximale de la palette (kg)"
            value={palletConfig.maxWeightKg ?? 0}
            onChange={(v) => patchPallet({ maxWeightKg: v > 0 ? v : undefined })}
            hint="Valeur indicative, à ajuster selon votre cahier des charges — laissez à 0 pour ne pas limiter."
          />
          <div className="grid grid-cols-2 gap-3">
            <NumberField label="Débordement autorisé (mm)" value={palletConfig.overhangMm} onChange={(v) => patchPallet({ overhangMm: v })} />
            <NumberField
              label="Espace de sécurité entre cartons (mm)"
              value={palletConfig.safetyGapMm}
              onChange={(v) => patchPallet({ safetyGapMm: v })}
            />
          </div>
          <NumberField
            label="Ratio de support minimal (0 à 1)"
            value={palletConfig.minimumSupportRatio}
            step={0.05}
            onChange={(v) => patchPallet({ minimumSupportRatio: Math.min(1, Math.max(0, v)) })}
            hint="Surface minimale de contact requise sous un carton empilé. Défaut : 0.8 (approximation logicielle, voir README)."
          />
          <NumberField
            label="Poids max. toléré au-dessus d'un carton fragile (kg)"
            value={settings.fragileMaxWeightOnTopKg}
            onChange={(v) => updateSettings(simulation.id, { fragileMaxWeightOnTopKg: Math.max(0, v) })}
          />

          <div className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2">
            <span className="text-sm text-navy-800">Autoriser les rotations</span>
            <Switch
              checked={settings.globalRotationsEnabled}
              onCheckedChange={(v) => updateSettings(simulation.id, { globalRotationsEnabled: v })}
            />
          </div>

          <div>
            <Label>Niveau d&apos;optimisation</Label>
            <Select
              value={settings.optimizationLevel}
              onValueChange={(v) => updateSettings(simulation.id, { optimizationLevel: v as "rapide" | "approfondi" })}
            >
              <SelectTrigger className="mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="rapide">Rapide (une seule stratégie de tri)</SelectItem>
                <SelectItem value="approfondi">Approfondi (plusieurs stratégies, conserve la meilleure)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
  step = 1,
  hint,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  step?: number;
  hint?: string;
}) {
  return (
    <div>
      <Label>{label}</Label>
      <Input
        type="number"
        step={step}
        className="mt-1"
        value={Number.isFinite(value) ? value : 0}
        onChange={(e) => {
          const parsed = Number(e.target.value);
          onChange(Number.isFinite(parsed) ? parsed : 0);
        }}
      />
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}
