"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Simulation } from "@/domain/types";
import { useSimulationStore } from "@/store/simulation-store";
import { ApiError, cancelPalletizationJob, createPalletizationJob, getPalletizationJob } from "./client";
import type { JobStatusResponseContract } from "./contract-types";
import {
  NETWORK_RETRY_MESSAGE,
  PERSISTENT_NETWORK_ERROR_MESSAGE,
  interpretJobStatus,
  nextRetryDelayMs,
} from "./job-polling";

const POLL_INTERVAL_MS = Number(process.env.NEXT_PUBLIC_JOB_POLL_INTERVAL_MS) || 2_000;

export type JobPhase = "idle" | "queued" | "running" | "error";

/**
 * Remplace le parcours synchrone (`palletize()` + un seul `fetch` maintenu ouvert) par :
 * création du job → mémorisation du `jobId` (persisté avec la simulation) → polling du statut →
 * récupération du résultat une fois `succeeded`. Doit être instancié dans un composant qui ne
 * démonte jamais pendant le calcul (voir `SimulationWorkspace` : `TabsContent` de Radix démonte
 * les onglets inactifs, donc ce hook ne doit pas vivre dans `ResultsPanel`).
 */
export function usePalletizationJob(simulation: Simulation | undefined) {
  const setResult = useSimulationStore((s) => s.setResult);
  const setActiveJob = useSimulationStore((s) => s.setActiveJob);
  const clearActiveJob = useSimulationStore((s) => s.clearActiveJob);

  const [phase, setPhase] = useState<JobPhase>(simulation?.activeJobId ? "queued" : "idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [networkMessage, setNetworkMessage] = useState<string | null>(null);
  const [canCancel, setCanCancel] = useState(false);
  // Compteur purement interne : sa valeur n'est jamais lue, il ne sert qu'à déclencher un nouveau
  // rendu chaque seconde pendant qu'un job est actif, pour que `elapsedSeconds` (calculé plus bas
  // directement depuis l'horodatage serveur) reste à jour.
  const [, forceElapsedTick] = useState(0);

  const simulationId = simulation?.id ?? null;
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);
  const submittingRef = useRef(false);
  const trackedJobIdRef = useRef<string | null>(null);
  // La simulation peut se rafraîchir (nouvel id de store) pendant qu'un polling est en cours ; ce
  // ref permet à `poll` (identité stable, voir plus bas) de toujours lire le dernier id sans être
  // recréé à chaque rendu.
  const simulationIdRef = useRef(simulationId);
  useEffect(() => {
    simulationIdRef.current = simulationId;
  }, [simulationId]);

  const stopPolling = useCallback(() => {
    if (pollTimeoutRef.current !== null) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
  }, []);

  // Identité stable (dépendances vides) : tout ce que cette fonction lit est soit un ref (toujours
  // à jour), soit un setter d'état ou une action de store (stables entre les rendus). La récursion
  // passe par le nom de la fonction elle-même (`poll`), pas par la variable externe.
  const poll = useCallback(async function poll(jobId: string, failureCount: number): Promise<void> {
    if (!isMountedRef.current) return;

    let response: JobStatusResponseContract;
    try {
      response = await getPalletizationJob(jobId);
    } catch (error) {
      const isTransientNetworkIssue =
        error instanceof ApiError && (error.code === "NETWORK_ERROR" || error.code === "TIMEOUT");
      if (!isTransientNetworkIssue) {
        if (isMountedRef.current) {
          setErrorMessage(
            error instanceof ApiError ? error.message : "Erreur inattendue pendant le suivi du calcul."
          );
          setPhase("error");
        }
        if (simulationIdRef.current) clearActiveJob(simulationIdRef.current);
        trackedJobIdRef.current = null;
        return;
      }

      const nextAttempt = failureCount + 1;
      const delay = nextRetryDelayMs(nextAttempt);
      if (delay === null) {
        // Panne réseau persistante : ne jamais relancer automatiquement une deuxième
        // optimisation — l'utilisateur doit recharger la page pour reprendre le suivi.
        if (isMountedRef.current) {
          setNetworkMessage(null);
          setErrorMessage(PERSISTENT_NETWORK_ERROR_MESSAGE);
          setPhase("error");
        }
        return;
      }
      if (isMountedRef.current) setNetworkMessage(NETWORK_RETRY_MESSAGE);
      pollTimeoutRef.current = setTimeout(() => void poll(jobId, nextAttempt), delay);
      return;
    }

    if (!isMountedRef.current) return;
    setNetworkMessage(null);
    setCanCancel(response.status === "queued");

    const outcome = interpretJobStatus(response);
    if (outcome.kind === "continue") {
      setPhase(response.status === "running" ? "running" : "queued");
      pollTimeoutRef.current = setTimeout(() => void poll(jobId, 0), POLL_INTERVAL_MS);
      return;
    }

    trackedJobIdRef.current = null;
    if (simulationIdRef.current) clearActiveJob(simulationIdRef.current);
    if (outcome.kind === "succeeded") {
      if (simulationIdRef.current) setResult(simulationIdRef.current, outcome.result);
      setPhase("idle");
    } else {
      setErrorMessage(outcome.message);
      setPhase("error");
    }
  }, [clearActiveJob, setResult]);

  // Démarre (ou reprend, après un rafraîchissement de page) le polling dès qu'un `activeJobId`
  // apparaît sur la simulation et n'est pas déjà suivi par cette instance du hook.
  useEffect(() => {
    const activeId = simulation?.activeJobId;
    if (activeId && trackedJobIdRef.current !== activeId) {
      trackedJobIdRef.current = activeId;
      setErrorMessage(null);
      setNetworkMessage(null);
      setPhase("queued");
      void poll(activeId, 0);
    }
  }, [simulation?.activeJobId, poll]);

  // Tant qu'un job est actif, force un nouveau rendu chaque seconde pour rafraîchir
  // `elapsedSeconds` (calculé ci-dessous à partir de l'horodatage serveur, jamais stocké comme
  // état dérivé indépendant).
  useEffect(() => {
    if (!simulation?.activeJobId || !simulation.activeJobCreatedAtIso) return;
    const interval = setInterval(() => forceElapsedTick((t) => t + 1), 1000);
    return () => clearInterval(interval);
  }, [simulation?.activeJobId, simulation?.activeJobCreatedAtIso]);

  const elapsedSeconds =
    simulation?.activeJobId && simulation.activeJobCreatedAtIso
      ? Math.max(0, (Date.now() - new Date(simulation.activeJobCreatedAtIso).getTime()) / 1000)
      : 0;

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      stopPolling();
    };
  }, [stopPolling]);

  const start = useCallback(async () => {
    // Empêche un double clic (ou un second appel concurrent) de créer deux jobs.
    if (!simulation || submittingRef.current || simulation.activeJobId) return;
    submittingRef.current = true;
    setErrorMessage(null);
    setNetworkMessage(null);
    try {
      const created = await createPalletizationJob(simulation);
      setActiveJob(simulation.id, created.jobId, created.createdAt);
    } catch (error) {
      setErrorMessage(
        error instanceof ApiError ? error.message : "Erreur inattendue au lancement du calcul."
      );
      setPhase("error");
    } finally {
      submittingRef.current = false;
    }
  }, [simulation, setActiveJob]);

  const cancel = useCallback(async () => {
    const jobId = trackedJobIdRef.current ?? simulation?.activeJobId;
    if (!jobId) return;
    try {
      await cancelPalletizationJob(jobId);
    } catch {
      // Best-effort : le prochain tick de polling détectera l'état final du job de toute façon.
    }
  }, [simulation?.activeJobId]);

  return {
    phase,
    isRunning: phase === "queued" || phase === "running",
    elapsedSeconds,
    errorMessage,
    networkMessage,
    canCancel,
    start,
    cancel,
  };
}
