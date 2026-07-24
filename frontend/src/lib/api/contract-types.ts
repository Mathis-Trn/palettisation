/**
 * Types "sur le fil" (JSON échangé avec le backend Python), reflet exact de
 * `backend/src/palletizer/contracts.py`. Ne pas modifier sans répercuter le changement côté
 * backend (voir `contracts/openapi.json`, source de vérité générée automatiquement).
 *
 * Ces types ne sont jamais utilisés directement par les composants de rendu : `to-domain.ts`
 * centralise la conversion vers les types du domaine (`@/domain/types`).
 */

export type ShippingModeContract = "sea" | "air" | "road" | "unknown";
export type OptimizationLevelContract = "fast" | "thorough";
export type OrientationCodeContract = "LWH" | "WLH" | "LHW" | "HWL" | "WHL" | "HLW";
export type RejectionCodeContract =
  | "DIMENSIONS_EXCEED_PALLET"
  | "HEIGHT_EXCEEDED"
  | "WEIGHT_EXCEEDED"
  | "ROTATION_FORBIDDEN"
  | "STACKING_CONSTRAINT"
  | "NO_STABLE_POSITION"
  | "INVALID_DATA"
  | "INCOMPATIBLE_GROUP";

export type DimensionsMmContract = { length: number; width: number; height: number };

export type OrderLineContract = {
  lineNumber: number;
  sku: string;
  description?: string;
  quantity: number;
  unit?: string;
  dimensionsMm: DimensionsMmContract;
  weightKg?: number | null;
  allowRotation?: boolean;
  uprightOnly?: boolean;
  fragile?: boolean;
  stackable?: boolean;
  maxSupportedWeightKg?: number | null;
  productGroup?: string | null;
  incompatibleGroups?: string[];
};

export type OrderContract = {
  orderId: string;
  shippingMode: ShippingModeContract;
  lines: OrderLineContract[];
};

export type PalletContract = {
  code?: string;
  lengthMm: number;
  widthMm: number;
  maxHeightMm: number;
  emptyPalletHeightMm?: number;
  maxHeightIncludesPallet?: boolean;
  maxWeightKg?: number | null;
  overhangMm?: number;
  safetyGapMm?: number;
};

export type OptionsContract = {
  optimizationLevel?: OptimizationLevelContract;
  minimumSupportRatio?: number;
  globalRotationsEnabled?: boolean;
  fragileMaxWeightOnTopKg?: number;
};

export type PalletizeRequestContract = {
  contractVersion: "1.0";
  order: OrderContract;
  pallet: PalletContract;
  options?: OptionsContract;
};

export type Position3DContract = { x: number; y: number; z: number };
export type DimensionsContract = { length: number; width: number; height: number };

export type PalletConfigContract = {
  code: string;
  lengthMm: number;
  widthMm: number;
  maxHeightMm: number;
  emptyPalletHeightMm: number;
  maxHeightIncludesPallet: boolean;
  maxWeightKg?: number | null;
  overhangMm: number;
  safetyGapMm: number;
  minimumSupportRatio: number;
};

export type PlacedCartonContract = {
  instanceId: string;
  sku: string;
  originalDimensionsMm: DimensionsContract;
  placedDimensionsMm: DimensionsContract;
  positionMm: Position3DContract;
  orientation: OrientationCodeContract;
  palletIndex: number;
  placementScore: number;
  weightKg?: number | null;
  fragile: boolean;
  stackable: boolean;
  productGroup?: string | null;
};

export type UnplacedCartonContract = {
  instanceId: string;
  sku: string;
  dimensionsMm: DimensionsContract;
  code: RejectionCodeContract;
  message: string;
  weightKg?: number | null;
};

export type PalletResultContract = {
  index: number;
  config: PalletConfigContract;
  totalWeightKg: number;
  usableVolumeMm3: number;
  volumeUsedMm3: number;
  volumeUsageRatio: number;
  footprintUsageRatio: number;
  maxHeightUsedMm: number;
  placedCartons: PlacedCartonContract[];
};

export type PalletizeResponseContract = {
  contractVersion: "1.0";
  orderId: string;
  engineVersion: string;
  durationMs: number;
  warnings: string[];
  totalCartonsCount: number;
  placedCartonsCount: number;
  unplacedCartonsCount: number;
  palletsCount: number;
  globalVolumeUsageRatio: number;
  totalWeightKg: number;
  pallets: PalletResultContract[];
  unplacedCartons: UnplacedCartonContract[];
  legacyExpectedResult: { palletCount: number | null } | null;
};

// --- /orders/parse-csv --------------------------------------------------------------------

export type CsvImportErrorContract = {
  lineNumber: number | null;
  column: string | null;
  code: string;
  message: string;
  rawFragments: string[];
};

export type CsvImportWarningContract = { lineNumber: number | null; message: string };

export type ParsedCsvOrderContract = {
  orderId: string;
  shippingMode: ShippingModeContract;
  pallet: PalletContract;
  lines: OrderLineContract[];
  legacyPalletCount: number | null;
};

export type ParseCsvResponseContract = {
  contractVersion: "1.0";
  orders: ParsedCsvOrderContract[];
  errors: CsvImportErrorContract[];
  warnings: CsvImportWarningContract[];
  totalRows: number;
  acceptedRows: number;
  rejectedRows: number;
  stats: { ordersCount: number; palletFormats: string[]; shippingModes: string[] };
};

// --- /transport/load ------------------------------------------------------------------------

export type VehicleContract = {
  name?: string;
  innerLengthMm: number;
  innerWidthMm: number;
  innerHeightMm: number;
  maxPayloadKg: number;
  allowPalletRotationFloor?: boolean;
  allowPalletStacking?: boolean;
};

export type PalletToLoadContract = {
  palletResultIndex: number;
  footprintLengthMm: number;
  footprintWidthMm: number;
  heightMm: number;
  weightKg: number;
};

export type TransportLoadRequestContract = {
  contractVersion: "1.0";
  pallets: PalletToLoadContract[];
  vehicle: VehicleContract;
};

export type LoadedPalletPlacementContract = {
  palletResultIndex: number;
  vehicleIndex: number;
  x: number;
  y: number;
  rotated: boolean;
  stackLevel: number;
  lengthMm: number;
  widthMm: number;
  heightMm: number;
  weightKg: number;
};

export type VehicleLoadResultContract = {
  index: number;
  placements: LoadedPalletPlacementContract[];
  usedFloorAreaRatio: number;
  usedWeightKg: number;
};

export type TransportLoadResponseContract = {
  contractVersion: "1.0";
  vehicles: VehicleLoadResultContract[];
  unassignedPalletIndexes: number[];
  vehiclesNeeded: number;
  palletsLoadable: number;
};

// --- /health, /capabilities ------------------------------------------------------------------

export type HealthResponseContract = { status: string; version: string; engineVersion: string };

export type CapabilitiesResponseContract = {
  contractVersion: string;
  units: { dimensions: string; weight: string };
  supportedPalletFormats: string[];
  constraints: string[];
  limits: Record<string, number>;
  packingAdapter: { name: string; version: string };
};

export type ErrorResponseContract = {
  error: { code: string; message: string; correlation_id: string };
};
