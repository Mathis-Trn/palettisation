import { volumeOf } from "./geometry";
import type { CartonInstance, SortStrategyName } from "./types";

type Comparator = (a: CartonInstance, b: CartonInstance) => number;

/** Départage final déterministe : ordre d'entrée (instanceId), pour garantir la reproductibilité. */
function byInstanceId(a: CartonInstance, b: CartonInstance): number {
  return a.instanceId < b.instanceId ? -1 : a.instanceId > b.instanceId ? 1 : 0;
}

function largestDimension(instance: CartonInstance): number {
  const { length, width, height } = instance.dimensions;
  return Math.max(length, width, height);
}

const strategies: Record<SortStrategyName, Comparator> = {
  "volume-desc": (a, b) => volumeOf(b.dimensions) - volumeOf(a.dimensions) || byInstanceId(a, b),
  "largest-dimension-desc": (a, b) => largestDimension(b) - largestDimension(a) || byInstanceId(a, b),
  "weight-desc": (a, b) => (b.weightKg ?? 0) - (a.weightKg ?? 0) || byInstanceId(a, b),
  "footprint-desc": (a, b) =>
    b.dimensions.length * b.dimensions.width - a.dimensions.length * a.dimensions.width || byInstanceId(a, b),
};

/** Stratégies utilisées en mode rapide : une seule passe, volume décroissant. */
export const QUICK_STRATEGIES: SortStrategyName[] = ["volume-desc"];

/** Stratégies essayées en mode approfondi : la meilleure solution est conservée. */
export const THOROUGH_STRATEGIES: SortStrategyName[] = [
  "volume-desc",
  "largest-dimension-desc",
  "weight-desc",
  "footprint-desc",
];

export function sortInstances(instances: CartonInstance[], strategy: SortStrategyName): CartonInstance[] {
  return [...instances].sort(strategies[strategy]);
}
