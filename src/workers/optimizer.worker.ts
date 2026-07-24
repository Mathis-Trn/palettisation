import { optimizePallets } from "@/optimizer";
import type { CartonLine, OptimizationResult, OptimizerProgress, SimulationSettings } from "@/domain/types";

export type WorkerRequest = {
  type: "run";
  requestId: string;
  cartonLines: CartonLine[];
  settings: SimulationSettings;
};

export type WorkerResponse =
  | { type: "progress"; requestId: string; progress: OptimizerProgress }
  | { type: "done"; requestId: string; result: OptimizationResult }
  | { type: "error"; requestId: string; message: string };

self.onmessage = (event: MessageEvent<WorkerRequest>) => {
  const { type, requestId, cartonLines, settings } = event.data;
  if (type !== "run") return;

  try {
    const result = optimizePallets(cartonLines, settings, (progress) => {
      const message: WorkerResponse = { type: "progress", requestId, progress };
      self.postMessage(message);
    });
    const message: WorkerResponse = { type: "done", requestId, result };
    self.postMessage(message);
  } catch (error) {
    const message: WorkerResponse = {
      type: "error",
      requestId,
      message: error instanceof Error ? error.message : "Erreur inconnue pendant l'optimisation.",
    };
    self.postMessage(message);
  }
};

export {};
