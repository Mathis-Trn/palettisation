import { describe, expect, it } from "vitest";
import { optimizePallets } from "@/optimizer";
import type { CartonLine } from "@/domain/types";
import { assertNoOverlap, assertWithinBounds, makeCartonLine, makeSettings } from "./test-helpers";

describe("optimizePallets", () => {
  it("1. place un carton simple sur une palette", () => {
    const result = optimizePallets([makeCartonLine()], makeSettings());
    expect(result.palletsCount).toBe(1);
    expect(result.placedCartonsCount).toBe(1);
    expect(result.unplacedCartonsCount).toBe(0);
  });

  it("2. plusieurs cartons identiques créent le nombre minimal évident de palettes", () => {
    // Palette utile : 1200 x 800 x 956 mm. Carton 600x400x478 -> exactement 8 par palette (2x2x2).
    const line = makeCartonLine({
      dimensions: { length: 600, width: 400, height: 478 },
      quantity: 8,
      allowRotation: false,
    });
    const result = optimizePallets([line], makeSettings());
    expect(result.unplacedCartonsCount).toBe(0);
    expect(result.palletsCount).toBe(1);
    expect(result.pallets[0].volumeUsageRatio).toBeCloseTo(1, 2);

    const resultNinth = optimizePallets([{ ...line, quantity: 9 }], makeSettings());
    expect(resultNinth.unplacedCartonsCount).toBe(0);
    expect(resultNinth.palletsCount).toBe(2);
  });

  it("3 et 4. aucun chevauchement et aucun dépassement des limites, cas mixte", () => {
    const lines: CartonLine[] = [
      makeCartonLine({ sku: "A", dimensions: { length: 400, width: 300, height: 250 }, quantity: 15, weightKg: 6 }),
      makeCartonLine({ sku: "B", dimensions: { length: 350, width: 250, height: 200 }, quantity: 12, weightKg: 4 }),
      makeCartonLine({ sku: "C", dimensions: { length: 200, width: 200, height: 150 }, quantity: 20, weightKg: 2 }),
    ];
    const result = optimizePallets(lines, makeSettings({ optimizationLevel: "approfondi" }));
    for (const pallet of result.pallets) {
      assertNoOverlap(pallet.placedCartons);
      assertWithinBounds(pallet.placedCartons, pallet.config);
    }
    expect(result.placedCartonsCount + result.unplacedCartonsCount).toBe(result.totalCartonsCount);
  });

  it("5. la hauteur maximale est respectée", () => {
    // Hauteur utile = 1100 - 144 = 956 mm. Avec L=1000,W=700,H=2000 : seule l'orientation LWH a une
    // empreinte (1000x700) qui rentre dans 1200x800, mais sa hauteur (2000) dépasse toujours 956,
    // et aucune autre orientation (même en pivotant) n'a une empreinte compatible. -> HEIGHT_EXCEEDED.
    const line = makeCartonLine({
      dimensions: { length: 1000, width: 700, height: 2000 },
      quantity: 1,
      uprightOnly: false,
      allowRotation: true,
    });
    const result = optimizePallets([line], makeSettings());
    expect(result.placedCartonsCount).toBe(0);
    expect(result.unplacedCartonsCount).toBe(1);
    expect(result.unplacedCartons[0].code).toBe("HEIGHT_EXCEEDED");
  });

  it("6. le poids maximal est respecté", () => {
    const line = makeCartonLine({ weightKg: 900, dimensions: { length: 300, width: 200, height: 150 }, quantity: 1 });
    const result = optimizePallets([line], makeSettings({ palletConfig: { ...makeSettings().palletConfig, maxWeightKg: 800 } }));
    expect(result.placedCartonsCount).toBe(0);
    expect(result.unplacedCartons[0].code).toBe("WEIGHT_EXCEEDED");
  });

  it("7. les rotations interdites sont respectées", () => {
    // Ne rentre en LWH (900x1000x200 -> x=900,y=1000>800) mais rentre en WHL (x=1000,y=200,z=900).
    const dims = { length: 900, width: 1000, height: 200 };
    const rotated = optimizePallets(
      [makeCartonLine({ dimensions: dims, allowRotation: true, uprightOnly: false, quantity: 1 })],
      makeSettings()
    );
    expect(rotated.placedCartonsCount).toBe(1);
    expect(rotated.pallets[0].placedCartons[0].orientation).not.toBe("LWH");

    const forbidden = optimizePallets(
      [makeCartonLine({ dimensions: dims, allowRotation: false, uprightOnly: false, quantity: 1 })],
      makeSettings()
    );
    expect(forbidden.placedCartonsCount).toBe(0);
    expect(forbidden.unplacedCartons[0].code).toBe("ROTATION_FORBIDDEN");
  });

  it("8. le sens vertical obligatoire est respecté (aucune bascule)", () => {
    const dims = { length: 900, width: 1000, height: 200 };
    const result = optimizePallets(
      [makeCartonLine({ dimensions: dims, allowRotation: true, uprightOnly: true, quantity: 1 })],
      makeSettings()
    );
    // Seule une bascule (WHL) permettrait de placer ce carton ; le sens vertical l'interdit.
    expect(result.placedCartonsCount).toBe(0);

    // Vérifie aussi que, lorsqu'un placement upright réussit, l'orientation reste LWH ou WLH.
    const okResult = optimizePallets(
      [makeCartonLine({ dimensions: { length: 400, width: 300, height: 250 }, uprightOnly: true, allowRotation: true, quantity: 1 })],
      makeSettings()
    );
    expect(["LWH", "WLH"]).toContain(okResult.pallets[0].placedCartons[0].orientation);
  });

  it("9. un carton trop grand dans toutes les orientations est rejeté", () => {
    const result = optimizePallets(
      [makeCartonLine({ dimensions: { length: 5000, width: 5000, height: 5000 }, quantity: 1 })],
      makeSettings()
    );
    expect(result.placedCartonsCount).toBe(0);
    expect(result.unplacedCartons[0].code).toBe("DIMENSIONS_EXCEED_PALLET");
  });

  it("12. le déterminisme : mêmes entrées -> même résultat", () => {
    const lines: CartonLine[] = [
      makeCartonLine({ sku: "A", quantity: 10, dimensions: { length: 300, width: 250, height: 200 } }),
      makeCartonLine({ sku: "B", quantity: 7, dimensions: { length: 400, width: 300, height: 220 }, fragile: true, stackable: false }),
    ];
    const settings = makeSettings({ optimizationLevel: "approfondi" });
    const result1 = optimizePallets(lines, settings);
    const result2 = optimizePallets(lines, settings);

    const strip = (r: typeof result1) => ({
      pallets: r.pallets.map((p) => p.placedCartons.map((c) => ({ id: c.instanceId, pos: c.position, orientation: c.orientation }))),
      unplaced: r.unplacedCartons.map((u) => u.instanceId),
    });
    expect(strip(result1)).toEqual(strip(result2));
  });

  it("15. l'occupation volumique est correctement calculée", () => {
    // Palette utile : 1200 x 800 x 956 mm = 917 760 000 mm³. Un carton 600x400x478 = 114 720 000 mm³.
    const result = optimizePallets(
      [makeCartonLine({ dimensions: { length: 600, width: 400, height: 478 }, quantity: 1, allowRotation: false })],
      makeSettings()
    );
    const usableVolume = 1200 * 800 * 956;
    const cartonVolume = 600 * 400 * 478;
    expect(result.pallets[0].usableVolumeMm3).toBe(usableVolume);
    expect(result.pallets[0].volumeUsedMm3).toBe(cartonVolume);
    expect(result.pallets[0].volumeUsageRatio).toBeCloseTo(cartonVolume / usableVolume, 9);
  });
});
