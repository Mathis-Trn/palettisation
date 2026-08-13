"""Chargement des palettes dans un véhicule/conteneur — port fidèle de
`src/transport-loader/floor-packer.ts` (heuristique 2D « étagères », Next-Fit Decreasing Height,
plus une passe d'empilage optionnelle). Ce n'est pas un solveur combinatoire complet : le module
reste volontairement simple, comme dans la version TypeScript d'origine.

Indépendant du reste du moteur : ne consomme que `PalletToLoad` (empreinte/poids d'une palette déjà
chargée), jamais les cartons individuels.
"""

from __future__ import annotations

from palletizer.domain.models import (
    LoadedPalletPlacement,
    PalletToLoad,
    TransportLoadResult,
    VehicleConfig,
    VehicleLoadResult,
)


def _footprint(pallet: PalletToLoad, rotated: bool) -> tuple[float, float]:
    if rotated:
        return pallet.footprint_width_mm, pallet.footprint_length_mm
    return pallet.footprint_length_mm, pallet.footprint_width_mm


def _pack_floor(
    pallets: list[PalletToLoad], vehicle: VehicleConfig, vehicle_index: int
) -> tuple[list[LoadedPalletPlacement], list[PalletToLoad], float, float]:
    """Une passe « étagères » (shelf packing, Next-Fit Decreasing Height) au sol du véhicule."""
    placements: list[LoadedPalletPlacement] = []
    remaining: list[PalletToLoad] = []
    used_weight = 0.0
    shelf_y = 0.0
    shelf_height = 0.0
    cursor_x = 0.0

    for pallet in pallets:
        placed = False
        for rotated in (False, True) if vehicle.allow_pallet_rotation_floor else (False,):
            length, width = _footprint(pallet, rotated)
            if length > vehicle.inner_length_mm or width > vehicle.inner_width_mm:
                continue
            if used_weight + pallet.weight_kg > vehicle.max_payload_kg + 1e-9:
                continue

            if cursor_x + length > vehicle.inner_length_mm + 1e-9:
                shelf_y += shelf_height
                cursor_x = 0.0
                shelf_height = 0.0

            if shelf_y + width > vehicle.inner_width_mm + 1e-9:
                continue

            placements.append(
                LoadedPalletPlacement(
                    pallet_result_index=pallet.pallet_result_index,
                    vehicle_index=vehicle_index,
                    x_mm=cursor_x,
                    y_mm=shelf_y,
                    rotated=rotated,
                    stack_level=0,
                    length_mm=length,
                    width_mm=width,
                    height_mm=pallet.height_mm,
                    weight_kg=pallet.weight_kg,
                )
            )
            used_weight += pallet.weight_kg
            cursor_x += length
            shelf_height = max(shelf_height, width)
            placed = True
            break

        if not placed:
            remaining.append(pallet)

    floor_area_used = sum(p.length_mm * p.width_mm for p in placements)
    return placements, remaining, used_weight, floor_area_used


def _pack_stacking(
    floor_placements: list[LoadedPalletPlacement],
    remaining: list[PalletToLoad],
    vehicle: VehicleConfig,
    vehicle_index: int,
    used_weight: float,
) -> tuple[list[LoadedPalletPlacement], list[PalletToLoad], float]:
    """Passe d'empilage optionnelle : une palette restante par palette déjà posée au sol, si
    l'empreinte est compatible et si hauteur/poids cumulés respectent le véhicule."""
    if not vehicle.allow_pallet_stacking:
        return [], remaining, used_weight

    stacked: list[LoadedPalletPlacement] = []
    still_remaining: list[PalletToLoad] = []
    available_floor = list(floor_placements)

    for pallet in remaining:
        placed = False
        for i, base in enumerate(available_floor):
            if pallet.footprint_length_mm > base.length_mm + 1e-9 or (
                pallet.footprint_width_mm > base.width_mm + 1e-9
            ):
                continue
            if base.height_mm + pallet.height_mm > vehicle.inner_height_mm + 1e-9:
                continue
            if used_weight + pallet.weight_kg > vehicle.max_payload_kg + 1e-9:
                continue
            stacked.append(
                LoadedPalletPlacement(
                    pallet_result_index=pallet.pallet_result_index,
                    vehicle_index=vehicle_index,
                    x_mm=base.x_mm,
                    y_mm=base.y_mm,
                    rotated=False,
                    stack_level=1,
                    length_mm=pallet.footprint_length_mm,
                    width_mm=pallet.footprint_width_mm,
                    height_mm=pallet.height_mm,
                    weight_kg=pallet.weight_kg,
                )
            )
            used_weight += pallet.weight_kg
            del available_floor[i]
            placed = True
            break
        if not placed:
            still_remaining.append(pallet)

    return stacked, still_remaining, used_weight


def compute_transport_load(
    pallets: list[PalletToLoad], vehicle: VehicleConfig
) -> TransportLoadResult:
    """Charge des palettes dans des véhicules successifs jusqu'à épuisement, sans boucle infinie :
    si un véhicule vide ne peut accueillir aucune palette restante, le chargement s'arrête."""
    ordered = sorted(
        pallets,
        key=lambda p: (-(p.footprint_length_mm * p.footprint_width_mm), p.pallet_result_index),
    )
    vehicles: list[VehicleLoadResult] = []
    remaining = ordered

    while remaining:
        floor_placements, still_remaining, used_weight, floor_area = _pack_floor(
            remaining, vehicle, len(vehicles)
        )
        stacked_placements, still_remaining, used_weight = _pack_stacking(
            floor_placements, still_remaining, vehicle, len(vehicles), used_weight
        )
        all_placements = floor_placements + stacked_placements

        if not all_placements:
            break  # garde-fou : aucune palette ne rentre dans un véhicule vide, on arrête

        vehicle_floor_area = vehicle.inner_length_mm * vehicle.inner_width_mm
        vehicles.append(
            VehicleLoadResult(
                index=len(vehicles),
                placements=tuple(all_placements),
                used_floor_area_ratio=(
                    floor_area / vehicle_floor_area if vehicle_floor_area > 0 else 0.0
                ),
                used_weight_kg=used_weight,
            )
        )
        remaining = still_remaining

    loaded_indexes = {placement.pallet_result_index for v in vehicles for placement in v.placements}
    unassigned = tuple(
        p.pallet_result_index for p in ordered if p.pallet_result_index not in loaded_indexes
    )
    return TransportLoadResult(
        vehicles=tuple(vehicles),
        unassigned_pallet_indexes=unassigned,
        vehicles_needed=len(vehicles),
        pallets_loadable=len(ordered) - len(unassigned),
    )
