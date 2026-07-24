import { describe, expect, it } from "vitest";
import { optimizePallets } from "@/optimizer";
import { PALLET_PRESETS } from "@/domain/constants";
import type { CartonLine, SimulationSettings } from "@/domain/types";

const baseSettings: SimulationSettings = {
  transportMode: "routier",
  palletConfig: { ...PALLET_PRESETS.routier },
  globalRotationsEnabled: true,
  optimizationLevel: "rapide",
  fragileMaxWeightOnTopKg: 0,
};

const oneCarton: CartonLine[] = [
  {
    sku: "BOX-A",
    dimensions: { length: 400, width: 300, height: 250 },
    quantity: 1,
    weightKg: 8,
    allowRotation: true,
    uprightOnly: false,
    fragile: false,
    stackable: true,
  },
];

describe("smoke", () => {
  it("place un carton simple sur une palette", () => {
    const result = optimizePallets(oneCarton, baseSettings);
    expect(result.palletsCount).toBe(1);
    expect(result.placedCartonsCount).toBe(1);
    expect(result.unplacedCartonsCount).toBe(0);
  });
});
