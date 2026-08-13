import type { Dimensions3D, Position3D } from "@/domain/types";

/**
 * Conversion centralisée entre le repère métier (millimètres, origine au coin inférieur de la
 * palette, x=longueur, y=largeur, z=hauteur) et le repère de scène Three.js (mètres, Y vertical).
 * Aucun autre module ne doit convertir des coordonnées : les coordonnées graphiques ne sont
 * jamais la source de vérité métier, uniquement une projection pour l'affichage.
 */
const MM_TO_SCENE = 1 / 1000;

export function mmToScene(mm: number): number {
  return mm * MM_TO_SCENE;
}

/** Centre (en unités de scène) d'un pavé métier, pour un mesh Three.js centré par défaut. */
export function domainCenterToScene(position: Position3D, dims: Dimensions3D): [number, number, number] {
  const centerX = position.x + dims.length / 2;
  const centerZUp = position.z + dims.height / 2;
  const centerY = position.y + dims.width / 2;
  return [mmToScene(centerX), mmToScene(centerZUp), mmToScene(centerY)];
}

/** Dimensions (en unités de scène) d'un pavé métier : [longueur->x, hauteur->y(up), largeur->z]. */
export function domainSizeToScene(dims: Dimensions3D): [number, number, number] {
  return [mmToScene(dims.length), mmToScene(dims.height), mmToScene(dims.width)];
}
