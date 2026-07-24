import type { CartonLine, UnplacedCarton } from "@/domain/types";
import { cartonLineSchema } from "@/domain/schemas";
import type { CartonInstance } from "./types";

export type ExpandResult = {
  instances: CartonInstance[];
  invalid: UnplacedCarton[];
};

/**
 * Développe chaque ligne de commande en instances individuelles de cartons (une par unité de quantité).
 * Les identifiants d'instance sont générés de façon déterministe (compteur global sur l'ordre d'entrée),
 * garantissant que deux exécutions sur les mêmes données produisent exactement les mêmes identifiants.
 */
export function expandCartonLines(lines: CartonLine[]): ExpandResult {
  const instances: CartonInstance[] = [];
  const invalid: UnplacedCarton[] = [];
  let globalCounter = 0;

  lines.forEach((line, lineIndex) => {
    const parsed = cartonLineSchema.safeParse(line);
    if (!parsed.success) {
      const message = parsed.error.issues.map((issue) => issue.message).join(" ");
      invalid.push({
        instanceId: `invalid-${lineIndex}`,
        sku: line.sku || `(ligne ${lineIndex + 1})`,
        dimensions: line.dimensions ?? { length: 0, width: 0, height: 0 },
        weightKg: line.weightKg,
        code: "INVALID_DATA",
        message: message || "Données invalides.",
      });
      return;
    }

    const data = parsed.data;
    for (let unit = 0; unit < data.quantity; unit += 1) {
      instances.push({
        instanceId: `${sanitizeSku(data.sku)}__${String(globalCounter).padStart(5, "0")}`,
        sku: data.sku,
        lineIndex,
        dimensions: data.dimensions,
        weightKg: data.weightKg,
        allowRotation: data.allowRotation,
        uprightOnly: data.uprightOnly,
        fragile: data.fragile,
        stackable: data.stackable,
        maxSupportedWeightKg: data.maxSupportedWeightKg,
        productGroup: data.productGroup,
        incompatibleGroups: data.incompatibleGroups ?? [],
      });
      globalCounter += 1;
    }
  });

  return { instances, invalid };
}

function sanitizeSku(sku: string): string {
  return sku.replace(/[^a-zA-Z0-9_-]/g, "-");
}
