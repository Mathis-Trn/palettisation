"use client";

import { useRouter } from "next/navigation";
import { useSimulationStore } from "@/store/simulation-store";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DeleteSimulationDialog } from "./delete-simulation-dialog";
import { formatDateFr, formatInt, TRANSPORT_MODE_LABELS } from "@/lib/format";
import { DEMO_CARTON_LINES, DEMO_SIMULATION_NAME } from "@/lib/demo-data";
import { Boxes, Copy, FolderOpen, PackagePlus, Sparkles } from "lucide-react";
import { v4 as uuid } from "uuid";

export function DashboardView() {
  const router = useRouter();
  const hasHydrated = useSimulationStore((s) => s.hasHydrated);
  const simulations = useSimulationStore((s) => s.simulations);
  const createSimulation = useSimulationStore((s) => s.createSimulation);
  const duplicateSimulation = useSimulationStore((s) => s.duplicateSimulation);
  const deleteSimulation = useSimulationStore((s) => s.deleteSimulation);
  const replaceCartonLines = useSimulationStore((s) => s.replaceCartonLines);

  function handleNewSimulation() {
    const id = createSimulation();
    router.push(`/simulation/${id}`);
  }

  function handleLoadDemo() {
    const id = createSimulation(DEMO_SIMULATION_NAME);
    replaceCartonLines(
      id,
      DEMO_CARTON_LINES.map((line) => ({ ...line, id: uuid() }))
    );
    router.push(`/simulation/${id}`);
  }

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-navy-950">Palettisation 3D</h1>
          <p className="mt-1 text-sm text-slate-600">
            Portail de simulation de palettisation pour la préparation de vos commandes de transport routier, maritime ou aérien.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={handleLoadDemo}>
            <Sparkles className="h-4 w-4" />
            Démonstration
          </Button>
          <Button onClick={handleNewSimulation}>
            <PackagePlus className="h-4 w-4" />
            Nouvelle simulation
          </Button>
        </div>
      </header>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Simulations sauvegardées</h2>

        {!hasHydrated && <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">Chargement…</div>}

        {hasHydrated && simulations.length === 0 && (
          <Card>
            <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
              <Boxes className="h-10 w-10 text-slate-300" />
              <p className="text-sm text-slate-600">
                Aucune simulation pour le moment. Créez-en une nouvelle ou chargez le jeu de données de démonstration pour découvrir
                l&apos;application.
              </p>
              <div className="mt-2 flex gap-2">
                <Button variant="secondary" onClick={handleLoadDemo}>
                  Charger la démonstration
                </Button>
                <Button onClick={handleNewSimulation}>Nouvelle simulation</Button>
              </div>
            </CardContent>
          </Card>
        )}

        {hasHydrated && simulations.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {simulations.map((sim) => {
              const cartonCount = sim.cartonLines.reduce((sum, l) => sum + l.quantity, 0);
              return (
                <Card key={sim.id} className="flex flex-col">
                  <CardContent className="flex flex-1 flex-col gap-3">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-medium text-navy-900">{sim.name}</h3>
                      <Badge variant="navy">{TRANSPORT_MODE_LABELS[sim.settings.transportMode]}</Badge>
                    </div>
                    <p className="text-xs text-slate-500">Mise à jour le {formatDateFr(sim.updatedAtIso)}</p>
                    <div className="mt-1 flex gap-4 text-sm text-slate-600">
                      <div>
                        <div className="text-lg font-semibold text-navy-950">{formatInt(cartonCount)}</div>
                        <div className="text-xs text-slate-500">carton(s)</div>
                      </div>
                      <div>
                        <div className="text-lg font-semibold text-navy-950">{sim.lastResult ? formatInt(sim.lastResult.palletsCount) : "—"}</div>
                        <div className="text-xs text-slate-500">palette(s)</div>
                      </div>
                    </div>
                    <div className="mt-auto flex items-center justify-between pt-3">
                      <Button size="sm" variant="secondary" onClick={() => router.push(`/simulation/${sim.id}`)}>
                        <FolderOpen className="h-3.5 w-3.5" />
                        Ouvrir
                      </Button>
                      <div className="flex items-center gap-1">
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label={`Dupliquer ${sim.name}`}
                          onClick={() => duplicateSimulation(sim.id)}
                        >
                          <Copy className="h-4 w-4 text-slate-500" />
                        </Button>
                        <DeleteSimulationDialog name={sim.name} onConfirm={() => deleteSimulation(sim.id)} />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}
