import { Loader2 } from "lucide-react";

/**
 * État de calcul en cours. Ne prétend jamais connaître une progression réelle : pas de barre, pas
 * de pourcentage simulé — seulement un spinner, un message stable et le temps écoulé (mesuré côté
 * client, pas estimé). Le backend ne rapporte qu'un statut (`queued`/`running`/...), jamais un
 * taux d'avancement, car le moteur ne dispose d'aucune mesure fiable de progression.
 */
export function OptimizationLoader({ elapsedSeconds }: { elapsedSeconds: number }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-[180px] flex-col items-center justify-center gap-2 py-10 text-center"
    >
      <Loader2
        aria-hidden="true"
        className="h-7 w-7 animate-spin text-turquoise-500 motion-reduce:animate-none"
      />
      <p className="text-sm font-medium text-navy-900">Calcul de la palettisation en cours…</p>
      <p className="max-w-sm text-xs text-slate-500">
        Cette opération peut prendre plusieurs minutes pour une commande volumineuse.
      </p>
      <p className="text-xs text-slate-400" aria-hidden="true">
        Temps écoulé : {formatElapsedSeconds(elapsedSeconds)}
      </p>
      <span className="sr-only">
        Calcul de palettisation en cours, temps écoulé {formatElapsedSeconds(elapsedSeconds)}.
        Veuillez patienter, cette page se mettra à jour automatiquement.
      </span>
    </div>
  );
}

function formatElapsedSeconds(totalSeconds: number): string {
  const safeSeconds = Number.isFinite(totalSeconds) && totalSeconds > 0 ? Math.floor(totalSeconds) : 0;
  const minutes = Math.floor(safeSeconds / 60);
  const seconds = safeSeconds % 60;
  if (minutes === 0) return `${seconds}s`;
  return `${minutes} min ${String(seconds).padStart(2, "0")}s`;
}
