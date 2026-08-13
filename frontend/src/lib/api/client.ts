/**
 * Client HTTP typé vers le backend Python headless. Remplace l'ancien
 * `src/workers/optimizer-client.ts` : plus aucun calcul n'est effectué côté navigateur, ce module
 * ne fait que sérialiser la requête, appeler l'API, et désérialiser la réponse.
 */

import type { CartonLine, OptimizationResult, PalletResult, Simulation, TransportLoadResult, VehicleConfig } from "@/domain/types";
import type {
  CapabilitiesResponseContract,
  ErrorResponseContract,
  HealthResponseContract,
  JobCreatedResponseContract,
  JobStatusResponseContract,
  PalletizeRequestContract,
  PalletizeResponseContract,
  ParseCsvResponseContract,
  TransportLoadRequestContract,
  TransportLoadResponseContract,
} from "./contract-types";
import {
  cartonLineToOrderLineContract,
  contractToOptimizationResult,
  contractToTransportLoadResult,
  palletConfigToContract,
  palletResultToLoadContract,
  settingsToOptionsContract,
  transportModeToShippingMode,
  vehicleToContract,
} from "./to-domain";

// Timeout réseau court, pour les petites requêtes de création/consultation de job (jamais pour le
// calcul lui-même, qui s'exécute de façon asynchrone côté serveur — voir `createPalletizationJob`
// / `getPalletizationJob` ci-dessous et `usePalletizationJob`). Piloté par
// `NEXT_PUBLIC_API_REQUEST_TIMEOUT_MS` (15s par défaut).
const DEFAULT_TIMEOUT_MS = Number(process.env.NEXT_PUBLIC_API_REQUEST_TIMEOUT_MS) || 15_000;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number | null,
    public readonly code: string | null,
    public readonly correlationId: string | null
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function getBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_PALLETIZER_API_URL;
  if (!url) {
    throw new ApiError(
      "NEXT_PUBLIC_PALLETIZER_API_URL n'est pas configurée : impossible de joindre le backend.",
      null,
      "MISSING_API_URL",
      null
    );
  }
  return url.replace(/\/$/, "");
}

async function request<T>(
  path: string,
  init: RequestInit,
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<T> {
  const url = `${getBaseUrl()}${path}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(
        `Le serveur n'a pas répondu dans le délai imparti (${timeoutMs / 1000}s).`,
        null,
        "TIMEOUT",
        null
      );
    }
    throw new ApiError(
      "Impossible de joindre le backend. Vérifiez qu'il est démarré et accessible.",
      null,
      "NETWORK_ERROR",
      null
    );
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    let detail: ErrorResponseContract | null = null;
    try {
      detail = (await response.json()) as ErrorResponseContract;
    } catch {
      detail = null;
    }
    throw new ApiError(
      detail?.error?.message ?? `Erreur backend (HTTP ${response.status}).`,
      response.status,
      detail?.error?.code ?? null,
      detail?.error?.correlation_id ?? null
    );
  }

  return (await response.json()) as T;
}

export async function healthCheck(): Promise<HealthResponseContract> {
  return request<HealthResponseContract>("/health", { method: "GET" }, 5_000);
}

export async function getCapabilities(): Promise<CapabilitiesResponseContract> {
  return request<CapabilitiesResponseContract>("/api/v1/capabilities", { method: "GET" }, 5_000);
}

export async function parseCsv(file: File): Promise<ParseCsvResponseContract> {
  const formData = new FormData();
  formData.append("file", file);
  return request<ParseCsvResponseContract>("/api/v1/orders/parse-csv", {
    method: "POST",
    body: formData,
  });
}

function buildPalletizeRequest(
  orderId: string,
  shippingMode: PalletizeRequestContract["order"]["shippingMode"],
  lines: CartonLine[],
  simulation: Simulation
): PalletizeRequestContract {
  return {
    contractVersion: "1.0",
    order: {
      orderId,
      shippingMode,
      lines: lines.map((line, index) => cartonLineToOrderLineContract(line, index + 1)),
    },
    pallet: palletConfigToContract(simulation.settings.palletConfig),
    options: settingsToOptionsContract(simulation),
  };
}

export async function palletize(simulation: Simulation): Promise<OptimizationResult> {
  const request_ = buildPalletizeRequest(
    simulation.id,
    transportModeToShippingMode(simulation.settings.transportMode),
    simulation.cartonLines,
    simulation
  );
  const response = await request<PalletizeResponseContract>("/api/v1/palletize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request_),
  });
  return contractToOptimizationResult(response);
}

export async function palletizeCsv(
  file: File,
  orderId: string | undefined,
  simulation: Simulation
): Promise<OptimizationResult> {
  const formData = new FormData();
  formData.append("file", file);
  if (orderId) formData.append("orderId", orderId);
  formData.append(
    "optimizationLevel",
    simulation.settings.optimizationLevel === "approfondi" ? "thorough" : "fast"
  );
  formData.append(
    "minimumSupportRatio",
    String(simulation.settings.palletConfig.minimumSupportRatio)
  );
  const response = await request<PalletizeResponseContract>("/api/v1/palletize/csv", {
    method: "POST",
    body: formData,
  });
  return contractToOptimizationResult(response);
}

/** Démarre un calcul asynchrone : répond immédiatement (202), le résultat est récupéré plus tard
 * par `getPalletizationJob` (voir `usePalletizationJob`). Remplace l'ancien appel synchrone
 * `palletize()` pour le parcours normal de l'interface (le calcul peut durer plusieurs minutes,
 * jamais tenu dans une seule requête HTTP). */
export async function createPalletizationJob(
  simulation: Simulation
): Promise<JobCreatedResponseContract> {
  const request_ = buildPalletizeRequest(
    simulation.id,
    transportModeToShippingMode(simulation.settings.transportMode),
    simulation.cartonLines,
    simulation
  );
  return request<JobCreatedResponseContract>("/api/v1/palletization-jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request_),
  });
}

export async function getPalletizationJob(jobId: string): Promise<JobStatusResponseContract> {
  return request<JobStatusResponseContract>(
    `/api/v1/palletization-jobs/${encodeURIComponent(jobId)}`,
    { method: "GET" }
  );
}

export async function cancelPalletizationJob(jobId: string): Promise<JobStatusResponseContract> {
  return request<JobStatusResponseContract>(
    `/api/v1/palletization-jobs/${encodeURIComponent(jobId)}`,
    { method: "DELETE" }
  );
}

export async function computeTransportLoad(
  pallets: PalletResult[],
  vehicle: VehicleConfig
): Promise<TransportLoadResult> {
  const body: TransportLoadRequestContract = {
    contractVersion: "1.0",
    pallets: pallets.map(palletResultToLoadContract),
    vehicle: vehicleToContract(vehicle),
  };
  const response = await request<TransportLoadResponseContract>("/api/v1/transport/load", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return contractToTransportLoadResult(response);
}
