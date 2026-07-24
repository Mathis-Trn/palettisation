import type { CartonLine, PalletConfig, SimulationSettings } from "@/domain/types";
import { PALLET_PRESETS } from "@/domain/constants";
import type { PlacedCarton } from "@/domain/types";

export function makeSettings(overrides: Partial<SimulationSettings> = {}): SimulationSettings {
  return {
    transportMode: "routier",
    palletConfig: makePalletConfig(),
    globalRotationsEnabled: true,
    optimizationLevel: "rapide",
    fragileMaxWeightOnTopKg: 0,
    ...overrides,
  };
}

export function makePalletConfig(overrides: Partial<PalletConfig> = {}): PalletConfig {
  return { ...PALLET_PRESETS.routier, ...overrides };
}

export function makeCartonLine(overrides: Partial<CartonLine> = {}): CartonLine {
  return {
    sku: "BOX",
    dimensions: { length: 400, width: 300, height: 250 },
    quantity: 1,
    weightKg: 5,
    allowRotation: true,
    uprightOnly: false,
    fragile: false,
    stackable: true,
    ...overrides,
  };
}

/** Vérifie qu'aucun carton placé ne chevauche un autre sur la même palette. */
export function assertNoOverlap(placedCartons: PlacedCarton[]): void {
  for (let i = 0; i < placedCartons.length; i += 1) {
    for (let j = i + 1; j < placedCartons.length; j += 1) {
      const a = placedCartons[i];
      const b = placedCartons[j];
      if (a.palletIndex !== b.palletIndex) continue;
      const overlapX = a.position.x < b.position.x + b.placedDimensions.length - 1e-6 && b.position.x < a.position.x + a.placedDimensions.length - 1e-6;
      const overlapY = a.position.y < b.position.y + b.placedDimensions.width - 1e-6 && b.position.y < a.position.y + a.placedDimensions.width - 1e-6;
      const overlapZ = a.position.z < b.position.z + b.placedDimensions.height - 1e-6 && b.position.z < a.position.z + a.placedDimensions.height - 1e-6;
      if (overlapX && overlapY && overlapZ) {
        throw new Error(`Chevauchement détecté entre ${a.instanceId} et ${b.instanceId}`);
      }
    }
  }
}

/** Vérifie qu'aucun carton ne dépasse les limites utiles de la palette (débordement inclus). */
export function assertWithinBounds(placedCartons: PlacedCarton[], palletConfig: PalletConfig): void {
  const maxX = palletConfig.dimensions.length + palletConfig.overhangMm;
  const maxY = palletConfig.dimensions.width + palletConfig.overhangMm;
  const usableHeight = palletConfig.maxHeightIncludesPallet
    ? palletConfig.dimensions.height - palletConfig.emptyPalletHeightMm
    : palletConfig.dimensions.height;

  for (const carton of placedCartons) {
    expectWithinBounds(carton, maxX, maxY, usableHeight);
  }
}

function expectWithinBounds(carton: PlacedCarton, maxX: number, maxY: number, maxZ: number): void {
  const eps = 1e-6;
  if (carton.position.x < -eps || carton.position.x + carton.placedDimensions.length > maxX + eps) {
    throw new Error(`Carton ${carton.instanceId} hors limites en X`);
  }
  if (carton.position.y < -eps || carton.position.y + carton.placedDimensions.width > maxY + eps) {
    throw new Error(`Carton ${carton.instanceId} hors limites en Y`);
  }
  if (carton.position.z < -eps || carton.position.z + carton.placedDimensions.height > maxZ + eps) {
    throw new Error(`Carton ${carton.instanceId} hors limites en Z`);
  }
}
