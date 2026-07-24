import type { PalletConfig, SimulationSettings } from "@/domain/types";
import { REJECTION_MESSAGES } from "@/domain/types";
import { getAllowedOrientations } from "./orientations";
import { boxesOverlap, isWithinBounds } from "./geometry";
import { checkSupport } from "./support";
import { scorePlacement } from "./scoring";
import type { CartonInstance, ExtremePoint, PlacementFailure, WorkingPallet } from "./types";

/** Nombre maximal de points extrêmes conservés par palette, pour borner le temps de calcul. */
const MAX_EXTREME_POINTS = 400;

export function createEmptyPallet(): WorkingPallet {
  return { boxes: [], extremePoints: [{ x: 0, y: 0, z: 0 }], totalWeightKg: 0 };
}

export function usableBounds(palletConfig: PalletConfig): { maxX: number; maxY: number; maxZ: number } {
  const usableHeight = palletConfig.maxHeightIncludesPallet
    ? palletConfig.dimensions.height - palletConfig.emptyPalletHeightMm
    : palletConfig.dimensions.height;
  return {
    maxX: palletConfig.dimensions.length + palletConfig.overhangMm,
    maxY: palletConfig.dimensions.width + palletConfig.overhangMm,
    maxZ: Math.max(0, usableHeight),
  };
}

/**
 * Détermine si un carton peut, dans l'absolu, tenir sur une palette vide (bornes + poids),
 * sans tenir compte des autres cartons. Utilisé pour rejeter immédiatement un carton impossible
 * plutôt que d'ouvrir indéfiniment de nouvelles palettes (garantie de terminaison).
 */
export function canInstanceEverFit(
  instance: CartonInstance,
  palletConfig: PalletConfig,
  globalRotationsEnabled: boolean
): { fits: boolean; failure?: PlacementFailure } {
  if (
    palletConfig.maxWeightKg !== undefined &&
    instance.weightKg !== undefined &&
    instance.weightKg > palletConfig.maxWeightKg
  ) {
    return { fits: false, failure: { code: "WEIGHT_EXCEEDED", message: REJECTION_MESSAGES.WEIGHT_EXCEEDED } };
  }

  const { maxX, maxY, maxZ } = usableBounds(palletConfig);
  const restricted = getAllowedOrientations(instance.dimensions, instance.allowRotation, instance.uprightOnly, globalRotationsEnabled);
  const fitsRestricted = restricted.some((o) => o.dims.length <= maxX && o.dims.width <= maxY && o.dims.height <= maxZ);
  if (fitsRestricted) return { fits: true };

  const unrestricted = getAllowedOrientations(instance.dimensions, true, false, true);
  const fitsUnrestricted = unrestricted.some((o) => o.dims.length <= maxX && o.dims.width <= maxY && o.dims.height <= maxZ);
  if (fitsUnrestricted) {
    return { fits: false, failure: { code: "ROTATION_FORBIDDEN", message: REJECTION_MESSAGES.ROTATION_FORBIDDEN } };
  }

  const footprintFitsSomeOrientation = unrestricted.some((o) => o.dims.length <= maxX && o.dims.width <= maxY);
  if (footprintFitsSomeOrientation) {
    return { fits: false, failure: { code: "HEIGHT_EXCEEDED", message: REJECTION_MESSAGES.HEIGHT_EXCEEDED } };
  }

  return { fits: false, failure: { code: "DIMENSIONS_EXCEED_PALLET", message: REJECTION_MESSAGES.DIMENSIONS_EXCEED_PALLET } };
}

function dedupePoint(points: ExtremePoint[], candidate: ExtremePoint): ExtremePoint[] {
  const exists = points.some(
    (p) => Math.abs(p.x - candidate.x) < 1e-6 && Math.abs(p.y - candidate.y) < 1e-6 && Math.abs(p.z - candidate.z) < 1e-6
  );
  return exists ? points : [...points, candidate];
}

/** Tente de placer une instance sur une palette de travail. Retourne l'échec le plus pertinent sinon. */
export function tryPlaceOnPallet(
  instance: CartonInstance,
  pallet: WorkingPallet,
  palletConfig: PalletConfig,
  settings: SimulationSettings
): { success: true } | { success: false; failure: PlacementFailure } {
  const { maxX, maxY, maxZ } = usableBounds(palletConfig);

  if (
    palletConfig.maxWeightKg !== undefined &&
    instance.weightKg !== undefined &&
    pallet.totalWeightKg + instance.weightKg > palletConfig.maxWeightKg + 1e-6
  ) {
    return { success: false, failure: { code: "WEIGHT_EXCEEDED", message: REJECTION_MESSAGES.WEIGHT_EXCEEDED } };
  }

  const orientations = getAllowedOrientations(
    instance.dimensions,
    instance.allowRotation,
    instance.uprightOnly,
    settings.globalRotationsEnabled
  );

  let best: { point: ExtremePoint; orientationCode: (typeof orientations)[number]["code"]; dims: (typeof orientations)[number]["dims"]; score: number } | null =
    null;
  let lastFailureCode: PlacementFailure["code"] = "NO_STABLE_POSITION";
  let lastFailureMessage: string = REJECTION_MESSAGES.NO_STABLE_POSITION;
  let anyBoundsFit = false;

  for (const point of pallet.extremePoints) {
    for (const orientation of orientations) {
      const candidateBox = { position: point, dims: orientation.dims };
      if (!isWithinBounds(candidateBox, maxX, maxY, maxZ)) continue;
      anyBoundsFit = true;

      const overlaps = pallet.boxes.some((box) =>
        boxesOverlap(candidateBox, { position: box.position, dims: box.placedDimensions }, palletConfig.safetyGapMm)
      );
      if (overlaps) continue;

      const support = checkSupport(
        point,
        orientation.dims,
        instance.weightKg,
        pallet.boxes,
        palletConfig.minimumSupportRatio,
        settings.fragileMaxWeightOnTopKg
      );
      if (!support.ok) {
        lastFailureCode = support.reason ?? "NO_STABLE_POSITION";
        lastFailureMessage = support.detail ?? REJECTION_MESSAGES[lastFailureCode];
        continue;
      }

      const score = scorePlacement({
        position: point,
        dims: orientation.dims,
        supportRatio: support.supportRatio,
        sku: instance.sku,
        existingBoxes: pallet.boxes,
      });

      if (
        !best ||
        score > best.score + 1e-9 ||
        (Math.abs(score - best.score) <= 1e-9 && comparePointThenCode(point, orientation.code, best.point, best.orientationCode) < 0)
      ) {
        best = { point, orientationCode: orientation.code, dims: orientation.dims, score };
      }
    }
  }

  if (!best) {
    if (!anyBoundsFit) {
      return { success: false, failure: { code: "DIMENSIONS_EXCEED_PALLET", message: REJECTION_MESSAGES.DIMENSIONS_EXCEED_PALLET } };
    }
    return { success: false, failure: { code: lastFailureCode, message: lastFailureMessage } };
  }

  pallet.boxes.push({
    instance,
    position: best.point,
    orientation: best.orientationCode,
    placedDimensions: best.dims,
    score: best.score,
  });
  pallet.totalWeightKg += instance.weightKg ?? 0;

  pallet.extremePoints = pallet.extremePoints.filter(
    (p) => !(Math.abs(p.x - best!.point.x) < 1e-6 && Math.abs(p.y - best!.point.y) < 1e-6 && Math.abs(p.z - best!.point.z) < 1e-6)
  );

  const newPoints: ExtremePoint[] = [
    { x: best.point.x + best.dims.length, y: best.point.y, z: best.point.z },
    { x: best.point.x, y: best.point.y + best.dims.width, z: best.point.z },
    { x: best.point.x, y: best.point.y, z: best.point.z + best.dims.height },
  ];
  for (const p of newPoints) {
    if (p.x <= maxX + 1e-6 && p.y <= maxY + 1e-6 && p.z <= maxZ + 1e-6) {
      pallet.extremePoints = dedupePoint(pallet.extremePoints, p);
    }
  }

  if (pallet.extremePoints.length > MAX_EXTREME_POINTS) {
    pallet.extremePoints = [...pallet.extremePoints]
      .sort((a, b) => a.z - b.z || a.x + a.y - (b.x + b.y))
      .slice(0, MAX_EXTREME_POINTS);
  }

  return { success: true };
}

function comparePointThenCode(
  pointA: ExtremePoint,
  codeA: string,
  pointB: ExtremePoint,
  codeB: string
): number {
  return (
    pointA.z - pointB.z ||
    pointA.y - pointB.y ||
    pointA.x - pointB.x ||
    (codeA < codeB ? -1 : codeA > codeB ? 1 : 0)
  );
}
