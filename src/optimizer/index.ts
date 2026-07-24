import type {
  CartonLine,
  OptimizationResult,
  OptimizerProgress,
  PalletConfig,
  PalletResult,
  SimulationSettings,
  UnplacedCarton,
} from "@/domain/types";
import { ENGINE_VERSION, PRACTICAL_INSTANCE_LIMIT } from "@/domain/constants";
import { expandCartonLines } from "./expand";
import { packWithStrategy } from "./packer";
import { QUICK_STRATEGIES, THOROUGH_STRATEGIES } from "./sort-strategies";
import { usableBounds } from "./engine";
import { volumeOf } from "./geometry";
import type { PackingStrategyResult, WorkingPallet } from "./types";

export type { OptimizerProgress };

function buildPalletResult(index: number, pallet: WorkingPallet, palletConfig: PalletConfig): PalletResult {
  const { maxX, maxY, maxZ } = usableBounds(palletConfig);
  const usableVolumeMm3 = maxX * maxY * maxZ;
  const volumeUsedMm3 = pallet.boxes.reduce((sum, box) => sum + volumeOf(box.placedDimensions), 0);
  const maxHeightUsedMm = pallet.boxes.reduce((max, box) => Math.max(max, box.position.z + box.placedDimensions.height), 0);

  const groundArea = maxX * maxY;
  const groundOccupied = pallet.boxes
    .filter((box) => box.position.z <= 1e-6)
    .reduce((sum, box) => sum + box.placedDimensions.length * box.placedDimensions.width, 0);
  const footprintUsageRatio = groundArea > 0 ? Math.min(1, groundOccupied / groundArea) : 0;

  return {
    index,
    config: palletConfig,
    placedCartons: pallet.boxes.map((box) => ({
      instanceId: box.instance.instanceId,
      sku: box.instance.sku,
      originalDimensions: box.instance.dimensions,
      placedDimensions: box.placedDimensions,
      position: box.position,
      orientation: box.orientation,
      weightKg: box.instance.weightKg,
      palletIndex: index,
      placementScore: box.score,
      fragile: box.instance.fragile,
      stackable: box.instance.stackable,
      productGroup: box.instance.productGroup,
    })),
    totalWeightKg: pallet.totalWeightKg,
    usableVolumeMm3,
    volumeUsedMm3,
    volumeUsageRatio: usableVolumeMm3 > 0 ? volumeUsedMm3 / usableVolumeMm3 : 0,
    footprintUsageRatio,
    maxHeightUsedMm,
  };
}

function toUnplacedCarton(entry: PackingStrategyResult["unplaced"][number]): UnplacedCarton {
  return {
    instanceId: entry.instance.instanceId,
    sku: entry.instance.sku,
    dimensions: entry.instance.dimensions,
    weightKg: entry.instance.weightKg,
    code: entry.failure.code,
    message: entry.failure.message,
  };
}

function strategyMetrics(result: PackingStrategyResult, palletConfig: PalletConfig) {
  const { maxX, maxY, maxZ } = usableBounds(palletConfig);
  const usableVolume = maxX * maxY * maxZ;
  const totalUsedVolume = result.pallets.reduce(
    (sum, pallet) => sum + pallet.boxes.reduce((s, box) => s + volumeOf(box.placedDimensions), 0),
    0
  );
  const totalUsableVolume = usableVolume * Math.max(1, result.pallets.length);
  const avgScore =
    result.pallets.reduce((sum, pallet) => sum + pallet.boxes.reduce((s, box) => s + box.score, 0), 0) /
    Math.max(1, result.pallets.reduce((n, pallet) => n + pallet.boxes.length, 0));

  return {
    palletsCount: result.pallets.length,
    volumeUsageRatio: totalUsableVolume > 0 ? totalUsedVolume / totalUsableVolume : 0,
    avgScore,
  };
}

/** Vrai si `candidate` constitue une meilleure solution que `current` : moins de palettes, puis
 *  meilleur taux de remplissage, puis meilleure stabilité moyenne. */
function isBetterStrategy(candidate: PackingStrategyResult, current: PackingStrategyResult, palletConfig: PalletConfig): boolean {
  const a = strategyMetrics(candidate, palletConfig);
  const b = strategyMetrics(current, palletConfig);
  if (a.palletsCount !== b.palletsCount) return a.palletsCount < b.palletsCount;
  if (Math.abs(a.volumeUsageRatio - b.volumeUsageRatio) > 1e-9) return a.volumeUsageRatio > b.volumeUsageRatio;
  return a.avgScore > b.avgScore;
}

export function optimizePallets(
  cartonLines: CartonLine[],
  settings: SimulationSettings,
  onProgress?: (progress: OptimizerProgress) => void
): OptimizationResult {
  const start = Date.now();
  const { instances, invalid } = expandCartonLines(cartonLines);

  const strategies = settings.optimizationLevel === "rapide" ? QUICK_STRATEGIES : THOROUGH_STRATEGIES;

  let best: PackingStrategyResult | null = null;
  strategies.forEach((strategyName, strategyIndex) => {
    const result = packWithStrategy(instances, settings.palletConfig, settings, strategyName, (processedCount, palletsSoFar) => {
      onProgress?.({
        phase: "placement",
        processedInstances: processedCount,
        totalInstances: instances.length,
        currentPalletIndex: palletsSoFar,
        strategyIndex,
        strategiesCount: strategies.length,
      });
    });
    if (!best || isBetterStrategy(result, best, settings.palletConfig)) {
      best = result;
    }
  });

  const finalResult = best ?? { strategyName: strategies[0], pallets: [], unplaced: [] };

  const pallets = finalResult.pallets.map((pallet, index) => buildPalletResult(index, pallet, settings.palletConfig));
  const unplacedFromPacking = finalResult.unplaced.map(toUnplacedCarton);
  const unplacedCartons: UnplacedCarton[] = [...invalid, ...unplacedFromPacking];

  const placedCartonsCount = pallets.reduce((sum, p) => sum + p.placedCartons.length, 0);
  const totalWeightKg = pallets.reduce((sum, p) => sum + p.totalWeightKg, 0);
  const totalUsableVolume = pallets.reduce((sum, p) => sum + p.usableVolumeMm3, 0);
  const totalUsedVolume = pallets.reduce((sum, p) => sum + p.volumeUsedMm3, 0);

  const warnings: string[] = [];
  if (instances.length > PRACTICAL_INSTANCE_LIMIT) {
    warnings.push(
      `La commande comporte ${instances.length} cartons, au-delà du seuil de fluidité recommandé (${PRACTICAL_INSTANCE_LIMIT}). Le mode rapide est conseillé.`
    );
  }
  if (invalid.length > 0) {
    warnings.push(`${invalid.length} ligne(s) de commande ignorée(s) pour données invalides.`);
  }
  if (unplacedFromPacking.length > 0) {
    warnings.push(`${unplacedFromPacking.length} carton(s) n'ont pas pu être placés sur une palette.`);
  }

  return {
    pallets,
    unplacedCartons,
    totalCartonsCount: instances.length + invalid.length,
    placedCartonsCount,
    unplacedCartonsCount: unplacedCartons.length,
    palletsCount: pallets.length,
    globalVolumeUsageRatio: totalUsableVolume > 0 ? totalUsedVolume / totalUsableVolume : 0,
    totalWeightKg,
    warnings,
    computedAtIso: new Date().toISOString(),
    engineVersion: ENGINE_VERSION,
    levelUsed: settings.optimizationLevel,
    durationMs: Date.now() - start,
  };
}

export { expandCartonLines } from "./expand";
export { getAllowedOrientations } from "./orientations";
export type { CartonInstance } from "./types";
