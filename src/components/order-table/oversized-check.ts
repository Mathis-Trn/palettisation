import type { CartonLine, PalletConfig } from "@/domain/types";
import { getAllowedOrientations } from "@/optimizer/orientations";

/** Vrai si le carton ne rentre dans la palette dans aucune orientation autorisée (débordement inclus). */
export function isCartonOversizedForPallet(line: Pick<CartonLine, "dimensions" | "allowRotation" | "uprightOnly">, palletConfig: PalletConfig, globalRotationsEnabled: boolean): boolean {
  if (line.dimensions.length <= 0 || line.dimensions.width <= 0 || line.dimensions.height <= 0) return false;

  const usableHeight = palletConfig.maxHeightIncludesPallet
    ? palletConfig.dimensions.height - palletConfig.emptyPalletHeightMm
    : palletConfig.dimensions.height;
  const maxX = palletConfig.dimensions.length + palletConfig.overhangMm;
  const maxY = palletConfig.dimensions.width + palletConfig.overhangMm;

  const orientations = getAllowedOrientations(line.dimensions, line.allowRotation, line.uprightOnly, globalRotationsEnabled);
  return !orientations.some((o) => o.dims.length <= maxX && o.dims.width <= maxY && o.dims.height <= usableHeight);
}
