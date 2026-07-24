import type { Dimensions3D, OrientationCode, Position3D, RejectionCode } from "@/domain/types";

/** Une instance individuelle de carton, issue de l'expansion d'une CartonLine par sa quantité. */
export type CartonInstance = {
  instanceId: string;
  sku: string;
  lineIndex: number;
  dimensions: Dimensions3D;
  weightKg?: number;
  allowRotation: boolean;
  uprightOnly: boolean;
  fragile: boolean;
  stackable: boolean;
  maxSupportedWeightKg?: number;
  productGroup?: string;
  incompatibleGroups: string[];
};

/** Une instance invalide dès l'expansion (dimensions ou quantité incorrectes). */
export type InvalidInstance = {
  sku: string;
  dimensions: Dimensions3D;
  weightKg?: number;
  reason: string;
};

export type OrientedBox = {
  code: OrientationCode;
  dims: Dimensions3D;
};

/** Une boîte déjà posée sur la palette de travail, pendant le calcul. */
export type WorkingPlacedBox = {
  instance: CartonInstance;
  position: Position3D;
  orientation: OrientationCode;
  placedDimensions: Dimensions3D;
  score: number;
};

export type ExtremePoint = Position3D;

export type WorkingPallet = {
  boxes: WorkingPlacedBox[];
  extremePoints: ExtremePoint[];
  totalWeightKg: number;
};

export type PlacementFailure = {
  code: RejectionCode;
  message: string;
};

export type SortStrategyName = "volume-desc" | "largest-dimension-desc" | "weight-desc" | "footprint-desc";

export type PackingStrategyResult = {
  strategyName: SortStrategyName;
  pallets: WorkingPallet[];
  unplaced: { instance: CartonInstance; failure: PlacementFailure }[];
};
