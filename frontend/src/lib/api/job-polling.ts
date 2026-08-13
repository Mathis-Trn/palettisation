/**
 * Logique de polling pure (sans React, sans minuteur) : facilement testable en isolation.
 * `use-palletization-job.ts` orchestre les effets (intervalles, fetch) autour de ces fonctions.
 */

import type { OptimizationResult } from "@/domain/types";
import type { JobStatusResponseContract } from "./contract-types";
import { contractToOptimizationResult } from "./to-domain";

export type JobOutcome =
  | { kind: "continue" }
  | { kind: "succeeded"; result: OptimizationResult }
  | { kind: "error"; message: string };

/**
 * Décide quoi faire d'une réponse de statut de job. N'affiche une erreur que pour `failed`,
 * `expired`, `cancelled`, ou un statut inconnu/réponse invalide — jamais pour `queued`/`running`.
 */
export function interpretJobStatus(response: JobStatusResponseContract): JobOutcome {
  switch (response.status) {
    case "queued":
    case "running":
      return { kind: "continue" };
    case "succeeded":
      if (!response.result) {
        return {
          kind: "error",
          message: "Réponse invalide du serveur : résultat manquant pour un calcul réussi.",
        };
      }
      return { kind: "succeeded", result: contractToOptimizationResult(response.result) };
    case "failed":
      return { kind: "error", message: response.error?.message ?? "Le calcul a échoué." };
    case "expired":
      return {
        kind: "error",
        message: response.error?.message ?? "Le calcul a dépassé le délai maximal autorisé.",
      };
    case "cancelled":
      return { kind: "error", message: "Le calcul a été annulé." };
    default:
      return { kind: "error", message: `Statut de calcul inattendu : ${String(response.status)}` };
  }
}

export const MAX_NETWORK_RETRY_ATTEMPTS = 5;

/**
 * Délai borné (backoff exponentiel plafonné) avant la prochaine tentative après une panne réseau
 * transitoire. `attempt` est le nombre d'échecs consécutifs (1 = premier échec). Renvoie `null`
 * au-delà de `MAX_NETWORK_RETRY_ATTEMPTS` : la panne est alors considérée persistante.
 */
export function nextRetryDelayMs(attempt: number): number | null {
  if (attempt < 1 || attempt > MAX_NETWORK_RETRY_ATTEMPTS) return null;
  return Math.min(2_000 * 2 ** (attempt - 1), 15_000);
}

export const NETWORK_RETRY_MESSAGE = "Connexion au serveur momentanément indisponible, nouvelle tentative…";

export const PERSISTENT_NETWORK_ERROR_MESSAGE =
  "Impossible de joindre le serveur après plusieurs tentatives. Le calcul continue peut-être " +
  "côté serveur ; rechargez la page dans quelques instants pour reprendre le suivi.";
