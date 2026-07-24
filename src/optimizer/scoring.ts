import type { Dimensions3D, Position3D } from "@/domain/types";
import type { WorkingPlacedBox } from "./types";
import { footprintIntersectionArea } from "./geometry";

export type ScoreInputs = {
  position: Position3D;
  dims: Dimensions3D;
  supportRatio: number;
  sku: string;
  existingBoxes: WorkingPlacedBox[];
};

/**
 * Combine plusieurs critères en un score unique (plus haut = meilleur) pour départager les
 * positions/orientations candidates valides. Pondérations empiriques, documentées dans README.md.
 */
export function scorePlacement({ position, dims, supportRatio, sku, existingBoxes }: ScoreInputs): number {
  const resultingHeight = position.z + dims.height;
  const originDistance = position.x + position.y;

  let skuAdjacencyBonus = 0;
  let wallContactBonus = 0;
  if (position.x <= 1e-6) wallContactBonus += 1;
  if (position.y <= 1e-6) wallContactBonus += 1;
  if (position.z <= 1e-6) wallContactBonus += 1;

  const dilatedCandidate = {
    position: { x: position.x - 1, y: position.y - 1, z: position.z },
    dims: { length: dims.length + 2, width: dims.width + 2, height: dims.height },
  };
  for (const box of existingBoxes) {
    if (box.instance.sku !== sku) continue;
    const sameLevel = Math.abs(box.position.z - position.z) <= 1e-6;
    if (!sameLevel) continue;
    const nearby = footprintIntersectionArea(dilatedCandidate, { position: box.position, dims: box.placedDimensions });
    if (nearby > 0) skuAdjacencyBonus += 1;
  }

  const WEIGHT_HEIGHT = -1.0;
  const WEIGHT_ORIGIN = -0.05;
  const WEIGHT_SUPPORT = 50;
  const WEIGHT_WALL_CONTACT = 20;
  const WEIGHT_SKU_ADJACENCY = 5;

  return (
    resultingHeight * WEIGHT_HEIGHT +
    originDistance * WEIGHT_ORIGIN +
    supportRatio * WEIGHT_SUPPORT +
    wallContactBonus * WEIGHT_WALL_CONTACT +
    skuAdjacencyBonus * WEIGHT_SKU_ADJACENCY
  );
}
