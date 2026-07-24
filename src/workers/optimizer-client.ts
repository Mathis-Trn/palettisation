import type { CartonLine, OptimizationResult, OptimizerProgress, SimulationSettings } from "@/domain/types";
import type { WorkerRequest, WorkerResponse } from "./optimizer.worker";
import { optimizePallets } from "@/optimizer";

let cachedWorker: Worker | null = null;

function getWorker(): Worker | null {
  if (typeof window === "undefined") return null;
  if (typeof Worker === "undefined") return null;
  if (!cachedWorker) {
    cachedWorker = new Worker(new URL("./optimizer.worker.ts", import.meta.url), { type: "module" });
  }
  return cachedWorker;
}

/**
 * Exécute le moteur d'optimisation hors du thread principal via un Web Worker, pour ne jamais
 * bloquer l'interface. Se replie sur un calcul synchrone si les Web Workers ne sont pas disponibles
 * (rendu serveur, environnement de test).
 */
export function runOptimization(
  cartonLines: CartonLine[],
  settings: SimulationSettings,
  onProgress?: (progress: OptimizerProgress) => void
): Promise<OptimizationResult> {
  const worker = getWorker();
  if (!worker) {
    return Promise.resolve(optimizePallets(cartonLines, settings, onProgress));
  }

  const requestId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;

  return new Promise((resolve, reject) => {
    const handleMessage = (event: MessageEvent<WorkerResponse>) => {
      const data = event.data;
      if (data.requestId !== requestId) return;

      if (data.type === "progress") {
        onProgress?.(data.progress);
        return;
      }
      worker.removeEventListener("message", handleMessage);
      if (data.type === "done") {
        resolve(data.result);
      } else if (data.type === "error") {
        reject(new Error(data.message));
      }
    };

    worker.addEventListener("message", handleMessage);
    const request: WorkerRequest = { type: "run", requestId, cartonLines, settings };
    worker.postMessage(request);
  });
}
