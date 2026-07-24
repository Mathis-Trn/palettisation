"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useSimulationStore } from "@/store/simulation-store";
import { runOptimization } from "@/workers/optimizer-client";
import type { OptimizerProgress } from "@/domain/types";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConfigurationPanel } from "@/components/configuration/configuration-panel";
import { OrderTable } from "@/components/order-table/order-table";
import { ResultsPanel } from "@/components/results/results-panel";
import { TransportPanel } from "@/components/transport/transport-panel";
import { ArrowLeft } from "lucide-react";
import { TRANSPORT_MODE_LABELS } from "@/lib/format";
import { Badge } from "@/components/ui/badge";

export function SimulationWorkspace({ simulationId }: { simulationId: string }) {
  const router = useRouter();
  const hasHydrated = useSimulationStore((s) => s.hasHydrated);
  const simulation = useSimulationStore((s) => s.simulations.find((sim) => sim.id === simulationId));
  const renameSimulation = useSimulationStore((s) => s.renameSimulation);
  const setResult = useSimulationStore((s) => s.setResult);

  const [activeTab, setActiveTab] = useState("commande");
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState<OptimizerProgress | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  useEffect(() => {
    if (hasHydrated && !simulation) {
      router.replace("/");
    }
  }, [hasHydrated, simulation, router]);

  if (!hasHydrated || !simulation) {
    return <div className="flex flex-1 items-center justify-center text-sm text-slate-500">Chargement…</div>;
  }

  async function handleRun() {
    if (!simulation) return;
    setIsRunning(true);
    setRunError(null);
    setProgress(null);
    try {
      const result = await runOptimization(simulation.cartonLines, simulation.settings, setProgress);
      setResult(simulation.id, result);
      setActiveTab("resultats");
    } catch (error) {
      setRunError(error instanceof Error ? error.message : "Erreur inattendue pendant l'optimisation.");
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-8">
      <header className="flex flex-col gap-3">
        <Link href="/" className="flex w-fit items-center gap-1 text-sm text-slate-500 hover:text-navy-900">
          <ArrowLeft className="h-4 w-4" />
          Tableau de bord
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <input
            className="rounded-md border border-transparent bg-transparent px-1 text-xl font-semibold text-navy-950 hover:border-slate-200 focus-visible:border-slate-300 focus-visible:outline-none"
            value={simulation.name}
            onChange={(e) => renameSimulation(simulation.id, e.target.value)}
            aria-label="Nom de la simulation"
          />
          <Badge variant="navy">{TRANSPORT_MODE_LABELS[simulation.settings.transportMode]}</Badge>
        </div>
        {runError && <p className="rounded-md bg-danger-50 px-3 py-2 text-sm text-danger-500">{runError}</p>}
      </header>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="configuration">Configuration</TabsTrigger>
          <TabsTrigger value="commande">Commande</TabsTrigger>
          <TabsTrigger value="resultats">Résultats</TabsTrigger>
          <TabsTrigger value="transport">Transport</TabsTrigger>
        </TabsList>

        <TabsContent value="configuration">
          <ConfigurationPanel simulation={simulation} />
        </TabsContent>

        <TabsContent value="commande">
          <OrderTable simulation={simulation} />
        </TabsContent>

        <TabsContent value="resultats">
          <ResultsPanel simulation={simulation} isRunning={isRunning} progress={progress} onRun={handleRun} />
        </TabsContent>

        <TabsContent value="transport">
          <TransportPanel simulation={simulation} />
        </TabsContent>
      </Tabs>
    </main>
  );
}
