import { describe, expect, it } from "vitest";
import {
  cartonLineToOrderLineContract,
  contractToOptimizationResult,
  contractToTransportLoadResult,
  orderLineContractToCartonLine,
  transportModeToShippingMode,
} from "@/lib/api/to-domain";
import type { CartonLine } from "@/domain/types";
import type { PalletizeResponseContract, TransportLoadResponseContract } from "@/lib/api/contract-types";

describe("transportModeToShippingMode", () => {
  it("maps the three transport modes to the contract's shipping modes", () => {
    expect(transportModeToShippingMode("routier")).toBe("road");
    expect(transportModeToShippingMode("maritime")).toBe("sea");
    expect(transportModeToShippingMode("aerien")).toBe("air");
  });
});

describe("cartonLineToOrderLineContract / orderLineContractToCartonLine round trip", () => {
  it("preserves all fields through a round trip", () => {
    const line: CartonLine = {
      sku: "BOX-A",
      dimensions: { length: 400, width: 300, height: 250 },
      quantity: 12,
      weightKg: 8.5,
      allowRotation: true,
      uprightOnly: false,
      fragile: true,
      stackable: false,
      maxSupportedWeightKg: 20,
      productGroup: "chimie",
      incompatibleGroups: ["alimentaire"],
    };
    const contract = cartonLineToOrderLineContract(line, 3);
    expect(contract.lineNumber).toBe(3);
    expect(contract.dimensionsMm).toEqual({ length: 400, width: 300, height: 250 });

    const roundTripped = orderLineContractToCartonLine(contract);
    expect(roundTripped).toEqual(line);
  });
});

describe("contractToOptimizationResult", () => {
  it("converts a full palletize response into the render-model shape", () => {
    const response: PalletizeResponseContract = {
      contractVersion: "1.0",
      orderId: "SO-1",
      engineVersion: "1.0.0",
      durationMs: 12.5,
      warnings: [],
      totalCartonsCount: 1,
      placedCartonsCount: 1,
      unplacedCartonsCount: 0,
      palletsCount: 1,
      globalVolumeUsageRatio: 0.5,
      totalWeightKg: 5,
      pallets: [
        {
          index: 0,
          config: {
            code: "P:80x120x110",
            lengthMm: 800,
            widthMm: 1200,
            maxHeightMm: 1100,
            emptyPalletHeightMm: 144,
            maxHeightIncludesPallet: true,
            maxWeightKg: 1000,
            overhangMm: 0,
            safetyGapMm: 0,
            minimumSupportRatio: 0.8,
          },
          totalWeightKg: 5,
          usableVolumeMm3: 1000,
          volumeUsedMm3: 500,
          volumeUsageRatio: 0.5,
          footprintUsageRatio: 0.5,
          maxHeightUsedMm: 100,
          placedCartons: [
            {
              instanceId: "BOX__00001",
              sku: "BOX",
              originalDimensionsMm: { length: 100, width: 100, height: 100 },
              placedDimensionsMm: { length: 100, width: 100, height: 100 },
              positionMm: { x: 0, y: 0, z: 0 },
              orientation: "LWH",
              palletIndex: 0,
              placementScore: 42,
              weightKg: 5,
              fragile: false,
              stackable: true,
              productGroup: null,
            },
          ],
        },
      ],
      unplacedCartons: [],
      legacyExpectedResult: { palletCount: 3 },
    };

    const result = contractToOptimizationResult(response);
    expect(result.pallets).toHaveLength(1);
    expect(result.pallets[0].config.dimensions).toEqual({ length: 800, width: 1200, height: 1100 });
    expect(result.pallets[0].placedCartons[0]).toMatchObject({
      instanceId: "BOX__00001",
      position: { x: 0, y: 0, z: 0 },
      placementScore: 42,
    });
    expect(result.placedCartonsCount).toBe(1);
  });
});

describe("contractToTransportLoadResult", () => {
  it("passes through placements with the same field names the floor-plan component expects", () => {
    const response: TransportLoadResponseContract = {
      contractVersion: "1.0",
      vehicles: [
        {
          index: 0,
          placements: [
            {
              palletResultIndex: 0,
              vehicleIndex: 0,
              x: 10,
              y: 20,
              rotated: false,
              stackLevel: 0,
              lengthMm: 1200,
              widthMm: 800,
              heightMm: 1100,
              weightKg: 300,
            },
          ],
          usedFloorAreaRatio: 0.4,
          usedWeightKg: 300,
        },
      ],
      unassignedPalletIndexes: [],
      vehiclesNeeded: 1,
      palletsLoadable: 1,
    };

    const result = contractToTransportLoadResult(response);
    expect(result.vehicles[0].placements[0]).toEqual({
      palletResultIndex: 0,
      vehicleIndex: 0,
      x: 10,
      y: 20,
      rotated: false,
      stackLevel: 0,
      lengthMm: 1200,
      widthMm: 800,
      heightMm: 1100,
      weightKg: 300,
    });
  });
});
