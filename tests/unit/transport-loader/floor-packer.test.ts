import { describe, expect, it } from "vitest";
import { loadPalletsIntoVehicles } from "@/transport-loader/floor-packer";
import type { PalletToLoad, VehicleConfig } from "@/transport-loader/types";

function makeVehicle(overrides: Partial<VehicleConfig> = {}): VehicleConfig {
  return {
    name: "Test",
    innerLengthMm: 13600,
    innerWidthMm: 2470,
    innerHeightMm: 2700,
    maxPayloadKg: 24000,
    allowPalletRotationFloor: true,
    allowPalletStacking: false,
    ...overrides,
  };
}

function makePallet(index: number, overrides: Partial<PalletToLoad> = {}): PalletToLoad {
  return {
    palletResultIndex: index,
    footprintLengthMm: 1200,
    footprintWidthMm: 800,
    heightMm: 1100,
    weightKg: 500,
    ...overrides,
  };
}

describe("loadPalletsIntoVehicles", () => {
  it("charge plusieurs palettes standard dans un seul véhicule quand la place le permet", () => {
    const pallets = Array.from({ length: 10 }, (_, i) => makePallet(i));
    const result = loadPalletsIntoVehicles(pallets, makeVehicle());
    expect(result.vehiclesNeeded).toBe(1);
    expect(result.palletsLoadable).toBe(10);
    expect(result.unassignedPalletIndexes).toHaveLength(0);
  });

  it("ouvre un second véhicule quand le poids maximal est dépassé", () => {
    const pallets = Array.from({ length: 5 }, (_, i) => makePallet(i, { weightKg: 6000 }));
    const result = loadPalletsIntoVehicles(pallets, makeVehicle({ maxPayloadKg: 24000 }));
    expect(result.vehiclesNeeded).toBeGreaterThanOrEqual(2);
    expect(result.unassignedPalletIndexes).toHaveLength(0);
  });

  it("rejette une palette dont la hauteur dépasse le véhicule", () => {
    const pallets = [makePallet(0, { heightMm: 3000 })];
    const result = loadPalletsIntoVehicles(pallets, makeVehicle());
    expect(result.unassignedPalletIndexes).toEqual([0]);
    expect(result.palletsLoadable).toBe(0);
  });

  it("empile les palettes restantes quand l'empilage est autorisé", () => {
    const pallets = [
      makePallet(0, { heightMm: 800 }),
      makePallet(1, { heightMm: 800 }),
    ];
    const vehicle = makeVehicle({ innerLengthMm: 1200, innerWidthMm: 800, innerHeightMm: 2000, allowPalletStacking: true });
    const result = loadPalletsIntoVehicles(pallets, vehicle);
    expect(result.palletsLoadable).toBe(2);
    expect(result.vehiclesNeeded).toBe(1);
  });

  it("ne chevauche jamais deux palettes sur la même étagère", () => {
    const pallets = Array.from({ length: 20 }, (_, i) => makePallet(i));
    const result = loadPalletsIntoVehicles(pallets, makeVehicle());
    for (const vehicle of result.vehicles) {
      const floor = vehicle.placements.filter((p) => p.stackLevel === 0);
      for (let i = 0; i < floor.length; i += 1) {
        for (let j = i + 1; j < floor.length; j += 1) {
          const a = floor[i];
          const b = floor[j];
          const overlapX = a.x < b.x + b.lengthMm && b.x < a.x + a.lengthMm;
          const overlapY = a.y < b.y + b.widthMm && b.y < a.y + a.widthMm;
          expect(overlapX && overlapY).toBe(false);
        }
      }
    }
  });
});
