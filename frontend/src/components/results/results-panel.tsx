"use client";

import { useState } from "react";
import type { Simulation } from "@/domain/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { KpiCards } from "./kpi-cards";
import { PalletNavigator } from "./pallet-navigator";
import { PlacedCartonsTable } from "./placed-cartons-table";
import { UnplacedCartonsTable } from "./unplaced-cartons-table";
import { PrintSummary } from "./print-summary";
import { PalletViewer } from "@/components/three/pallet-viewer";
import { Download, Play, Printer, AlertTriangle } from "lucide-react";
import { downloadTextFile } from "@/lib/download";
import { exportPlacedCartonsToCsv, exportResultToJson, exportUnplacedCartonsToCsv } from "@/lib/import-export/export-result";
import { PRACTICAL_INSTANCE_LIMIT } from "@/domain/constants";

export function ResultsPanel({
  simulation,
  isRunning,
  onRun,
}: {
  simulation: Simulation;
  isRunning: boolean;
  onRun: () => void;
}) {
  const result = simulation.lastResult;
  const [selectedPalletIndex, setSelectedPalletIndex] = useState(0);
  const [lastSeenResult, setLastSeenResult] = useState(result);

  // Revient à la première palette lorsqu'un nouveau résultat arrive (ajustement d'état pendant
  // le rendu, préféré à un effect pour éviter un rendu en cascade — voir la doc React).
  if (result !== lastSeenResult) {
    setLastSeenResult(result);
    setSelectedPalletIndex(0);
  }

  const totalQuantity = simulation.cartonLines.reduce((sum, l) => sum + (Number.isFinite(l.quantity) ? l.quantity : 0), 0);
  const selectedPallet = result?.pallets[Math.min(selectedPalletIndex, Math.max(0, result.pallets.length - 1))];

  return (
    <div className="flex flex-col gap-5">
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
          <div>
            <p className="text-sm text-navy-900">
              {totalQuantity} carton(s) dans la commande, {simulation.cartonLines.length} référence(s).
            </p>
            {totalQuantity > PRACTICAL_INSTANCE_LIMIT && (
              <p className="mt-1 flex items-center gap-1 text-xs text-warning-500">
                <AlertTriangle className="h-3.5 w-3.5" />
                Commande volumineuse : le mode rapide est recommandé pour rester fluide.
              </p>
            )}
          </div>
          <div className="flex gap-2">
            {result && (
              <>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => downloadTextFile(`${simulation.name}.json`, exportResultToJson(simulation), "application/json")}
                >
                  <Download className="h-3.5 w-3.5" />
                  Export JSON
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() =>
                    downloadTextFile(`${simulation.name}-cartons-places.csv`, exportPlacedCartonsToCsv(result), "text/csv;charset=utf-8")
                  }
                >
                  <Download className="h-3.5 w-3.5" />
                  Export CSV (placés)
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() =>
                    downloadTextFile(`${simulation.name}-cartons-non-places.csv`, exportUnplacedCartonsToCsv(result), "text/csv;charset=utf-8")
                  }
                >
                  <Download className="h-3.5 w-3.5" />
                  Export CSV (non placés)
                </Button>
                <Button size="sm" variant="secondary" onClick={() => window.print()}>
                  <Printer className="h-3.5 w-3.5" />
                  Imprimer la fiche
                </Button>
              </>
            )}
            <Button size="sm" onClick={onRun} disabled={isRunning || simulation.cartonLines.length === 0}>
              <Play className="h-3.5 w-3.5" />
              {result ? "Relancer l'optimisation" : "Lancer l'optimisation"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {isRunning && (
        <Card>
          <CardContent className="py-4">
            <p className="mb-2 text-sm text-navy-800">
              Calcul en cours sur le serveur de palettisation… (le backend ne rapporte pas de
              progression détaillée, seulement le résultat final)
            </p>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div className="h-full w-1/3 animate-pulse rounded-full bg-turquoise-500" />
            </div>
          </CardContent>
        </Card>
      )}

      {!result && !isRunning && (
        <Card>
          <CardContent className="py-14 text-center text-sm text-slate-500">
            Aucun résultat pour le moment. Configurez votre commande puis lancez l&apos;optimisation.
          </CardContent>
        </Card>
      )}

      {result && (
        <>
          {result.warnings.length > 0 && (
            <div className="flex flex-col gap-2">
              {result.warnings.map((warning, i) => (
                <p key={i} className="flex items-start gap-2 rounded-md bg-warning-50 px-3 py-2 text-sm text-warning-500">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  {warning}
                </p>
              ))}
            </div>
          )}

          <KpiCards result={result} />

          {result.pallets.length > 0 && selectedPallet && (
            <Card>
              <CardHeader>
                <CardTitle>Palettes générées</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <PalletNavigator pallets={result.pallets} selectedIndex={selectedPallet.index} onSelect={setSelectedPalletIndex} />

                <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                  <MiniStat label="Cartons" value={String(selectedPallet.placedCartons.length)} />
                  <MiniStat label="Poids" value={`${selectedPallet.totalWeightKg.toFixed(1)} kg`} />
                  <MiniStat label="Occupation volumique" value={`${(selectedPallet.volumeUsageRatio * 100).toFixed(1)} %`} />
                  <MiniStat label="Hauteur utilisée" value={`${Math.round(selectedPallet.maxHeightUsedMm)} mm`} />
                </div>

                <PalletViewer pallet={selectedPallet} />

                <details>
                  <summary className="cursor-pointer text-sm font-medium text-navy-800">Détail des cartons placés (tableau)</summary>
                  <div className="mt-3">
                    <PlacedCartonsTable pallet={selectedPallet} />
                  </div>
                </details>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Cartons non placés</CardTitle>
            </CardHeader>
            <CardContent>
              <UnplacedCartonsTable cartons={result.unplacedCartons} />
            </CardContent>
          </Card>
        </>
      )}

      <PrintSummary simulation={simulation} />
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
