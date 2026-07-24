import type { Dimensions3D, Position3D } from "@/domain/types";

/** Tolérance numérique (mm) pour absorber les erreurs d'arrondi flottant lors des comparaisons. */
export const EPSILON_MM = 1e-6;

export function volumeOf(dims: Dimensions3D): number {
  return dims.length * dims.width * dims.height;
}

export type Box3 = {
  position: Position3D;
  dims: Dimensions3D;
};

/**
 * Teste le chevauchement de deux pavés droits (AABB), avec un espace de sécurité optionnel
 * appliqué sur les axes X et Y (le plan du sol). L'espace vertical (Z) n'est pas gonflé :
 * les cartons empilés doivent pouvoir se toucher exactement.
 */
export function boxesOverlap(a: Box3, b: Box3, safetyGapMm = 0): boolean {
  const gap = Math.max(0, safetyGapMm);
  const aMinX = a.position.x - gap / 2;
  const aMaxX = a.position.x + a.dims.length + gap / 2;
  const bMinX = b.position.x - gap / 2;
  const bMaxX = b.position.x + b.dims.length + gap / 2;
  if (aMaxX <= bMinX + EPSILON_MM || bMaxX <= aMinX + EPSILON_MM) return false;

  const aMinY = a.position.y - gap / 2;
  const aMaxY = a.position.y + a.dims.width + gap / 2;
  const bMinY = b.position.y - gap / 2;
  const bMaxY = b.position.y + b.dims.width + gap / 2;
  if (aMaxY <= bMinY + EPSILON_MM || bMaxY <= aMinY + EPSILON_MM) return false;

  const aMinZ = a.position.z;
  const aMaxZ = a.position.z + a.dims.height;
  const bMinZ = b.position.z;
  const bMaxZ = b.position.z + b.dims.height;
  if (aMaxZ <= bMinZ + EPSILON_MM || bMaxZ <= aMinZ + EPSILON_MM) return false;

  return true;
}

/** Aire de l'intersection des empreintes au sol (X,Y) de deux pavés, indépendamment de Z. */
export function footprintIntersectionArea(a: Box3, b: Box3): number {
  const xOverlap = Math.min(a.position.x + a.dims.length, b.position.x + b.dims.length) - Math.max(a.position.x, b.position.x);
  const yOverlap = Math.min(a.position.y + a.dims.width, b.position.y + b.dims.width) - Math.max(a.position.y, b.position.y);
  if (xOverlap <= EPSILON_MM || yOverlap <= EPSILON_MM) return 0;
  return xOverlap * yOverlap;
}

export function isWithinBounds(box: Box3, maxX: number, maxY: number, maxZ: number, minX = 0, minY = 0): boolean {
  return (
    box.position.x >= minX - EPSILON_MM &&
    box.position.y >= minY - EPSILON_MM &&
    box.position.z >= 0 - EPSILON_MM &&
    box.position.x + box.dims.length <= maxX + EPSILON_MM &&
    box.position.y + box.dims.width <= maxY + EPSILON_MM &&
    box.position.z + box.dims.height <= maxZ + EPSILON_MM
  );
}
