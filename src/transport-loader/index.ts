import type { PalletResult } from "@/domain/types";
import { loadPalletsIntoVehicles } from "./floor-packer";
import type { PalletToLoad, VehicleConfig } from "./types";

export type { PalletToLoad, VehicleConfig, TransportLoadResult, LoadedPalletPlacement, VehicleLoadResult } from "./types";
export { loadPalletsIntoVehicles } from "./floor-packer";

/** Convertit les palettes issues du moteur de palettisation en éléments chargeables pour le transport. */
export function palletResultsToLoadable(pallets: PalletResult[]): PalletToLoad[] {
  return pallets.map((pallet) => ({
    palletResultIndex: pallet.index,
    footprintLengthMm: pallet.config.dimensions.length + pallet.config.overhangMm,
    footprintWidthMm: pallet.config.dimensions.width + pallet.config.overhangMm,
    heightMm: pallet.config.emptyPalletHeightMm + pallet.maxHeightUsedMm,
    weightKg: pallet.totalWeightKg,
  }));
}

export function computeTransportLoad(pallets: PalletResult[], vehicle: VehicleConfig) {
  return loadPalletsIntoVehicles(palletResultsToLoadable(pallets), vehicle);
}
