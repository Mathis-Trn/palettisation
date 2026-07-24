"""Moteur de placement (points extrêmes) sur une palette, et boucle multi-palettes.

py3dbp (via `packing/py3dbp_adapter.py`, injecté comme `OrientationProvider`) n'est utilisé ici que
pour la primitive géométrique de rotation (les 6 permutations d'axes). La recherche de placement,
les contraintes métier (support, fragilité, gerbage, groupes incompatibles, espace de sécurité) et
le score de placement restent implémentés en Python, portés fidèlement de l'ancien moteur
TypeScript (`src/optimizer/engine.ts`, `packer.ts`) : py3dbp ne gère nativement ni la restriction
des rotations autorisées, ni l'espace de sécurité, ni le ratio de support, ni la fragilité, ni les
groupes incompatibles.

Garde-fou anti-boucle infinie : `can_instance_ever_fit` teste la faisabilité sur une palette VIDE
avant d'en ouvrir une nouvelle ; si même une palette vide ne peut accueillir le carton, il est
rejeté immédiatement avec un code précis, sans jamais ouvrir de palette supplémentaire pour rien.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from palletizer.application.ports import OrientationProvider
from palletizer.domain.enums import REJECTION_MESSAGES, OrientationCode, RejectionCode
from palletizer.domain.models import (
    CartonInstance,
    Dimensions3D,
    OptimizationOptions,
    PalletSpec,
    PlacedCarton,
    Position3D,
    UnplacedCarton,
)
from palletizer.packing import py3dbp_adapter
from palletizer.packing.constraints import allowed_orientations, is_compatible_with_pallet
from palletizer.packing.scoring import score_placement
from palletizer.packing.validation import EPSILON_MM, boxes_overlap, check_support, is_within_bounds

MAX_EXTREME_POINTS = 400
_ORIGIN = Position3D(0.0, 0.0, 0.0)


@dataclass(slots=True)
class WorkingPallet:
    boxes: list[PlacedCarton] = field(default_factory=list)
    instances: list[CartonInstance] = field(default_factory=list)
    extreme_points: list[Position3D] = field(default_factory=lambda: [_ORIGIN])
    total_weight_kg: float = 0.0


def _points_close(a: Position3D, b: Position3D) -> bool:
    return (
        abs(a.x_mm - b.x_mm) <= EPSILON_MM
        and abs(a.y_mm - b.y_mm) <= EPSILON_MM
        and abs(a.z_mm - b.z_mm) <= EPSILON_MM
    )


def _register_placement(pallet: WorkingPallet, position: Position3D, dims: Dimensions3D) -> None:
    pallet.extreme_points = [p for p in pallet.extreme_points if not _points_close(p, position)]
    candidates = (
        Position3D(position.x_mm + dims.length_mm, position.y_mm, position.z_mm),
        Position3D(position.x_mm, position.y_mm + dims.width_mm, position.z_mm),
        Position3D(position.x_mm, position.y_mm, position.z_mm + dims.height_mm),
    )
    for candidate in candidates:
        if not any(_points_close(candidate, existing) for existing in pallet.extreme_points):
            pallet.extreme_points.append(candidate)
    if len(pallet.extreme_points) > MAX_EXTREME_POINTS:
        pallet.extreme_points.sort(key=lambda p: (p.z_mm, p.x_mm + p.y_mm))
        pallet.extreme_points = pallet.extreme_points[:MAX_EXTREME_POINTS]


def can_instance_ever_fit(
    instance: CartonInstance,
    spec: PalletSpec,
    options: OptimizationOptions,
    orientation_provider: OrientationProvider = py3dbp_adapter.oriented_dimensions,
) -> tuple[bool, RejectionCode | None]:
    """Faisabilité sur une palette VIDE. Distingue poids / rotation interdite / hauteur / bornes."""
    if (
        instance.weight_kg is not None
        and spec.max_weight_kg is not None
        and instance.weight_kg > spec.max_weight_kg + 1e-9
    ):
        return False, RejectionCode.WEIGHT_EXCEEDED

    max_x, max_y, max_z = spec.usable_length_mm, spec.usable_width_mm, spec.usable_height_mm
    allowed = allowed_orientations(instance, options.global_rotations_enabled)
    for code in allowed:
        dims = orientation_provider(instance.dimensions_mm, code)
        if (
            dims.length_mm <= max_x + EPSILON_MM
            and dims.width_mm <= max_y + EPSILON_MM
            and (dims.height_mm <= max_z + EPSILON_MM)
        ):
            return True, None

    any_fits_all = False
    any_fits_footprint_only = False
    for code in py3dbp_adapter.ALL_ORIENTATIONS:
        dims = orientation_provider(instance.dimensions_mm, code)
        fits_footprint = (
            dims.length_mm <= max_x + EPSILON_MM and dims.width_mm <= max_y + EPSILON_MM
        )
        if fits_footprint and dims.height_mm <= max_z + EPSILON_MM:
            any_fits_all = True
        if fits_footprint:
            any_fits_footprint_only = True

    if any_fits_all:
        return False, RejectionCode.ROTATION_FORBIDDEN
    if any_fits_footprint_only:
        return False, RejectionCode.HEIGHT_EXCEEDED
    return False, RejectionCode.DIMENSIONS_EXCEED_PALLET


def try_place_on_pallet(
    instance: CartonInstance,
    pallet: WorkingPallet,
    spec: PalletSpec,
    options: OptimizationOptions,
    orientation_provider: OrientationProvider = py3dbp_adapter.oriented_dimensions,
) -> PlacedCarton | None:
    """Meilleure position/orientation valide sur cette palette, ou None si aucune ne convient."""
    if (
        spec.max_weight_kg is not None
        and instance.weight_kg is not None
        and pallet.total_weight_kg + instance.weight_kg > spec.max_weight_kg + 1e-9
    ):
        return None

    max_x, max_y, max_z = spec.usable_length_mm, spec.usable_width_mm, spec.usable_height_mm
    allowed = allowed_orientations(instance, options.global_rotations_enabled)

    candidates: list[
        tuple[float, float, float, float, str, Position3D, Dimensions3D, OrientationCode]
    ] = []
    for point in pallet.extreme_points:
        for code in allowed:
            dims = orientation_provider(instance.dimensions_mm, code)
            if not is_within_bounds(point, dims, max_x, max_y, max_z):
                continue
            if any(
                boxes_overlap(
                    point, dims, box.position_mm, box.placed_dimensions_mm, spec.safety_gap_mm
                )
                for box in pallet.boxes
            ):
                continue
            support = check_support(
                point,
                dims,
                instance.weight_kg,
                pallet.boxes,
                spec.minimum_support_ratio,
                options.fragile_max_weight_on_top_kg,
            )
            if not support.ok:
                continue
            score = score_placement(point, dims, support.support_ratio, instance.sku, pallet.boxes)
            candidates.append(
                (score, point.z_mm, point.y_mm, point.x_mm, code.value, point, dims, code)
            )

    if not candidates:
        return None

    best = min(candidates, key=lambda c: (-c[0], c[1], c[2], c[3], c[4]))
    score, _, _, _, _, position, dims, orientation = best
    return PlacedCarton(
        instance_id=instance.instance_id,
        sku=instance.sku,
        original_dimensions_mm=instance.dimensions_mm,
        placed_dimensions_mm=dims,
        position_mm=position,
        orientation=orientation,
        pallet_index=0,
        placement_score=score,
        fragile=instance.fragile,
        stackable=instance.stackable,
        weight_kg=instance.weight_kg,
        max_supported_weight_kg=instance.max_supported_weight_kg,
        product_group=instance.product_group,
    )


def pack_with_strategy(
    instances: Sequence[CartonInstance],
    spec: PalletSpec,
    options: OptimizationOptions,
    orientation_provider: OrientationProvider = py3dbp_adapter.oriented_dimensions,
) -> tuple[list[WorkingPallet], list[UnplacedCarton]]:
    """Boucle multi-palettes déterministe (port de `packer.ts::packWithStrategy`).

    Pour chaque instance (déjà triée par l'appelant selon la stratégie) : tenter les palettes déjà
    ouvertes et compatibles (groupes) ; sinon, si une palette VIDE ne pourrait de toute façon pas
    l'accueillir, rejeter immédiatement (garde-fou anti-boucle infinie) ; sinon ouvrir une nouvelle
    palette, sur laquelle le placement est garanti de réussir.
    """
    open_pallets: list[WorkingPallet] = []
    unplaced: list[UnplacedCarton] = []

    for instance in instances:
        placed_on: WorkingPallet | None = None
        for index, pallet in enumerate(open_pallets):
            if not is_compatible_with_pallet(instance, pallet.instances):
                continue
            result = try_place_on_pallet(instance, pallet, spec, options, orientation_provider)
            if result is not None:
                placed = replace(result, pallet_index=index)
                pallet.boxes.append(placed)
                pallet.instances.append(instance)
                if instance.weight_kg is not None:
                    pallet.total_weight_kg += instance.weight_kg
                _register_placement(pallet, placed.position_mm, placed.placed_dimensions_mm)
                placed_on = pallet
                break
        if placed_on is not None:
            continue

        fits, reason = can_instance_ever_fit(instance, spec, options, orientation_provider)
        if not fits:
            code = reason or RejectionCode.DIMENSIONS_EXCEED_PALLET
            unplaced.append(
                UnplacedCarton(
                    instance_id=instance.instance_id,
                    sku=instance.sku,
                    dimensions_mm=instance.dimensions_mm,
                    code=code,
                    message=REJECTION_MESSAGES[code],
                    weight_kg=instance.weight_kg,
                )
            )
            continue

        new_pallet = WorkingPallet()
        result = try_place_on_pallet(instance, new_pallet, spec, options, orientation_provider)
        if result is None:  # pragma: no cover - garde-fou : ne doit jamais se produire
            unplaced.append(
                UnplacedCarton(
                    instance_id=instance.instance_id,
                    sku=instance.sku,
                    dimensions_mm=instance.dimensions_mm,
                    code=RejectionCode.NO_STABLE_POSITION,
                    message=(
                        "Échec inattendu du placement sur une palette vide malgré un "
                        "pré-contrôle de faisabilité positif."
                    ),
                    weight_kg=instance.weight_kg,
                )
            )
            continue
        placed = replace(result, pallet_index=len(open_pallets))
        new_pallet.boxes.append(placed)
        new_pallet.instances.append(instance)
        if instance.weight_kg is not None:
            new_pallet.total_weight_kg += instance.weight_kg
        _register_placement(new_pallet, placed.position_mm, placed.placed_dimensions_mm)
        open_pallets.append(new_pallet)

    return open_pallets, unplaced
