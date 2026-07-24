import { EPSILON_MM, footprintIntersectionArea } from "./geometry";
import type { WorkingPlacedBox } from "./types";
import type { Dimensions3D, Position3D } from "@/domain/types";

export type SupportCheckResult = {
  ok: boolean;
  supportRatio: number;
  reason?: "STACKING_CONSTRAINT" | "NO_STABLE_POSITION";
  detail?: string;
};

/**
 * Contrôle de support et de stabilité pour une position candidate.
 *
 * Approximation logicielle (voir README) : le support est estimé en 2D sur l'empreinte au sol
 * du carton, sans simulation physique. Elle ne remplace pas une validation de chargement réelle.
 */
export function checkSupport(
  candidatePosition: Position3D,
  candidateDims: Dimensions3D,
  candidateWeightKg: number | undefined,
  existingBoxes: WorkingPlacedBox[],
  minimumSupportRatio: number,
  fragileMaxWeightOnTopKg: number
): SupportCheckResult {
  // Posé directement sur le plateau de la palette : support total garanti par la palette elle-même.
  if (candidatePosition.z <= EPSILON_MM) {
    return { ok: true, supportRatio: 1 };
  }

  const candidateBox = { position: candidatePosition, dims: candidateDims };
  const footprintArea = candidateDims.length * candidateDims.width;

  const supportingBoxes = existingBoxes.filter((box) => {
    const topZ = box.position.z + box.placedDimensions.height;
    return Math.abs(topZ - candidatePosition.z) <= EPSILON_MM;
  });

  let contactArea = 0;
  for (const support of supportingBoxes) {
    const intersection = footprintIntersectionArea(candidateBox, {
      position: support.position,
      dims: support.placedDimensions,
    });
    if (intersection <= EPSILON_MM) continue;

    if (!support.instance.stackable) {
      return {
        ok: false,
        supportRatio: 0,
        reason: "STACKING_CONSTRAINT",
        detail: `Le carton ${support.instance.sku} n'est pas gerbable : rien ne peut être posé au-dessus.`,
      };
    }

    if (support.instance.fragile) {
      const weight = candidateWeightKg ?? 0;
      if (weight > fragileMaxWeightOnTopKg + EPSILON_MM) {
        return {
          ok: false,
          supportRatio: 0,
          reason: "STACKING_CONSTRAINT",
          detail: `Le carton ${support.instance.sku} est fragile : poids au-dessus limité à ${fragileMaxWeightOnTopKg} kg.`,
        };
      }
    }

    if (
      support.instance.maxSupportedWeightKg !== undefined &&
      candidateWeightKg !== undefined &&
      candidateWeightKg > support.instance.maxSupportedWeightKg + EPSILON_MM
    ) {
      return {
        ok: false,
        supportRatio: 0,
        reason: "STACKING_CONSTRAINT",
        detail: `Le carton ${support.instance.sku} ne supporte pas plus de ${support.instance.maxSupportedWeightKg} kg au-dessus.`,
      };
    }

    contactArea += intersection;
  }

  const supportRatio = footprintArea > 0 ? contactArea / footprintArea : 0;
  if (supportRatio + EPSILON_MM < minimumSupportRatio) {
    return { ok: false, supportRatio, reason: "NO_STABLE_POSITION" };
  }

  // Centre de gravité projeté : le centre de l'empreinte doit reposer sur une zone supportée
  // (approximation : il doit être contenu dans l'empreinte d'au moins un carton support).
  const centerX = candidatePosition.x + candidateDims.length / 2;
  const centerY = candidatePosition.y + candidateDims.width / 2;
  const centerSupported = supportingBoxes.some((support) => {
    const minX = support.position.x;
    const maxX = support.position.x + support.placedDimensions.length;
    const minY = support.position.y;
    const maxY = support.position.y + support.placedDimensions.width;
    return centerX >= minX - EPSILON_MM && centerX <= maxX + EPSILON_MM && centerY >= minY - EPSILON_MM && centerY <= maxY + EPSILON_MM;
  });

  if (!centerSupported) {
    return { ok: false, supportRatio, reason: "NO_STABLE_POSITION", detail: "Centre de gravité hors de la zone de support." };
  }

  return { ok: true, supportRatio };
}
