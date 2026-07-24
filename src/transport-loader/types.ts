/**
 * Module de chargement transport : estime combien de palettes (déjà chargées, issues du moteur
 * de palettisation) peuvent entrer dans un véhicule ou un conteneur. Module distinct et plus
 * simple que le moteur de palettisation : placement 2D des empreintes au sol uniquement.
 */

export type VehicleConfig = {
  name: string;
  innerLengthMm: number;
  innerWidthMm: number;
  innerHeightMm: number;
  maxPayloadKg: number;
  allowPalletRotationFloor: boolean;
  /** Empilage de palettes chargées les unes sur les autres. Désactivé par défaut. */
  allowPalletStacking: boolean;
};

/** Une palette déjà chargée (résultat de la palettisation) à faire entrer dans un véhicule. */
export type PalletToLoad = {
  palletResultIndex: number;
  footprintLengthMm: number;
  footprintWidthMm: number;
  heightMm: number;
  weightKg: number;
};

export type LoadedPalletPlacement = {
  palletResultIndex: number;
  vehicleIndex: number;
  x: number;
  y: number;
  rotated: boolean;
  stackLevel: 0 | 1;
  lengthMm: number;
  widthMm: number;
  heightMm: number;
  weightKg: number;
};

export type VehicleLoadResult = {
  index: number;
  placements: LoadedPalletPlacement[];
  usedFloorAreaRatio: number;
  usedWeightKg: number;
};

export type TransportLoadResult = {
  vehicles: VehicleLoadResult[];
  unassignedPalletIndexes: number[];
  vehiclesNeeded: number;
  palletsLoadable: number;
};
