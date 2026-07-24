import type { PalletConfig, SimulationSettings } from "@/domain/types";
import { canInstanceEverFit, createEmptyPallet, tryPlaceOnPallet } from "./engine";
import { sortInstances } from "./sort-strategies";
import type { CartonInstance, PackingStrategyResult, SortStrategyName, WorkingPallet } from "./types";

/** Vérifie qu'une instance est compatible avec toutes les instances déjà présentes sur la palette. */
function isCompatibleWithPallet(instance: CartonInstance, pallet: WorkingPallet): boolean {
  return pallet.boxes.every((box) => {
    const otherGroup = box.instance.productGroup;
    const thisGroup = instance.productGroup;
    if (otherGroup && instance.incompatibleGroups.includes(otherGroup)) return false;
    if (thisGroup && box.instance.incompatibleGroups.includes(thisGroup)) return false;
    return true;
  });
}

/**
 * Emballe l'ensemble des instances selon une seule stratégie de tri.
 * Garantie de terminaison : chaque instance est soit placée, soit rejetée avec un code,
 * après au plus une tentative d'ouverture de nouvelle palette (jamais de boucle indéfinie).
 */
export function packWithStrategy(
  instances: CartonInstance[],
  palletConfig: PalletConfig,
  settings: SimulationSettings,
  strategyName: SortStrategyName,
  onInstanceProcessed?: (processedCount: number, palletsSoFar: number) => void
): PackingStrategyResult {
  const sorted = sortInstances(instances, strategyName);
  const pallets: WorkingPallet[] = [];
  const unplaced: PackingStrategyResult["unplaced"] = [];

  let processed = 0;
  for (const instance of sorted) {
    let placed = false;

    for (const pallet of pallets) {
      if (!isCompatibleWithPallet(instance, pallet)) continue;
      const result = tryPlaceOnPallet(instance, pallet, palletConfig, settings);
      if (result.success) {
        placed = true;
        break;
      }
    }

    if (!placed) {
      const feasibility = canInstanceEverFit(instance, palletConfig, settings.globalRotationsEnabled);
      if (!feasibility.fits) {
        unplaced.push({ instance, failure: feasibility.failure! });
      } else {
        const newPallet = createEmptyPallet();
        const result = tryPlaceOnPallet(instance, newPallet, palletConfig, settings);
        if (result.success) {
          pallets.push(newPallet);
          placed = true;
        } else {
          // Ne devrait pas se produire si `canInstanceEverFit` est cohérent avec `tryPlaceOnPallet`
          // sur une palette vide ; conservé comme filet de sécurité pour éviter toute boucle.
          unplaced.push({ instance, failure: result.failure });
        }
      }
    }

    processed += 1;
    onInstanceProcessed?.(processed, pallets.length);
  }

  return { strategyName, pallets, unplaced };
}
