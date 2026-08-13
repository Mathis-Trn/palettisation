/**
 * Point de conversion UNIQUE entre le contrat JSON du backend Python et le modèle de rendu
 * (`@/domain/types`), consommé par la visualisation 3D, les tableaux de résultats et l'export.
 * Aucun autre module ne doit lire directement les types de `contract-types.ts` (voir section 16
 * du cahier des charges : « centralise la conversion du résultat API vers le modèle de rendu »).
 */

import type {
  CartonLine,
  OptimizationResult,
  PalletConfig,
  PalletResult,
  PlacedCarton,
  RejectionCode,
  Simulation,
  TransportLoadResult,
  TransportMode,
  UnplacedCarton,
  VehicleConfig,
} from "@/domain/types";
import type {
  DimensionsMmContract,
  OptionsContract,
  OrderLineContract,
  PalletConfigContract,
  PalletContract,
  PalletizeResponseContract,
  PalletToLoadContract,
  ParsedCsvOrderContract,
  ShippingModeContract,
  TransportLoadResponseContract,
  VehicleContract,
} from "./contract-types";

// --- Sortant : domaine -> contrat (requêtes) ------------------------------------------------

const TRANSPORT_MODE_TO_SHIPPING_MODE: Record<TransportMode, ShippingModeContract> = {
  routier: "road",
  maritime: "sea",
  aerien: "air",
};

export function cartonLineToOrderLineContract(
  line: CartonLine,
  lineNumber: number
): OrderLineContract {
  return {
    lineNumber,
    sku: line.sku,
    description: line.sku,
    quantity: line.quantity,
    unit: "PIECE",
    dimensionsMm: { ...line.dimensions },
    weightKg: line.weightKg,
    allowRotation: line.allowRotation,
    uprightOnly: line.uprightOnly,
    fragile: line.fragile,
    stackable: line.stackable,
    maxSupportedWeightKg: line.maxSupportedWeightKg,
    productGroup: line.productGroup,
    incompatibleGroups: line.incompatibleGroups ?? [],
  };
}

export function palletConfigToContract(config: PalletConfig): PalletContract {
  return {
    code: config.name,
    lengthMm: config.dimensions.length,
    widthMm: config.dimensions.width,
    maxHeightMm: config.dimensions.height,
    emptyPalletHeightMm: config.emptyPalletHeightMm,
    maxHeightIncludesPallet: config.maxHeightIncludesPallet,
    maxWeightKg: config.maxWeightKg,
    overhangMm: config.overhangMm,
    safetyGapMm: config.safetyGapMm,
  };
}

export function settingsToOptionsContract(simulation: Simulation): OptionsContract {
  return {
    optimizationLevel: simulation.settings.optimizationLevel === "approfondi" ? "thorough" : "fast",
    minimumSupportRatio: simulation.settings.palletConfig.minimumSupportRatio,
    globalRotationsEnabled: simulation.settings.globalRotationsEnabled,
    fragileMaxWeightOnTopKg: simulation.settings.fragileMaxWeightOnTopKg,
  };
}

export function transportModeToShippingMode(mode: TransportMode): ShippingModeContract {
  return TRANSPORT_MODE_TO_SHIPPING_MODE[mode];
}

export function vehicleToContract(vehicle: VehicleConfig): VehicleContract {
  return {
    name: vehicle.name,
    innerLengthMm: vehicle.innerLengthMm,
    innerWidthMm: vehicle.innerWidthMm,
    innerHeightMm: vehicle.innerHeightMm,
    maxPayloadKg: vehicle.maxPayloadKg,
    allowPalletRotationFloor: vehicle.allowPalletRotationFloor,
    allowPalletStacking: vehicle.allowPalletStacking,
  };
}

export function palletResultToLoadContract(pallet: PalletResult): PalletToLoadContract {
  return {
    palletResultIndex: pallet.index,
    footprintLengthMm: pallet.config.dimensions.length,
    footprintWidthMm: pallet.config.dimensions.width,
    heightMm: pallet.config.emptyPalletHeightMm + pallet.maxHeightUsedMm,
    weightKg: pallet.totalWeightKg,
  };
}

// --- Entrant : contrat -> domaine (réponses) ------------------------------------------------

function dimsFromContract(dims: DimensionsMmContract) {
  return { length: dims.length, width: dims.width, height: dims.height };
}

function configFromContract(config: PalletConfigContract): PalletConfig {
  return {
    name: config.code,
    dimensions: { length: config.lengthMm, width: config.widthMm, height: config.maxHeightMm },
    emptyPalletHeightMm: config.emptyPalletHeightMm,
    maxWeightKg: config.maxWeightKg ?? undefined,
    maxHeightIncludesPallet: config.maxHeightIncludesPallet,
    overhangMm: config.overhangMm,
    safetyGapMm: config.safetyGapMm,
    minimumSupportRatio: config.minimumSupportRatio,
  };
}

function placedCartonFromContract(box: PalletizeResponseContract["pallets"][number]["placedCartons"][number]): PlacedCarton {
  return {
    instanceId: box.instanceId,
    sku: box.sku,
    originalDimensions: dimsFromContract(box.originalDimensionsMm),
    placedDimensions: dimsFromContract(box.placedDimensionsMm),
    position: { x: box.positionMm.x, y: box.positionMm.y, z: box.positionMm.z },
    orientation: box.orientation,
    weightKg: box.weightKg ?? undefined,
    palletIndex: box.palletIndex,
    placementScore: box.placementScore,
    fragile: box.fragile,
    stackable: box.stackable,
    productGroup: box.productGroup ?? undefined,
  };
}

function unplacedCartonFromContract(
  item: PalletizeResponseContract["unplacedCartons"][number]
): UnplacedCarton {
  return {
    instanceId: item.instanceId,
    sku: item.sku,
    dimensions: dimsFromContract(item.dimensionsMm),
    weightKg: item.weightKg ?? undefined,
    code: item.code as RejectionCode,
    message: item.message,
  };
}

function palletResultFromContract(pallet: PalletizeResponseContract["pallets"][number]): PalletResult {
  return {
    index: pallet.index,
    config: configFromContract(pallet.config),
    placedCartons: pallet.placedCartons.map(placedCartonFromContract),
    totalWeightKg: pallet.totalWeightKg,
    usableVolumeMm3: pallet.usableVolumeMm3,
    volumeUsedMm3: pallet.volumeUsedMm3,
    volumeUsageRatio: pallet.volumeUsageRatio,
    footprintUsageRatio: pallet.footprintUsageRatio,
    maxHeightUsedMm: pallet.maxHeightUsedMm,
  };
}

export function contractToOptimizationResult(response: PalletizeResponseContract): OptimizationResult {
  return {
    pallets: response.pallets.map(palletResultFromContract),
    unplacedCartons: response.unplacedCartons.map(unplacedCartonFromContract),
    totalCartonsCount: response.totalCartonsCount,
    placedCartonsCount: response.placedCartonsCount,
    unplacedCartonsCount: response.unplacedCartonsCount,
    palletsCount: response.palletsCount,
    globalVolumeUsageRatio: response.globalVolumeUsageRatio,
    totalWeightKg: response.totalWeightKg,
    warnings: response.warnings,
    computedAtIso: new Date().toISOString(),
    engineVersion: response.engineVersion,
    levelUsed: response.warnings.some((w) => w.includes("approfondi")) ? "approfondi" : "rapide",
    durationMs: response.durationMs,
  };
}

export function contractToTransportLoadResult(
  response: TransportLoadResponseContract
): TransportLoadResult {
  return {
    vehicles: response.vehicles.map((v) => ({
      index: v.index,
      placements: v.placements.map((p) => ({
        palletResultIndex: p.palletResultIndex,
        vehicleIndex: p.vehicleIndex,
        x: p.x,
        y: p.y,
        rotated: p.rotated,
        stackLevel: p.stackLevel === 1 ? 1 : 0,
        lengthMm: p.lengthMm,
        widthMm: p.widthMm,
        heightMm: p.heightMm,
        weightKg: p.weightKg,
      })),
      usedFloorAreaRatio: v.usedFloorAreaRatio,
      usedWeightKg: v.usedWeightKg,
    })),
    unassignedPalletIndexes: response.unassignedPalletIndexes,
    vehiclesNeeded: response.vehiclesNeeded,
    palletsLoadable: response.palletsLoadable,
  };
}

/** Ligne normalisée détectée dans le CSV, prête à être éditée comme une ligne de commande. */
export function orderLineContractToCartonLine(line: OrderLineContract): CartonLine {
  return {
    sku: line.sku,
    dimensions: dimsFromContract(line.dimensionsMm),
    quantity: line.quantity,
    weightKg: line.weightKg ?? undefined,
    allowRotation: line.allowRotation ?? true,
    uprightOnly: line.uprightOnly ?? false,
    fragile: line.fragile ?? false,
    stackable: line.stackable ?? true,
    maxSupportedWeightKg: line.maxSupportedWeightKg ?? undefined,
    productGroup: line.productGroup ?? undefined,
    incompatibleGroups: line.incompatibleGroups,
  };
}

export type DetectedCsvOrder = {
  orderId: string;
  shippingMode: ShippingModeContract;
  palletCode: string;
  lineCount: number;
  legacyPalletCount: number | null;
  lines: CartonLine[];
};

export function parsedCsvOrderToDetectedOrder(order: ParsedCsvOrderContract): DetectedCsvOrder {
  return {
    orderId: order.orderId,
    shippingMode: order.shippingMode,
    palletCode: order.pallet.code ?? "",
    lineCount: order.lines.length,
    legacyPalletCount: order.legacyPalletCount,
    lines: order.lines.map(orderLineContractToCartonLine),
  };
}
