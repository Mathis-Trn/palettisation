"""Agrégation des métriques d'une palette — port de la partie `buildPalletResult` de
`src/optimizer/index.ts`."""

from __future__ import annotations

from collections.abc import Sequence

from palletizer.domain.models import PalletResult, PalletSpec, PlacedCarton
from palletizer.packing.validation import EPSILON_MM


def usable_volume_mm3(spec: PalletSpec) -> float:
    return spec.usable_length_mm * spec.usable_width_mm * spec.usable_height_mm


def build_pallet_result(
    index: int, spec: PalletSpec, placed_cartons: Sequence[PlacedCarton]
) -> PalletResult:
    boxes = tuple(placed_cartons)
    total_weight = sum(box.weight_kg or 0.0 for box in boxes)
    volume_used = sum(box.placed_dimensions_mm.volume_mm3 for box in boxes)
    usable_volume = usable_volume_mm3(spec)
    volume_usage_ratio = volume_used / usable_volume if usable_volume > 0 else 0.0

    ground_boxes = [box for box in boxes if box.position_mm.z_mm <= EPSILON_MM]
    footprint_used = sum(
        box.placed_dimensions_mm.length_mm * box.placed_dimensions_mm.width_mm
        for box in ground_boxes
    )
    usable_footprint = spec.usable_length_mm * spec.usable_width_mm
    footprint_usage_ratio = footprint_used / usable_footprint if usable_footprint > 0 else 0.0

    max_height_used = max(
        (box.position_mm.z_mm + box.placed_dimensions_mm.height_mm for box in boxes), default=0.0
    )

    return PalletResult(
        index=index,
        spec=spec,
        placed_cartons=boxes,
        total_weight_kg=total_weight,
        usable_volume_mm3=usable_volume,
        volume_used_mm3=volume_used,
        volume_usage_ratio=volume_usage_ratio,
        footprint_usage_ratio=footprint_usage_ratio,
        max_height_used_mm=max_height_used,
    )
