import { describe, expect, it } from "vitest";
import { createEmptyPallet, tryPlaceOnPallet } from "@/optimizer/engine";
import { checkSupport } from "@/optimizer/support";
import type { CartonInstance } from "@/optimizer/types";
import { makePalletConfig, makeSettings } from "./test-helpers";

function makeInstance(overrides: Partial<CartonInstance> = {}): CartonInstance {
  return {
    instanceId: "inst-1",
    sku: "BOX",
    lineIndex: 0,
    dimensions: { length: 400, width: 400, height: 200 },
    weightKg: 5,
    allowRotation: false,
    uprightOnly: true,
    fragile: false,
    stackable: true,
    incompatibleGroups: [],
    ...overrides,
  };
}

describe("tryPlaceOnPallet - gerbage et stabilité", () => {
  it("10. un carton non gerbable ne reçoit aucun carton au-dessus", () => {
    const palletConfig = makePalletConfig();
    const settings = makeSettings({ palletConfig });
    const pallet = createEmptyPallet();

    // Le premier carton occupe toute l'empreinte utile et n'est pas gerbable.
    const base = makeInstance({
      instanceId: "base",
      dimensions: { length: 1200, width: 800, height: 100 },
      stackable: false,
    });
    const baseResult = tryPlaceOnPallet(base, pallet, palletConfig, settings);
    expect(baseResult.success).toBe(true);

    // Un second carton ne peut être placé qu'au-dessus (empreinte déjà saturée) -> doit être rejeté.
    const second = makeInstance({ instanceId: "second", dimensions: { length: 400, width: 400, height: 100 } });
    const secondResult = tryPlaceOnPallet(second, pallet, palletConfig, settings);
    expect(secondResult.success).toBe(false);
    if (!secondResult.success) {
      expect(secondResult.failure.code).toBe("STACKING_CONSTRAINT");
    }
  });

  it("11. le ratio de support minimal est respecté", () => {
    const supportBox = {
      instance: makeInstance({ instanceId: "support", stackable: true, dimensions: { length: 400, width: 400, height: 200 } }),
      position: { x: 0, y: 0, z: 0 },
      orientation: "LWH" as const,
      placedDimensions: { length: 400, width: 400, height: 200 },
      score: 0,
    };

    // 50% de recouvrement seulement (candidat décalé de moitié en X) : ratio 0.8 non atteint.
    const halfSupport = checkSupport(
      { x: 200, y: 0, z: 200 },
      { length: 400, width: 400, height: 200 },
      3,
      [supportBox],
      0.8,
      0
    );
    expect(halfSupport.ok).toBe(false);
    expect(halfSupport.reason).toBe("NO_STABLE_POSITION");
    expect(halfSupport.supportRatio).toBeCloseTo(0.5, 5);

    // Recouvrement complet : le ratio de 1.0 satisfait largement le minimum de 0.8.
    const fullSupport = checkSupport({ x: 0, y: 0, z: 200 }, { length: 400, width: 400, height: 200 }, 3, [supportBox], 0.8, 0);
    expect(fullSupport.ok).toBe(true);
    expect(fullSupport.supportRatio).toBeCloseTo(1, 5);
  });

  it("règle de fragilité : un carton fragile ne supporte pas de poids au-dessus du seuil configuré", () => {
    const fragileBox = {
      instance: makeInstance({ instanceId: "fragile", fragile: true, stackable: true }),
      position: { x: 0, y: 0, z: 0 },
      orientation: "LWH" as const,
      placedDimensions: { length: 400, width: 400, height: 200 },
      score: 0,
    };
    const tooHeavy = checkSupport({ x: 0, y: 0, z: 200 }, { length: 400, width: 400, height: 100 }, 5, [fragileBox], 0.8, 2);
    expect(tooHeavy.ok).toBe(false);
    expect(tooHeavy.reason).toBe("STACKING_CONSTRAINT");

    const lightEnough = checkSupport({ x: 0, y: 0, z: 200 }, { length: 400, width: 400, height: 100 }, 1, [fragileBox], 0.8, 2);
    expect(lightEnough.ok).toBe(true);
  });
});
