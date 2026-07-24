import { describe, expect, it } from "vitest";
import { expandCartonLines } from "@/optimizer/expand";
import { makeCartonLine } from "./test-helpers";

describe("expandCartonLines", () => {
  it("14. développe correctement les quantités en instances individuelles", () => {
    const { instances, invalid } = expandCartonLines([
      makeCartonLine({ sku: "A", quantity: 5 }),
      makeCartonLine({ sku: "B", quantity: 3 }),
    ]);
    expect(invalid).toHaveLength(0);
    expect(instances).toHaveLength(8);
    expect(instances.filter((i) => i.sku === "A")).toHaveLength(5);
    expect(instances.filter((i) => i.sku === "B")).toHaveLength(3);

    const ids = new Set(instances.map((i) => i.instanceId));
    expect(ids.size).toBe(8);
  });

  it("rejette une ligne avec des données invalides sans bloquer les autres lignes", () => {
    const { instances, invalid } = expandCartonLines([
      makeCartonLine({ sku: "VALID", quantity: 2 }),
      makeCartonLine({ sku: "INVALID", quantity: 0 }),
      makeCartonLine({ sku: "NEGATIVE", dimensions: { length: -10, width: 100, height: 100 } }),
    ]);
    expect(instances).toHaveLength(2);
    expect(invalid).toHaveLength(2);
    expect(invalid.every((u) => u.code === "INVALID_DATA")).toBe(true);
  });
});
