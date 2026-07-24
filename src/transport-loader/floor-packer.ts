import type { PalletToLoad, TransportLoadResult, VehicleConfig, VehicleLoadResult } from "./types";

type Shelf = {
  yStart: number;
  height: number;
  xCursor: number;
};

type OpenVehicle = {
  result: VehicleLoadResult;
  shelves: Shelf[];
  usedWeightKg: number;
};

/**
 * Placement 2D des empreintes de palettes sur le plancher du véhicule, par une heuristique
 * de type "étagères" (shelf packing, Next-Fit Decreasing Height) : simple, déterministe,
 * suffisante pour une estimation de chargement. Ce n'est pas un plan de calage certifié.
 *
 * Si `vehicle.allowPalletStacking` est actif, une seconde passe empile les palettes restantes
 * directement au-dessus de palettes déjà posées, lorsque la hauteur cumulée et le poids le permettent.
 */
export function loadPalletsIntoVehicles(pallets: PalletToLoad[], vehicle: VehicleConfig): TransportLoadResult {
  const sorted = [...pallets].sort(
    (a, b) =>
      b.footprintLengthMm * b.footprintWidthMm - a.footprintLengthMm * a.footprintWidthMm ||
      a.palletResultIndex - b.palletResultIndex
  );

  const vehicles: OpenVehicle[] = [];
  const unassigned: number[] = [];
  const remainingAfterFloor: PalletToLoad[] = [];

  function openNewVehicle(): OpenVehicle {
    const v: OpenVehicle = {
      result: { index: vehicles.length, placements: [], usedFloorAreaRatio: 0, usedWeightKg: 0 },
      shelves: [{ yStart: 0, height: 0, xCursor: 0 }],
      usedWeightKg: 0,
    };
    vehicles.push(v);
    return v;
  }

  function fitsEmptyVehicle(pallet: PalletToLoad): boolean {
    if (pallet.heightMm > vehicle.innerHeightMm) return false;
    if (pallet.weightKg > vehicle.maxPayloadKg) return false;
    const normalFits = pallet.footprintLengthMm <= vehicle.innerLengthMm && pallet.footprintWidthMm <= vehicle.innerWidthMm;
    const rotatedFits =
      vehicle.allowPalletRotationFloor &&
      pallet.footprintWidthMm <= vehicle.innerLengthMm &&
      pallet.footprintLengthMm <= vehicle.innerWidthMm;
    return normalFits || rotatedFits;
  }

  function tryPlaceOnShelves(v: OpenVehicle, pallet: PalletToLoad): boolean {
    const orientations = vehicle.allowPalletRotationFloor
      ? [
          { length: pallet.footprintLengthMm, width: pallet.footprintWidthMm, rotated: false },
          { length: pallet.footprintWidthMm, width: pallet.footprintLengthMm, rotated: true },
        ]
      : [{ length: pallet.footprintLengthMm, width: pallet.footprintWidthMm, rotated: false }];

    // Essaie d'abord la dernière étagère ouverte, puis en ouvre une nouvelle si nécessaire.
    for (const shelf of v.shelves) {
      for (const orientation of orientations) {
        const shelfHeight = shelf.height === 0 ? orientation.width : shelf.height;
        if (orientation.width > shelfHeight + 1e-6) continue;
        if (shelf.xCursor + orientation.length > vehicle.innerLengthMm + 1e-6) continue;
        if (shelf.yStart + shelfHeight > vehicle.innerWidthMm + 1e-6) continue;

        shelf.height = shelfHeight;
        v.result.placements.push({
          palletResultIndex: pallet.palletResultIndex,
          vehicleIndex: v.result.index,
          x: shelf.xCursor,
          y: shelf.yStart,
          rotated: orientation.rotated,
          stackLevel: 0,
          lengthMm: orientation.length,
          widthMm: orientation.width,
          heightMm: pallet.heightMm,
          weightKg: pallet.weightKg,
        });
        shelf.xCursor += orientation.length;
        v.usedWeightKg += pallet.weightKg;
        return true;
      }
    }

    // Aucune étagère existante ne convient : ouvre une nouvelle étagère si la place verticale le permet.
    const lastShelf = v.shelves[v.shelves.length - 1];
    const nextYStart = lastShelf.yStart + lastShelf.height;
    for (const orientation of orientations) {
      if (orientation.length > vehicle.innerLengthMm + 1e-6) continue;
      if (nextYStart + orientation.width > vehicle.innerWidthMm + 1e-6) continue;

      const newShelf: Shelf = { yStart: nextYStart, height: orientation.width, xCursor: orientation.length };
      v.shelves.push(newShelf);
      v.result.placements.push({
        palletResultIndex: pallet.palletResultIndex,
        vehicleIndex: v.result.index,
        x: 0,
        y: nextYStart,
        rotated: orientation.rotated,
        stackLevel: 0,
        lengthMm: orientation.length,
        widthMm: orientation.width,
        heightMm: pallet.heightMm,
        weightKg: pallet.weightKg,
      });
      v.usedWeightKg += pallet.weightKg;
      return true;
    }

    return false;
  }

  function tryStackOnAnyVehicle(pallet: PalletToLoad): boolean {
    for (const v of vehicles) {
      const floorPlacements = v.result.placements.filter((p) => p.stackLevel === 0);
      const target = floorPlacements.find((base) => {
        const alreadyStacked = v.result.placements.some((p) => p.stackLevel === 1 && p.x === base.x && p.y === base.y);
        if (alreadyStacked) return false;
        if (base.heightMm + pallet.heightMm > vehicle.innerHeightMm + 1e-6) return false;
        if (v.usedWeightKg + pallet.weightKg > vehicle.maxPayloadKg + 1e-6) return false;
        return pallet.footprintLengthMm <= base.lengthMm + 1e-6 && pallet.footprintWidthMm <= base.widthMm + 1e-6;
      });
      if (!target) continue;

      v.result.placements.push({
        palletResultIndex: pallet.palletResultIndex,
        vehicleIndex: v.result.index,
        x: target.x,
        y: target.y,
        rotated: false,
        stackLevel: 1,
        lengthMm: pallet.footprintLengthMm,
        widthMm: pallet.footprintWidthMm,
        heightMm: pallet.heightMm,
        weightKg: pallet.weightKg,
      });
      v.usedWeightKg += pallet.weightKg;
      return true;
    }
    return false;
  }

  let current = openNewVehicle();
  for (const pallet of sorted) {
    if (!fitsEmptyVehicle(pallet)) {
      unassigned.push(pallet.palletResultIndex);
      continue;
    }

    if (current.usedWeightKg + pallet.weightKg > vehicle.maxPayloadKg + 1e-6) {
      current = openNewVehicle();
    }

    let placed = tryPlaceOnShelves(current, pallet);

    // L'empilage est tenté sur les véhicules déjà ouverts avant d'en ouvrir un nouveau :
    // cela reflète mieux l'intérêt pratique de l'empilage (limiter le nombre de véhicules).
    if (!placed && vehicle.allowPalletStacking) {
      placed = tryStackOnAnyVehicle(pallet);
    }

    if (!placed) {
      current = openNewVehicle();
      placed = tryPlaceOnShelves(current, pallet);
    }

    if (!placed) {
      remainingAfterFloor.push(pallet);
    }
  }

  for (const pallet of remainingAfterFloor) unassigned.push(pallet.palletResultIndex);

  for (const v of vehicles) {
    const floorArea = vehicle.innerLengthMm * vehicle.innerWidthMm;
    const usedArea = v.result.placements
      .filter((p) => p.stackLevel === 0)
      .reduce((sum, p) => sum + p.lengthMm * p.widthMm, 0);
    v.result.usedFloorAreaRatio = floorArea > 0 ? Math.min(1, usedArea / floorArea) : 0;
    v.result.usedWeightKg = v.usedWeightKg;
  }

  const vehicleResults = vehicles.map((v) => v.result).filter((v) => v.placements.length > 0);
  const totalLoadable = vehicleResults.reduce((sum, v) => sum + v.placements.length, 0);

  return {
    vehicles: vehicleResults,
    unassignedPalletIndexes: unassigned,
    vehiclesNeeded: vehicleResults.length,
    palletsLoadable: totalLoadable,
  };
}

